# Copyright (c) 2012-2014 Roger Light <roger@atchoo.org>
#
# This is a much stripped down version of Roger Light's paho.mqtt intended for micropython
# All rights reserved. This program and the accompanying materials
# are made available under the terms of the Eclipse Public License v1.0
# and Eclipse Distribution License v1.0
#

"""
This is an MQTT v3.1 client module for micropython.
"""
import select
import socket
import ustruct as struct
import utime as time

EAGAIN = const(11)

#PROTOCOL_NAMEv31 = b"MQIsdp" protocol=3

# Message types
CONNECT = const(0x10) 
CONNACK = const(0x20) 
PUBLISH = const(0x30) 
SUBSCRIBE = const(0x80) 
SUBACK = const(0x90) 
PINGREQ = 0xC0 
PINGRESP = const(0xD0) 

# Connection state
mqtt_cs_new = 0
mqtt_cs_connected = 1
mqtt_cs_disconnecting = 2
mqtt_cs_connect_async = 3

# Error values
MQTT_ERR_AGAIN = -1
MQTT_ERR_SUCCESS = 0
MQTT_ERR_PROTOCOL = 2
MQTT_ERR_NO_CONN = 4
MQTT_ERR_CONN_REFUSED = 5
MQTT_ERR_CONN_LOST = 7

