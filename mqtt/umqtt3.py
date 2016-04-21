# Copyright (c) 2012-2014 Roger Light <roger@atchoo.org>
#
# This is a stripped down version of paho.mqtt intended for micropython
# All rights reserved. This program and the accompanying materials
# are made available under the terms of the Eclipse Public License v1.0
# and Eclipse Distribution License v1.0 which accompany this distribution.
#
# The Eclipse Public License is available at
#    http://www.eclipse.org/legal/epl-v10.html
# and the Eclipse Distribution License is available at
#   http://www.eclipse.org/org/documents/edl-v10.php.
#
# Contributors:
#    Roger Light - initial API and implementation

"""
This is an MQTT v3.1 client module. MQTT is a lightweight pub/sub messaging
protocol that is easy to implement and suitable for low powered devices.
"""
import select
import socket
import ustruct as struct
import utime as time

EAGAIN = const(11)

MQTTv31 = const(3)
MQTTv311 = const(4)

PROTOCOL_NAMEv31 = b"MQIsdp"
PROTOCOL_NAMEv311 = b"MQTT"

PROTOCOL_VERSION = const(3)

# Message types
CONNECT = const(0x10)
CONNACK = const(0x20)
PUBLISH = const(0x30)
SUBSCRIBE = const(0x80)
SUBACK = const(0x90)
DISCONNECT = const(0xE0)

# CONNACK codes
CONNACK_REFUSED_PROTOCOL_VERSION = 1

# Connection state
mqtt_cs_new = 0
mqtt_cs_connected = 1
mqtt_cs_disconnecting = 2
mqtt_cs_connect_async = 3

# Message state
mqtt_ms_invalid = 0
mqtt_ms_publish= 1
mqtt_ms_wait_for_puback = 2
mqtt_ms_wait_for_pubrec = 3
mqtt_ms_resend_pubrel = 4
mqtt_ms_wait_for_pubrel = 5
mqtt_ms_wait_for_pubcomp = 7
mqtt_ms_queued = 9

# Error values
MQTT_ERR_AGAIN = -1
MQTT_ERR_SUCCESS = 0
MQTT_ERR_PROTOCOL = 2
MQTT_ERR_NO_CONN = 4
MQTT_ERR_CONN_REFUSED = 5
MQTT_ERR_CONN_LOST = 7

#def topic_matches_sub(sub, topic):
#    """Check whether a topic matches a subscription.  """
#    print("topic_matches_sub")
#    result = True
#    multilevel_wildcard = False
#
#    slen = len(sub)
#    tlen = len(topic)
#
#    if slen > 0 and tlen > 0:
#        if (sub[0] == '$' and topic[0] != '$') or (topic[0] == '$' and sub[0] != '$'):
#            return False
#
#    spos = 0
#    tpos = 0
#
#    while spos < slen and tpos < tlen:
#        if sub[spos] == topic[tpos]:
#            if tpos == tlen-1:
#                # Check for e.g. foo matching foo/#
#                if spos == slen-3 and sub[spos+1] == '/' and sub[spos+2] == '#':
#                    result = True
#                    multilevel_wildcard = True
#                    break
#
#            spos += 1
#            tpos += 1
#
#            if tpos == tlen and spos == slen-1 and sub[spos] == '+':
#                spos += 1
#                result = True
#                break
#        else:
#            if sub[spos] == '+':
#                spos += 1
#                while tpos < tlen and topic[tpos] != '/':
#                    tpos += 1
#                if tpos == tlen and spos == slen:
#                    result = True
#                    break
#
#            elif sub[spos] == '#':
#                multilevel_wildcard = True
#                if spos+1 != slen:
#                    result = False
#                    break
#                else:
#                    result = True
#                    break
#
#            else:
#                result = False
#                break
#
#    if not multilevel_wildcard and (tpos < tlen or spos < slen):
#        result = False
#
#    return result

class MQTTMessage:
    """ This is a class that describes an incoming message."""
    def __init__(self):
        print("MQTTMessage Class")
        self.timestamp = 0
        self.state = mqtt_ms_invalid
        self.dup = False
        self.mid = 0
        self.topic = ""
        self.payload = None
        self.qos = 0
        self.retain = False

class Client:
    """MQTT version 3.1/3.1.1 client class."""
    def __init__(self, client_id="", clean_session=True, userdata=None, protocol=MQTTv31):
        if not clean_session and (client_id == "" or client_id is None):
            raise ValueError('A client id must be provided if clean session is False.')
        print("Client Class")
        self._protocol = protocol
        self._userdata = userdata
        self._sock = None
        self._keepalive = 60
        self._message_retry = 20
        self._last_retry_check = 0
        self._clean_session = clean_session
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
        self._out_packet = []
        self._current_out_packet = None
        self._last_msg_in = time.time()
        self._last_msg_out = time.time()
        self._ping_t = 0
        self._last_mid = 0
        self._state = mqtt_cs_new
        self._out_messages = []
        self._in_messages = []
        self._max_inflight_messages = 20
        self._inflight_messages = 0
        self.on_disconnect = None
        self.on_connect = None
        self.on_publish = None
        self.on_message = None
        self.on_message_filtered = []
        self.on_subscribe = None
        self.on_unsubscribe = None
        self._host = ""
        self._port = 1883
        self._bind_address = ""
        self._in_callback = False
        self._strict_protocol = False

    def __del__(self):
        print("__del__ Client")
        pass

    def connect(self, host, port=1883, keepalive=60, bind_address=""):
        """Connect to a remote broker.
        """
        print("connect")
        self.connect_async(host, port, keepalive, bind_address)
        return self.reconnect()

    def connect_async(self, host, port=1883, keepalive=60, bind_address=""):
        """Connect to a remote broker asynchronously. This is a non-blocking
        connect call that can be used with loop_start() to provide very quick
        start.
        """
        print("connect_async")
        if host is None or len(host) == 0:
            raise ValueError('Invalid host.')
        if port <= 0:
            raise ValueError('Invalid port number.')
        if keepalive < 0:
            raise ValueError('Keepalive must be >=0.')

        self._host = host
        self._port = port
        self._keepalive = keepalive
        self._bind_address = bind_address

        self._state = mqtt_cs_connect_async

    def reconnect(self):
        """Reconnect the client after a disconnect. Can only be called after
        connect()/connect_async()."""
        print("reconnect")
        if len(self._host) == 0:
            raise ValueError('Invalid host.')
        if self._port <= 0:
            raise ValueError('Invalid port number.')

        self._in_packet = {
            "command": 0,
            "have_remaining": 0,
            "remaining_count": [],
            "remaining_mult": 1,
            "remaining_length": 0,
            "packet": b"",
            "to_process": 0,
            "pos": 0}

        self._out_packet = []

        self._current_out_packet = None

        self._last_msg_in = time.time()
        self._last_msg_out = time.time()

        self._ping_t = 0
        self._state = mqtt_cs_new
        if self._sock:
            self._sock.close()
            self._sock = None
            print("self._sock == None")

        # Put messages in progress in a valid state.
        self._messages_reconnect_reset()

        sock = socket.create_connection((self._host, self._port), source_address=(self._bind_address, 0))
        self._sock = sock
        self._sock.setblocking(0)
        self.ep = select.epoll()
        self.fileno = self._sock.fileno()
        self.ep.register(self.fileno)

        print("self._sock =", self._sock)

        return self._send_connect(self._keepalive, self._clean_session)

    def loop(self, timeout=1):
        """Process network events.
        """
        print("loop")

        print("self._current_out_packet =", self._current_out_packet)
        print("self._out_packet =", self._out_packet)
        if self._current_out_packet is None and len(self._out_packet) > 0:
            self._current_out_packet = self._out_packet.pop(0)
        print("self._current_out_packet =", self._current_out_packet)

        events = self.ep.poll(timeout)
        print("events = ", events)
        for fileno, ev in events:
            if ev & select.EPOLLIN:
                rc = self.loop_read()
                if rc or (self._sock is None):
                    return rc

            if ev & select.EPOLLOUT and self._current_out_packet:
                rc = self.loop_write()
                if rc or (self._sock is None):
                    return rc

        return self.loop_misc()

    def subscribe(self, topic, qos=0):
        """Subscribe the client to one or more topics."""
        print("subscribe")
        topic_qos_list = None
        if isinstance(topic, str):
            if qos<0 or qos>2:
                raise ValueError('Invalid QoS level.')
            if topic is None or len(topic) == 0:
                raise ValueError('Invalid topic.')
            topic_qos_list = [(topic.encode('utf-8'), qos)]
        elif isinstance(topic, tuple):
            if topic[1]<0 or topic[1]>2:
                raise ValueError('Invalid QoS level.')
            if topic[0] is None or len(topic[0]) == 0 or not isinstance(topic[0], str):
                raise ValueError('Invalid topic.')
            topic_qos_list = [(topic[0].encode('utf-8'), topic[1])]
        elif isinstance(topic, list):
            topic_qos_list = []
            for t in topic:
                if t[1]<0 or t[1]>2:
                    raise ValueError('Invalid QoS level.')
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

        max_packets = len(self._out_messages) + len(self._in_messages)
        if max_packets < 1:
            max_packets = 1

        for i in range(0, max_packets):
            rc = self._packet_read() #only call to _packet_read
            if rc > 0:
                return self._loop_rc_handle(rc)
            elif rc == MQTT_ERR_AGAIN:
                return MQTT_ERR_SUCCESS
        return MQTT_ERR_SUCCESS

    def loop_write(self):
        """Process write network events.""" 
        print("loop_write")
        if self._sock is None:
            return MQTT_ERR_NO_CONN

        max_packets = len(self._out_packet) + 1
        if max_packets < 1:
            max_packets = 1

        for i in range(0, max_packets):
            rc = self._packet_write()
            if rc > 0:
                return self._loop_rc_handle(rc)
            elif rc == MQTT_ERR_AGAIN:
                return MQTT_ERR_SUCCESS
        return MQTT_ERR_SUCCESS

    def loop_misc(self):
        """Process miscellaneous network events.""" 
        print("loop_misc")
        if self._sock is None:
            return MQTT_ERR_NO_CONN

        now = time.time()
        self._check_keepalive()
        if self._last_retry_check+1 < now:
            # Only check once a second at most
            self._message_retry_check()
            self._last_retry_check = now

        if self._ping_t > 0 and now - self._ping_t >= self._keepalive:
            # client->ping_t != 0 means we are waiting for a pingresp.
            # This hasn't happened in the keepalive time so we should disconnect.
            if self._sock:
                self._sock.close()
                self._sock = None

            if self._state == mqtt_cs_disconnecting:
                rc = MQTT_ERR_SUCCESS
            else:
                rc = 1
            if self.on_disconnect:
                self._in_callback = True
                self.on_disconnect(self, self._userdata, rc)
                self._in_callback = False
            return MQTT_ERR_CONN_LOST
        return MQTT_ERR_SUCCESS

    # ============================================================
    # Private functions
    # ============================================================

    #def _loop_rc_handle(self, rc):
    #    print("_loop_rc_handle")
    #    if rc:
    #        if self._sock:
    #            self._sock.close()
    #            self._sock = None

    #        if self._state == mqtt_cs_disconnecting:
    #            rc = MQTT_ERR_SUCCESS
    #        if self.on_disconnect:
    #            self._in_callback = True
    #            self.on_disconnect(self, self._userdata, rc)
    #            self._in_callback = False

    #    return rc

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

        self._last_msg_in = time.time()
        return rc

    def _packet_write(self):
        print("_packet_write")

        while self._current_out_packet:
            packet = self._current_out_packet

            try:
                write_length = self._sock.send(packet['packet'][packet['pos']:])
            except AttributeError:
                return MQTT_ERR_SUCCESS
            except socket.error as err:
                if err.errno == EAGAIN:
                    return MQTT_ERR_AGAIN
                print(err)
                return 1

            if write_length > 0:
                packet['to_process'] = packet['to_process'] - write_length
                packet['pos'] = packet['pos'] + write_length

                if packet['to_process'] == 0:
                    if (packet['command'] & 0xF0) == PUBLISH and packet['qos'] == 0:
                        if self.on_publish:
                            self._in_callback = True
                            self.on_publish(self, self._userdata, packet['mid'])
                            self._in_callback = False

                    if (packet['command'] & 0xF0) == DISCONNECT:
                        self._last_msg_out = time.time()
                        if self.on_disconnect:
                            self._in_callback = True
                            self.on_disconnect(self, self._userdata, 0)
                            self._in_callback = False

                        if self._sock:
                            self._sock.close()
                            self._sock = None
                        return MQTT_ERR_SUCCESS

                    if len(self._out_packet) > 0:
                        self._current_out_packet = self._out_packet.pop(0)
                    else:
                        self._current_out_packet = None
            else:
                break

        self._last_msg_out = time.time()
        print("self._current_out_packet =", self._current_out_packet)
        return MQTT_ERR_SUCCESS

    def _check_keepalive(self):
        print("_check_keepalive")
        now = time.time()
        last_msg_out = self._last_msg_out
        last_msg_in = self._last_msg_in
        if (self._sock is not None) and (now - last_msg_out >= self._keepalive or now - last_msg_in >= self._keepalive):
            if self._state == mqtt_cs_connected and self._ping_t == 0:
                self._send_pingreq()
                self._last_msg_out = now
                self._last_msg_in = now
            else:
                if self._sock:
                    self._sock.close()
                    self._sock = None

                if self._state == mqtt_cs_disconnecting:
                    rc = MQTT_ERR_SUCCESS
                else:
                    rc = 1
                if self.on_disconnect:
                    self._in_callback = True
                    self.on_disconnect(self, self._userdata, rc)
                    self._in_callback = False

    def _mid_generate(self):
        print("_mid_generate")
        self._last_mid = self._last_mid + 1
        if self._last_mid == 65536:
            self._last_mid = 1
        return self._last_mid

    def _pack_remaining_length(self, packet, remaining_length):
        print("_pack_remaining_length")
        remaining_bytes = []
        while True:
            byte = remaining_length % 128
            remaining_length = remaining_length // 128
            # If there are more digits to encode, set the top bit of this digit
            if remaining_length > 0:
                byte = byte | 0x80

            remaining_bytes.append(byte)
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

    #def _send_publish(self, mid, topic, payload=None, qos=0, retain=False, dup=False):
    #    print("_send_publish")
    #    if self._sock is None:
    #        return MQTT_ERR_NO_CONN

    #    utopic = topic.encode('utf-8')
    #    command = PUBLISH # | ((dup&0x1)<<3) | (qos<<1) | retain
    #    packet = bytearray()
    #    packet.extend(struct.pack("!B", command))
    #    if payload is None:
    #        remaining_length = 2+len(utopic)
    #    else:
    #        if isinstance(payload, str):
    #            upayload = payload.encode('utf-8')
    #            payloadlen = len(upayload)
    #        elif isinstance(payload, bytearray):
    #            payloadlen = len(payload)
    #        elif isinstance(payload, unicode):
    #            upayload = payload.encode('utf-8')
    #            payloadlen = len(upayload)

    #        remaining_length = 2+len(utopic) + payloadlen

    #    #if qos > 0:
    #        # For message id
    #        #remaining_length = remaining_length + 2

    #    self._pack_remaining_length(packet, remaining_length)
    #    self._pack_str16(packet, topic)

    #    #if qos > 0:
    #        # For message id
    #        #packet.extend(struct.pack("!H", mid))

    #    if payload is not None:
    #        if isinstance(payload, str):
    #            pack_format = str(payloadlen) + "s"
    #            packet.extend(struct.pack(pack_format, upayload))
    #        elif isinstance(payload, bytearray):
    #            packet.extend(payload)
    #        elif isinstance(payload, unicode):
    #            pack_format = str(payloadlen) + "s"
    #            packet.extend(struct.pack(pack_format, upayload))
    #        else:
    #            raise TypeError('payload must be a string, unicode or a bytearray.')

    #    return self._packet_queue(PUBLISH, packet, mid, qos)

    def _send_connect(self, keepalive, clean_session):
        print("_send_connect")
        if self._protocol == MQTTv31:
            protocol = PROTOCOL_NAMEv31
            proto_ver = 3
        else:
            protocol = PROTOCOL_NAMEv311
            proto_ver = 4
        remaining_length = 2+len(protocol) + 1+1+2 + 2+len(self._client_id)
        connect_flags = 0
        if clean_session:
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
        packet.extend(struct.pack("!H"+str(len(protocol))+"sBBH", len(protocol), protocol, proto_ver, connect_flags, keepalive))

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
        for t in topics:
            remaining_length = remaining_length + 2+len(t[0])+1

        command = SUBSCRIBE | (dup<<3) | (1<<1)
        packet = bytearray()
        packet.extend(struct.pack("!B", command))
        self._pack_remaining_length(packet, remaining_length)
        local_mid = self._mid_generate()
        packet.extend(struct.pack("!H", local_mid))
        for t in topics:
            self._pack_str16(packet, t[0])
            packet.extend(struct.pack("B", t[1]))
        return (self._packet_queue(command, packet, local_mid, 1), local_mid)

    def _message_retry_check_actual(self, messages):
        print("_message_retry_check_actual") #needed
        now = time.time()
        for m in messages:
            if m.timestamp + self._message_retry < now:
                if m.state == mqtt_ms_wait_for_puback or m.state == mqtt_ms_wait_for_pubrec:
                    m.timestamp = now
                    m.dup = True
                    self._send_publish(m.mid, m.topic, m.payload, m.qos, m.retain, m.dup)
                elif m.state == mqtt_ms_wait_for_pubrel:
                    m.timestamp = now
                    m.dup = True
                    self._send_pubrec(m.mid)
                elif m.state == mqtt_ms_wait_for_pubcomp:
                    m.timestamp = now
                    m.dup = True
                    self._send_pubrel(m.mid, True)

    def _message_retry_check(self):
        print("_message_retry_check") #needed
        self._message_retry_check_actual(self._out_messages)
        self._message_retry_check_actual(self._in_messages)

    def _messages_reconnect_reset_out(self):
        print("_messages_reconnect_reset_out") #needed
        self._inflight_messages = 0
        for m in self._out_messages:
            m.timestamp = 0
            if self._max_inflight_messages == 0 or self._inflight_messages < self._max_inflight_messages:
                if m.qos == 0:
                    m.state = mqtt_ms_publish
                elif m.qos == 1:
                    #self._inflight_messages = self._inflight_messages + 1
                    if m.state == mqtt_ms_wait_for_puback:
                        m.dup = True
                    m.state = mqtt_ms_publish
                elif m.qos == 2:
                    #self._inflight_messages = self._inflight_messages + 1
                    if m.state == mqtt_ms_wait_for_pubcomp:
                        m.state = mqtt_ms_resend_pubrel
                        m.dup = True
                    else:
                        if m.state == mqtt_ms_wait_for_pubrec:
                            m.dup = True
                        m.state = mqtt_ms_publish
            else:
                m.state = mqtt_ms_queued

    def _messages_reconnect_reset_in(self):
        print("_messages_reconnect_reset_in") #needed
        for m in self._in_messages:
            m.timestamp = 0
            if m.qos != 2:
                self._in_messages.pop(self._in_messages.index(m))
            else:
                # Preserve current state
                pass

    def _messages_reconnect_reset(self):
        print("_messages_reconnect_reset") #needed
        self._messages_reconnect_reset_out()
        self._messages_reconnect_reset_in()

    def _packet_queue(self, command, packet, mid, qos):
        print("_packet_queue") #needed
        mpkt = dict(
            command = command,
            mid = mid,
            qos = qos,
            pos = 0,
            to_process = len(packet),
            packet = packet)

        self._out_packet.append(mpkt)
        if self._current_out_packet is None and len(self._out_packet) > 0:
            self._current_out_packet = self._out_packet.pop(0)

        print("self._out_packet =", self._out_packet)
        if not self._in_callback: 
            return self.loop_write()
        else:
            return MQTT_ERR_SUCCESS

    def _packet_handle(self):
        print("_packet_handle")
        cmd = self._in_packet['command']&0xF0
        if cmd == PUBLISH: #appear to need PUBLISH
            return self._handle_publish()
        elif cmd == CONNACK:
            return self._handle_connack()
        elif cmd == SUBACK:
            return self._handle_suback()
        else:
            # If we don't recognise the command, return an error straight away.
            return MQTT_ERR_PROTOCOL

    def _handle_connack(self):
        print("_handle_connack") #needed
        if self._strict_protocol:
            if self._in_packet['remaining_length'] != 2:
                return MQTT_ERR_PROTOCOL

        if len(self._in_packet['packet']) != 2:
            return MQTT_ERR_PROTOCOL

        (flags, result) = struct.unpack("!BB", self._in_packet['packet'])
        if result == CONNACK_REFUSED_PROTOCOL_VERSION and self._protocol == MQTTv311:
            # Downgrade to MQTT v3.1
            self._protocol = MQTTv31
            return self.reconnect()

        if result == 0:
            self._state = mqtt_cs_connected

        if self.on_connect:
            self._in_callback = True

            flags_dict = dict()
            flags_dict['session present'] = flags & 0x01
            self.on_connect(self, self._userdata, flags_dict, result)
            self._in_callback = False

        if result == 0:
            rc = 0
            for m in self._out_messages:
                m.timestamp = time.time()
                if m.state == mqtt_ms_queued:
                    self.loop_write() # Process outgoing messages that have just been queued up
                    return MQTT_ERR_SUCCESS

                if m.qos == 0:
                    self._in_callback = True # Don't call loop_write after _send_publish()
                    rc = self._send_publish(m.mid, m.topic, m.payload, m.qos, m.retain, m.dup)
                    self._in_callback = False
                    if rc != 0:
                        return rc
                elif m.qos == 1:
                    if m.state == mqtt_ms_publish:
                        self._inflight_messages = self._inflight_messages + 1
                        m.state = mqtt_ms_wait_for_puback
                        self._in_callback = True # Don't call loop_write after _send_publish()
                        rc = self._send_publish(m.mid, m.topic, m.payload, m.qos, m.retain, m.dup)
                        self._in_callback = False
                        if rc != 0:
                            return rc
                elif m.qos == 2:
                    if m.state == mqtt_ms_publish:
                        self._inflight_messages = self._inflight_messages + 1
                        m.state = mqtt_ms_wait_for_pubrec
                        self._in_callback = True # Don't call loop_write after _send_publish()
                        rc = self._send_publish(m.mid, m.topic, m.payload, m.qos, m.retain, m.dup)
                        self._in_callback = False
                        if rc != 0:
                            return rc
                    elif m.state == mqtt_ms_resend_pubrel:
                        self._inflight_messages = self._inflight_messages + 1
                        m.state = mqtt_ms_wait_for_pubcomp
                        self._in_callback = True # Don't call loop_write after _send_pubrel()
                        rc = self._send_pubrel(m.mid, m.dup)
                        self._in_callback = False
                        if rc != 0:
                            return rc
                self.loop_write() # Process outgoing messages that have just been queued up
            return rc
        elif result > 0 and result < 6:
            return MQTT_ERR_CONN_REFUSED
        else:
            return MQTT_ERR_PROTOCOL

    #def _handle_suback(self):
    #    print("_handle_suback") #needed after _packet_handle
    #    pack_format = "!H" + str(len(self._in_packet['packet'])-2) + 's'
    #    (mid, packet) = struct.unpack(pack_format, self._in_packet['packet'])
    #    pack_format = "!" + "B"*len(packet)
    #    granted_qos = struct.unpack(pack_format, packet)

    #    if self.on_subscribe:
    #        self._in_callback = True
    #        self.on_subscribe(self, self._userdata, mid, granted_qos)
    #        self._in_callback = False

    #    return MQTT_ERR_SUCCESS

    def _handle_publish(self):
        rc = 0
        print("_handle_publish") #needed after packet_handle
        header = self._in_packet['command']
        message = MQTTMessage()
        message.dup = (header & 0x08)>>3
        message.qos = (header & 0x06)>>1
        message.retain = (header & 0x01)

        pack_format = "!H" + str(len(self._in_packet['packet'])-2) + 's'
        (slen, packet) = struct.unpack(pack_format, self._in_packet['packet'])
        pack_format = '!' + str(slen) + 's' + str(len(packet)-slen) + 's'
        (message.topic, packet) = struct.unpack(pack_format, packet)

        if len(message.topic) == 0:
            return MQTT_ERR_PROTOCOL

        message.topic = message.topic.decode('utf-8')

        #if message.qos > 0:
        #    pack_format = "!H" + str(len(packet)-2) + 's'
        #    (message.mid, packet) = struct.unpack(pack_format, packet)

        message.payload = packet

        message.timestamp = time.time()
        if message.qos == 0:
            self._handle_on_message(message)
            return MQTT_ERR_SUCCESS
        #elif message.qos == 1:
        #    rc = self._send_puback(message.mid)
        #    self._handle_on_message(message)
        #    return rc
        #elif message.qos == 2:
        #    rc = self._send_pubrec(message.mid)
        #    message.state = mqtt_ms_wait_for_pubrel
        #    self._in_message_mutex.acquire()
        #    self._in_messages.append(message)
        #    self._in_message_mutex.release()
        #    return rc
        else:
            return MQTT_ERR_PROTOCOL

    def _handle_on_message(self, message):
        print("_handle_on_message")
        matched = False
        for t in self.on_message_filtered:
            if topic_matches_sub(t[0], message.topic):
                self._in_callback = True
                t[1](self, self._userdata, message)
                self._in_callback = False
                matched = True

        if matched == False and self.on_message:
            self._in_callback = True
            self.on_message(self, self._userdata, message)
            self._in_callback = False