class Client:
    """MQTT version 3.1/3.1.1 client class."""
    def __init__(self, client_id="", userdata=None, protocol=3):
        print("Client Class")
        self._protocol = protocol
        self._userdata = userdata
        self._sock = None
        self._keepalive = 60
        self._message_retry = 20
        self._last_retry_check = 0
        if client_id == "" or client_id is None:
            self._client_id = "umqtt"
        else:
            self._client_id = client_id

        self._username = ""
        self._password = ""
        self._in_packet = {
            "command": 0,
            "have_remaining": 0,
            "remaining_count": [],
            "remaining_mult": 1,
            "remaining_length": 0,
            "packet": b"",
            "to_process": 0,
            "pos": 0}
        self._current_out_packet = None
        self._last_msg = time.time()
        self._ping_t = 0
        self._last_mid = 0
        self._state = mqtt_cs_new
        self._max_inflight_messages = 20
        self._inflight_messages = 0
        self.on_connect = None
        self.on_message = None
        self.on_subscribe = None
        self._host = ""
        self._port = 1883
        self._bind_address = ""

    #def __del__(self):
    #    print("__del__ Client")
    #    pass

    def connect(self, host, port=1883, keepalive=60, bind_address=""):
        """Connect to a remote broker.
        """
        print("connect")

        self._host = host
        self._port = port
        self._keepalive = keepalive
        self._bind_address = bind_address
        print("connect: self._state =", self._state)
        self._state = mqtt_cs_connect_async
        return self.reconnect()

    def reconnect(self):
        """Reconnect the client after a disconnect."""
        print("reconnect")

        self._in_packet = {
            "command": 0,
            "have_remaining": 0,
            "remaining_count": [],
            "remaining_mult": 1,
            "remaining_length": 0,
            "packet": b"",
            "to_process": 0,
            "pos": 0}

        self._current_out_packet = None

        self._last_msg = time.time()

        self._ping_t = 0
        print("reconnect: self._state =", self._state)
        self._state = mqtt_cs_new
        if self._sock:
            self._sock.close()
            self._sock = None
            print("self._sock == None")

        sock = socket.create_connection((self._host, self._port), source_address=(self._bind_address, 0))
        self._sock = sock
        self._sock.setblocking(0)
        self.ep = select.epoll()
        self.fileno = self._sock.fileno()
        self.ep.register(self.fileno)

        print("self._sock =", self._sock)

        return self._send_connect(self._keepalive)

    def loop(self, timeout=1):
        """Process network events.
        """
        print("loop")

        events = self.ep.poll(timeout)
        print("events = ", events)
        for fileno, ev in events:
            if ev & select.EPOLLIN:
                rc = self.loop_read()
                if rc or (self._sock is None):
                    return rc

        if self._sock is None:
            return MQTT_ERR_NO_CONN

        now = time.time()
        self._check_keepalive()
        if self._last_retry_check+1 < now:
            # Only check once a second at most
            # can this go? ############################
            self._last_retry_check = now

        if self._ping_t > 0 and now - self._ping_t >= self._keepalive:
            # client->ping_t != 0 means we are waiting for a pingresp.
            # This hasn't happened in the keepalive time so we should disconnect.
            if self._sock:
                self._sock.close()
                self._sock = None

            return MQTT_ERR_CONN_LOST

        return MQTT_ERR_SUCCESS

    def subscribe(self, topic, qos=0):
        """Subscribe the client to one or more topics."""
        print("subscribe")
        topic_qos_list = None
        if isinstance(topic, str):
            if topic is None or len(topic) == 0:
                raise ValueError('Invalid topic.')
            topic_qos_list = [(topic.encode('utf-8'), qos)]
        elif isinstance(topic, list):
            topic_qos_list = []
            for t in topic:
                #if t[1]<0 or t[1]>2:
                #    raise ValueError('Invalid QoS level.')
                if t[0] is None or len(t[0]) == 0 or not isinstance(t[0], str):
                    raise ValueError('Invalid topic.')
                topic_qos_list.append((t[0].encode('utf-8'), t[1]))

        if topic_qos_list is None:
            raise ValueError("No topic specified, or incorrect topic type.")

        if self._sock is None: 
            return (MQTT_ERR_NO_CONN, None)

        return self._send_subscribe(False, topic_qos_list)

    def loop_read(self):
        """Process read network events. """
        print("loop_read")
        if self._sock is None:
            return MQTT_ERR_NO_CONN

        rc = self._packet_read() #only call to _packet_read
        print("loop_read: rc =", rc)
        return rc

    def loop_write(self):
        """Process write network events.""" 
        print("loop_write")
        if self._sock is None:
            return MQTT_ERR_NO_CONN

        rc = self._packet_write()
        return rc

    # ============================================================
    # Private functions
    # ============================================================

    def _packet_read(self):
        print("_packet_read")
        if self._in_packet['command'] == 0:
            try:
                command = self._sock.recv(1)
            except socket.error as err:
                if err.errno == EAGAIN:
                    return MQTT_ERR_AGAIN
                print(err)
                return 1
            else:
                if len(command) == 0:
                    return 1
                command = struct.unpack("!B", command)
                self._in_packet['command'] = command[0]

        if self._in_packet['have_remaining'] == 0:
            # Read remaining
            # Algorithm for decoding taken from pseudo code at
            # http://publib.boulder.ibm.com/infocenter/wmbhelp/v6r0m0/topic/com.ibm.etools.mft.doc/ac10870_.htm
            while True:
                try:
                    byte = self._sock.recv(1)
                except socket.error as err:
                    if err.errno == EAGAIN:
                        return MQTT_ERR_AGAIN
                    print(err)
                    return 1
                else:
                    byte = struct.unpack("!B", byte)
                    byte = byte[0]
                    self._in_packet['remaining_count'].append(byte)
                    # Max 4 bytes length for remaining length as defined by protocol.
                     # Anything more likely means a broken/malicious client.
                    if len(self._in_packet['remaining_count']) > 4:
                        return MQTT_ERR_PROTOCOL

                    self._in_packet['remaining_length'] = self._in_packet['remaining_length'] + (byte & 127)*self._in_packet['remaining_mult']
                    self._in_packet['remaining_mult'] = self._in_packet['remaining_mult'] * 128

                if (byte & 128) == 0:
                    break

            self._in_packet['have_remaining'] = 1
            self._in_packet['to_process'] = self._in_packet['remaining_length']

        while self._in_packet['to_process'] > 0:
            try:
                data = self._sock.recv(self._in_packet['to_process'])
            except socket.error as err:
                if err.errno == EAGAIN:
                    return MQTT_ERR_AGAIN
                print(err)
                return 1
            else:
                self._in_packet['to_process'] = self._in_packet['to_process'] - len(data)
                self._in_packet['packet'] = self._in_packet['packet'] + data

        # All data for this packet is read.
        self._in_packet['pos'] = 0
        rc = self._packet_handle()

        # Free data and reset values
        self._in_packet = dict(
            command=0,
            have_remaining=0,
            remaining_count=[],
            remaining_mult=1,
            remaining_length=0,
            packet=b"",
            to_process=0,
            pos=0)

        self._last_msg = time.time()
        return rc

    def _packet_write(self):
        print("_packet_write")

        while self._current_out_packet:
            print("_packet_write: self._current_out_packet = ",self._current_out_packet)
            packet = self._current_out_packet

            try:
                write_length = self._sock.send(packet['packet'][packet['pos']:])
            except:
                return 1

            if write_length > 0:
                packet['to_process'] = packet['to_process'] - write_length
                packet['pos'] = packet['pos'] + write_length

                if packet['to_process'] == 0:
                    self._current_out_packet = None
            else:
                break

        self._last_msg = time.time()
        print("_packet_write: end: self._current_out_packet =", self._current_out_packet)
        return MQTT_ERR_SUCCESS

    def _check_keepalive(self):
        print("_check_keepalive")
        now = time.time()
        print("_check_keepalive: self._last_msg = ", self._last_msg)
        last_msg = self._last_msg
        if (self._sock is not None) and (now - last_msg >= self._keepalive):
            print("_check_keepalive: self._state =", self._state)
            if self._ping_t == 0:
                #self._send_pingreq()
                packet = struct.pack('!BB', PINGREQ, 0)
                self._packet_queue(PINGREQ, packet, 0, 0)
                self._last_msg = now

    def _mid_generate(self):
        print("_mid_generate")
        self._last_mid = self._last_mid + 1
        if self._last_mid == 65536:
            self._last_mid = 1
        return self._last_mid

    def _pack_remaining_length(self, packet, remaining_length):
        print("_pack_remaining_length")
        #from _send_subscribe and _send_connect
        #remaining_bytes = [] ? not used for anything
        while True:
            byte = remaining_length % 128
            remaining_length = remaining_length // 128
            # If there are more digits to encode, set the top bit of this digit
            if remaining_length > 0:
                byte = byte | 0x80

            #remaining_bytes.append(byte)
            packet.extend(struct.pack("!B", byte))
            if remaining_length == 0:
                # FIXME - this doesn't deal with incorrectly large payloads
                return packet

    def _pack_str16(self, packet, data):
        print("_pack_str16")
        if isinstance(data, bytearray) or isinstance(data, bytes):
            packet.extend(struct.pack("!H", len(data)))
            packet.extend(data)
        elif isinstance(data, str):
            udata = data.encode('utf-8')
            pack_format = "!H" + str(len(udata)) + "s"
            packet.extend(struct.pack(pack_format, len(udata), udata))
        else:
            raise TypeError

    def _send_connect(self, keepalive):
        print("_send_connect")

        remaining_length = 2+6+1+1+2+2+len(self._client_id)
        #remaining_length = 2+len(protocol) + 1+1+2 + 2+len(self._client_id)
        connect_flags = 0
        connect_flags = connect_flags | 0x02

        if self._username:
            remaining_length = remaining_length + 2+len(self._username)
            connect_flags = connect_flags | 0x80
            if self._password:
                connect_flags = connect_flags | 0x40
                remaining_length = remaining_length + 2+len(self._password)

        command = CONNECT
        packet = bytearray()
        packet.extend(struct.pack("!B", command))

        self._pack_remaining_length(packet, remaining_length)
        #packet.extend(struct.pack("!H"+str(len(protocol))+"sBBH", len(protocol), protocol, proto_ver, connect_flags, keepalive))
        packet.extend(struct.pack("!H"+"6"+"sBBH", 6, b"MQIsdp", 3, connect_flags, keepalive))

        self._pack_str16(packet, self._client_id)

        if self._username:
            self._pack_str16(packet, self._username)

            if self._password:
                self._pack_str16(packet, self._password)

        self._keepalive = keepalive
        return self._packet_queue(command, packet, 0, 0)

    def _send_subscribe(self, dup, topics):
        print("_send_subscribe")
        remaining_length = 2

        #topic_qos_list = [(topic.encode('utf-8'), qos)] - > [('test', 0)]
        #remaining_length = 2 + 2+ len('test') +1 --> 9
        for t in topics:
            remaining_length = remaining_length + 2+len(t[0])+1

        #SUBSCRIBE = const(0x80) - > 0b10000000
        # According to spec the fixed header is 0b10000010 
        # According to spec the second byte is the remaining length = 2 bytes of varialbe header + payload
        # If QoS is zero the variable header is 0,0 or if > 1 would be some unique identifier
        # dup = 0 (I think)
        # 1<<1 -> 0b00000010
        command = SUBSCRIBE | (dup<<3) | (1<<1)
        packet = bytearray()
        packet.extend(struct.pack("!B", command))
        self._pack_remaining_length(packet, remaining_length) #operates on packet and extends it
        local_mid = self._mid_generate()
        packet.extend(struct.pack("!H", local_mid))
        for t in topics:
            self._pack_str16(packet, t[0])
            packet.extend(struct.pack("B", t[1]))
        return (self._packet_queue(command, packet, local_mid, 1), local_mid)

    def _packet_queue(self, command, packet, mid, qos):
        print("_packet_queue") #needed
        mpkt = dict(
            command = command,
            mid = mid,
            qos = qos,
            pos = 0,
            to_process = len(packet),
            packet = packet)

        self._current_out_packet = mpkt
        return self.loop_write()

    def _packet_handle(self):
        print("_packet_handle")
        cmd = self._in_packet['command']&0xF0
        if cmd == CONNACK: #needed
            print("_packet_handle: CONNACK")
            return self._handle_connack()
        elif cmd == SUBACK: #needed
            print("_packet_handle: SUBACK")
            return self._handle_suback()
        elif cmd == PINGRESP: #needed
            print("_packet_handle: PINGRESP")
            return self._handle_pingresp()
        elif cmd == PUBLISH: #needed
            print("_packet_handle: PUBLISH")
            return self._handle_publish()
        else:
            # If we don't recognise the command, return an error straight away.
            print("_packet_haandle: didn't recognize command")
            return MQTT_ERR_PROTOCOL

    def _handle_pingresp(self):
        print("_handle_pingresp")

        # No longer waiting for a PINGRESP.
        self._ping_t = 0
        return 0

    def _handle_connack(self):
        print("_handle_connack") #needed

        if len(self._in_packet['packet']) != 2:
            return MQTT_ERR_PROTOCOL

        (flags, result) = struct.unpack("!BB", self._in_packet['packet'])
        # Do now support downgrade to MQTT v3.1

        if result == 0:
            self._state = mqtt_cs_connected
            print("_handle_connack: self._state =", self._state)

        if self.on_connect:
            flags_dict = dict()
            flags_dict['session present'] = flags & 0x01
            self.on_connect(self, self._userdata, flags_dict, result)

        if result == 0:
            rc = 0
            return rc
        elif result > 0 and result < 6:
            return MQTT_ERR_CONN_REFUSED
        else:
            return MQTT_ERR_PROTOCOL

    def _handle_suback(self):
        print("_handle_suback") #needed after _packet_handle
        pack_format = "!H" + str(len(self._in_packet['packet'])-2) + 's'
        (mid, packet) = struct.unpack(pack_format, self._in_packet['packet'])
        pack_format = "!" + "B"*len(packet)
        granted_qos = struct.unpack(pack_format, packet)

        if self.on_subscribe:
            self.on_subscribe(self, self._userdata, mid, granted_qos)

        return MQTT_ERR_SUCCESS

    def _handle_publish(self):
        rc = 0
        print("_handle_publish") #needed after packet_handle
        header = self._in_packet['command']
        #!H = ! means Network Byte Order, Size, and Alignment with H means unsigned short 2 bytes
        # For the 's' format character, the count is interpreted as the length of the bytes, not a repeat count like for the other format characters; for example, '10s' means a single 10-byte string
        # return  mtPacket(0b00110001, mtStr(topic), data)
        pack_format = "!H" + str(len(self._in_packet['packet'])-2) + 's'
        (slen, packet) = struct.unpack(pack_format, self._in_packet['packet'])
        pack_format = '!' + str(slen) + 's' + str(len(packet)-slen) + 's'
        topic, packet = struct.unpack(pack_format, packet) 

        # message.topic = b'test'
        msg = {} 
        msg['topic'] = topic.decode('utf-8') 
        msg['payload'] =  packet 
        msg['timestamp'] = time.time() 
        self.on_message(self, self._userdata, msg) 
        return 0
