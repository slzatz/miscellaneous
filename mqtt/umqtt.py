# Copyright (c) 2012-2014 Roger Light <roger@atchoo.org>
#
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
import errno
import sys
try:
    import select
    #import usocket as socket
    import socket
    import ustruct as struct
    import utime as time
except:
    import struct
    import time
#FIXME
if sys.platform != 'linux':
    EAGAIN = errno.WSAEWOULDBLOCK
else:
    EAGAIN = errno.EAGAIN

MQTTv31 = 3
MQTTv311 = 4

PROTOCOL_NAMEv31 = b"MQIsdp"
PROTOCOL_NAMEv311 = b"MQTT"

PROTOCOL_VERSION = 3

# Message types
CONNECT = 0x10
CONNACK = 0x20
PUBLISH = 0x30
PUBACK = 0x40
PUBREC = 0x50
PUBREL = 0x60
PUBCOMP = 0x70
SUBSCRIBE = 0x80
SUBACK = 0x90
UNSUBSCRIBE = 0xA0
UNSUBACK = 0xB0
PINGREQ = 0xC0
PINGRESP = 0xD0
DISCONNECT = 0xE0

# Log levels
MQTT_LOG_INFO = 0x01
MQTT_LOG_NOTICE = 0x02
MQTT_LOG_WARNING = 0x04
MQTT_LOG_ERR = 0x08
MQTT_LOG_DEBUG = 0x10

# CONNACK codes
CONNACK_ACCEPTED = 0
CONNACK_REFUSED_PROTOCOL_VERSION = 1
CONNACK_REFUSED_IDENTIFIER_REJECTED = 2
CONNACK_REFUSED_SERVER_UNAVAILABLE = 3
CONNACK_REFUSED_BAD_USERNAME_PASSWORD = 4
CONNACK_REFUSED_NOT_AUTHORIZED = 5

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
mqtt_ms_resend_pubcomp = 6
mqtt_ms_wait_for_pubcomp = 7
mqtt_ms_send_pubrec = 8
mqtt_ms_queued = 9

# Error values
MQTT_ERR_AGAIN = -1
MQTT_ERR_SUCCESS = 0
MQTT_ERR_NOMEM = 1
MQTT_ERR_PROTOCOL = 2
MQTT_ERR_INVAL = 3
MQTT_ERR_NO_CONN = 4
MQTT_ERR_CONN_REFUSED = 5
MQTT_ERR_NOT_FOUND = 6
MQTT_ERR_CONN_LOST = 7
MQTT_ERR_TLS = 8
MQTT_ERR_PAYLOAD_SIZE = 9
MQTT_ERR_NOT_SUPPORTED = 10
MQTT_ERR_AUTH = 11
MQTT_ERR_ACL_DENIED = 12
MQTT_ERR_UNKNOWN = 13
MQTT_ERR_ERRNO = 14

sockpair_data = b"0"

def error_string(mqtt_errno):
    """Return the error string associated with an mqtt error number."""
    if mqtt_errno == MQTT_ERR_SUCCESS:
        return "No error."
    elif mqtt_errno == MQTT_ERR_NOMEM:
        return "Out of memory."
    elif mqtt_errno == MQTT_ERR_PROTOCOL:
        return "A network protocol error occurred when communicating with the broker."
    elif mqtt_errno == MQTT_ERR_INVAL:
        return "Invalid function arguments provided."
    elif mqtt_errno == MQTT_ERR_NO_CONN:
        return "The client is not currently connected."
    elif mqtt_errno == MQTT_ERR_CONN_REFUSED:
        return "The connection was refused."
    elif mqtt_errno == MQTT_ERR_NOT_FOUND:
        return "Message not found (internal error)."
    elif mqtt_errno == MQTT_ERR_CONN_LOST:
        return "The connection was lost."
    elif mqtt_errno == MQTT_ERR_TLS:
        return "A TLS error occurred."
    elif mqtt_errno == MQTT_ERR_PAYLOAD_SIZE:
        return "Payload too large."
    elif mqtt_errno == MQTT_ERR_NOT_SUPPORTED:
        return "This feature is not supported."
    elif mqtt_errno == MQTT_ERR_AUTH:
        return "Authorisation failed."
    elif mqtt_errno == MQTT_ERR_ACL_DENIED:
        return "Access denied by ACL."
    elif mqtt_errno == MQTT_ERR_UNKNOWN:
        return "Unknown error."
    elif mqtt_errno == MQTT_ERR_ERRNO:
        return "Error defined by errno."
    else:
        return "Unknown error."


def connack_string(connack_code):
    """Return the string associated with a CONNACK result."""
    if connack_code == 0:
        return "Connection Accepted."
    elif connack_code == 1:
        return "Connection Refused: unacceptable protocol version."
    elif connack_code == 2:
        return "Connection Refused: identifier rejected."
    elif connack_code == 3:
        return "Connection Refused: broker unavailable."
    elif connack_code == 4:
        return "Connection Refused: bad user name or password."
    elif connack_code == 5:
        return "Connection Refused: not authorised."
    else:
        return "Connection Refused: unknown reason."


def topic_matches_sub(sub, topic):
    """Check whether a topic matches a subscription.

    For example:

    foo/bar would match the subscription foo/# or +/bar
    non/matching would not match the subscription non/+/+
    """
    result = True
    multilevel_wildcard = False

    slen = len(sub)
    tlen = len(topic)

    if slen > 0 and tlen > 0:
        if (sub[0] == '$' and topic[0] != '$') or (topic[0] == '$' and sub[0] != '$'):
            return False

    spos = 0
    tpos = 0

    while spos < slen and tpos < tlen:
        if sub[spos] == topic[tpos]:
            if tpos == tlen-1:
                # Check for e.g. foo matching foo/#
                if spos == slen-3 and sub[spos+1] == '/' and sub[spos+2] == '#':
                    result = True
                    multilevel_wildcard = True
                    break

            spos += 1
            tpos += 1

            if tpos == tlen and spos == slen-1 and sub[spos] == '+':
                spos += 1
                result = True
                break
        else:
            if sub[spos] == '+':
                spos += 1
                while tpos < tlen and topic[tpos] != '/':
                    tpos += 1
                if tpos == tlen and spos == slen:
                    result = True
                    break

            elif sub[spos] == '#':
                multilevel_wildcard = True
                if spos+1 != slen:
                    result = False
                    break
                else:
                    result = True
                    break

            else:
                result = False
                break

    if not multilevel_wildcard and (tpos < tlen or spos < slen):
        result = False

    return result

class MQTTMessage:
    """ This is a class that describes an incoming message. It is passed to the
    on_message callback as the message parameter.

    Members:

    topic : String. topic that the message was published on.
    payload : String/bytes the message payload.
    qos : Integer. The message Quality of Service 0, 1 or 2.
    retain : Boolean. If true, the message is a retained message and not fresh.
    mid : Integer. The message id.
    """
    def __init__(self):
        self.timestamp = 0
        self.state = mqtt_ms_invalid
        self.dup = False
        self.mid = 0
        self.topic = ""
        self.payload = None
        self.qos = 0
        self.retain = False

class Client(object):
    """MQTT version 3.1/3.1.1 client class.

    This is the main class for use communicating with an MQTT broker.

    General usage flow:

    * Use connect()/connect_async() to connect to a broker
    * Call loop() frequently to maintain network traffic flow with the broker
    * Or use loop_start() to set a thread running to call loop() for you.
    * Or use loop_forever() to handle calling loop() for you in a blocking
    * function.
    * Use subscribe() to subscribe to a topic and receive messages
    * Use publish() to send messages
    * Use disconnect() to disconnect from the broker

    Data returned from the broker is made available with the use of callback
    functions as described below.

    Callbacks
    =========

    A number of callback functions are available to receive data back from the
    broker. To use a callback, define a function and then assign it to the
    client:

    def on_connect(client, userdata, flags, rc):
        print("Connection returned " + str(rc))

    client.on_connect = on_connect

    All of the callbacks as described below have a "client" and an "userdata"
    argument. "client" is the Client instance that is calling the callback.
    "userdata" is user data of any type and can be set when creating a new client
    instance or with user_data_set(userdata).

    The callbacks:

    on_connect(client, userdata, flags, rc): called when the broker responds to our connection
      request.
      flags is a dict that contains response flags from the broker:
        flags['session present'] - this flag is useful for clients that are
            using clean session set to 0 only. If a client with clean
            session=0, that reconnects to a broker that it has previously
            connected to, this flag indicates whether the broker still has the
            session information for the client. If 1, the session still exists.
      The value of rc determines success or not:
        0: Connection successful
        1: Connection refused - incorrect protocol version
        2: Connection refused - invalid client identifier
        3: Connection refused - server unavailable
        4: Connection refused - bad username or password
        5: Connection refused - not authorised
        6-255: Currently unused.

    on_disconnect(client, userdata, rc): called when the client disconnects from the broker.
      The rc parameter indicates the disconnection state. If MQTT_ERR_SUCCESS
      (0), the callback was called in response to a disconnect() call. If any
      other value the disconnection was unexpected, such as might be caused by
      a network error.

    on_message(client, userdata, message): called when a message has been received on a
      topic that the client subscribes to. The message variable is a
      MQTTMessage that describes all of the message parameters.

    on_publish(client, userdata, mid): called when a message that was to be sent using the
      publish() call has completed transmission to the broker. For messages
      with QoS levels 1 and 2, this means that the appropriate handshakes have
      completed. For QoS 0, this simply means that the message has left the
      client. The mid variable matches the mid variable returned from the
      corresponding publish() call, to allow outgoing messages to be tracked.
      This callback is important because even if the publish() call returns
      success, it does not always mean that the message has been sent.

    on_subscribe(client, userdata, mid, granted_qos): called when the broker responds to a
      subscribe request. The mid variable matches the mid variable returned
      from the corresponding subscribe() call. The granted_qos variable is a
      list of integers that give the QoS level the broker has granted for each
      of the different subscription requests.

    on_unsubscribe(client, userdata, mid): called when the broker responds to an unsubscribe
      request. The mid variable matches the mid variable returned from the
      corresponding unsubscribe() call.

    on_log(client, userdata, level, buf): called when the client has log information. Define
      to allow debugging. The level variable gives the severity of the message
      and will be one of MQTT_LOG_INFO, MQTT_LOG_NOTICE, MQTT_LOG_WARNING,
      MQTT_LOG_ERR, and MQTT_LOG_DEBUG. The message itself is in buf.

    """
    def __init__(self, client_id="", clean_session=True, userdata=None, protocol=MQTTv31):
        """client_id is the unique client id string used when connecting to the
        broker. If client_id is zero length or None, then one will be randomly
        generated. In this case, clean_session must be True. If this is not the
        case a ValueError will be raised.

        clean_session is a boolean that determines the client type. If True,
        the broker will remove all information about this client when it
        disconnects. If False, the client is a persistent client and
        subscription information and queued messages will be retained when the
        client disconnects.
        Note that a client will never discard its own outgoing messages on
        disconnect. Calling connect() or reconnect() will cause the messages to
        be resent.  Use reinitialise() to reset a client to its original state.

        userdata is user defined data of any type that is passed as the "userdata"
        parameter to callbacks. It may be updated at a later point with the
        user_data_set() function.

        The protocol argument allows explicit setting of the MQTT version to
        use for this client. Can be paho.mqtt.client.MQTTv311 (v3.1.1) or
        paho.mqtt.client.MQTTv31 (v3.1), with the default being v3.1. If the
        broker reports that the client connected with an invalid protocol
        version, the client will automatically attempt to reconnect using v3.1
        instead.
        """
        if not clean_session and (client_id == "" or client_id is None):
            raise ValueError('A client id must be provided if clean session is False.')

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
        self._will = False
        self._will_topic = ""
        self._will_payload = None
        self._will_qos = 0
        self._will_retain = False
        self.on_disconnect = None
        self.on_connect = None
        self.on_publish = None
        self.on_message = None
        self.on_message_filtered = []
        self.on_subscribe = None
        self.on_unsubscribe = None
        self.on_log = None #None
        self._host = ""
        self._port = 1883
        self._bind_address = ""
        self._in_callback = False
        self._strict_protocol = False

    def __del__(self):
        pass

    def reinitialise(self, client_id="", clean_session=True, userdata=None):
        if self._sock:
            self._sock.close()
            self._sock = None

        self.__init__(client_id, clean_session, userdata)

    def connect(self, host, port=1883, keepalive=60, bind_address=""):
        """Connect to a remote broker.

        host is the hostname or IP address of the remote broker.
        port is the network port of the server host to connect to. Defaults to
        1883. Note that the default port for MQTT over SSL/TLS is 8883 so if you
        are using tls_set() the port may need providing.
        keepalive: Maximum period in seconds between communications with the
        broker. If no other messages are being exchanged, this controls the
        rate at which the client will send ping messages to the broker.
        """
        print("connect")
        self.connect_async(host, port, keepalive, bind_address)
        return self.reconnect()

    def connect_async(self, host, port=1883, keepalive=60, bind_address=""):
        """Connect to a remote broker asynchronously. This is a non-blocking
        connect call that can be used with loop_start() to provide very quick
        start.

        host is the hostname or IP address of the remote broker.
        port is the network port of the server host to connect to. Defaults to
        1883. Note that the default port for MQTT over SSL/TLS is 8883 so if you
        are using tls_set() the port may need providing.
        keepalive: Maximum period in seconds between communications with the
        broker. If no other messages are being exchanged, this controls the
        rate at which the client will send ping messages to the broker.
        """
        print("connect_async")
        if host is None or len(host) == 0:
            raise ValueError('Invalid host.')
        if port <= 0:
            raise ValueError('Invalid port number.')
        if keepalive < 0:
            raise ValueError('Keepalive must be >=0.')
        if bind_address != "" and bind_address is not None:
            if (sys.version_info[0] == 2 and sys.version_info[1] < 7) or (sys.version_info[0] == 3 and sys.version_info[1] < 2):
                raise ValueError('bind_address requires Python 2.7 or 3.2.')

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

        print("self._sock =", self._sock)

        return self._send_connect(self._keepalive, self._clean_session)

    def xxxloop(self, timeout=1.0, max_packets=1):
        """Process network events.

        This function must be called regularly to ensure communication with the
        broker is carried out. It calls select() on the network socket to wait
        for network events. If incoming data is present it will then be
        processed. Outgoing commands, from e.g. publish(), are normally sent
        immediately that their function is called, but this is not always
        possible. loop() will also attempt to send any remaining outgoing
        messages, which also includes commands that are part of the flow for
        messages with QoS>0.

        timeout: The time in seconds to wait for incoming/outgoing network
          traffic before timing out and returning.
        max_packets: Not currently used.

        Returns MQTT_ERR_SUCCESS on success.
        Returns >0 on error.

        A ValueError will be raised if timeout < 0"""
        print("loop")
        if timeout < 0.0:
            raise ValueError('Invalid timeout.')

        print("self._current_out_packet =", self._current_out_packet)
        print("self._out_packet =", self._out_packet)
        if self._current_out_packet is None and len(self._out_packet) > 0:
            self._current_out_packet = self._out_packet.pop(0)
        print("self._current_out_packet =", self._current_out_packet)
        if self._current_out_packet:
            wlist = [self.socket()]
        else:
            wlist = []

        # sockpairR is used to break out of select() before the timeout, on a
        # call to publish() etc.
        #rlist = [self.socket(), self._sockpairR]
        rlist = [self.socket()]
        print("rlist =",rlist)
        print("wlist =", wlist)
        try:
            socklist = select.select(rlist, wlist, [], timeout)
        except TypeError:
            # Socket isn't correct type, in likelihood connection is lost
            return MQTT_ERR_CONN_LOST
        except ValueError:
            # Can occur if we just reconnected but rlist/wlist contain a -1 for
            # some reason.
            return MQTT_ERR_CONN_LOST
        except:
            return MQTT_ERR_UNKNOWN
        print("socklist =",socklist)
        if self.socket() in socklist[0]:
            rc = self.loop_read(max_packets)
            if rc or (self._sock is None):
                return rc

        if self.socket() in socklist[1]:
            rc = self.loop_write(max_packets)
            if rc or (self._sock is None):
                return rc
        return self.loop_misc()

    def loop(self, timeout=1.0, max_packets=1):
        """Process network events.

        This function must be called regularly to ensure communication with the
        broker is carried out. It calls select() on the network socket to wait
        for network events. If incoming data is present it will then be
        processed. Outgoing commands, from e.g. publish(), are normally sent
        immediately that their function is called, but this is not always
        possible. loop() will also attempt to send any remaining outgoing
        messages, which also includes commands that are part of the flow for
        messages with QoS>0.

        timeout: The time in seconds to wait for incoming/outgoing network
          traffic before timing out and returning.
        max_packets: Not currently used.

        Returns MQTT_ERR_SUCCESS on success.
        Returns >0 on error.

        A ValueError will be raised if timeout < 0"""
        print("loop")
        if timeout < 0.0:
            raise ValueError('Invalid timeout.')

        print("self._current_out_packet =", self._current_out_packet)
        print("self._out_packet =", self._out_packet)
        if self._current_out_packet is None and len(self._out_packet) > 0:
            self._current_out_packet = self._out_packet.pop(0)
        print("self._current_out_packet =", self._current_out_packet)
        if self._current_out_packet:
            wlist = [self.socket()]
        else:
            wlist = []

        # sockpairR is used to break out of select() before the timeout, on a
        # call to publish() etc.
        #rlist = [self.socket(), self._sockpairR]
        #rlist = [self.socket()]
        #print("rlist =",rlist)
        #print("wlist =", wlist)

        ep = select.epoll()
        print(self.socket())
        fileno = self.socket().fileno()
        #print("fileno =", self.socket().fileno())
        #ep.register(self.socket().fileno(), select.EPOLLIN)
        ep.register(fileno, select.EPOLLIN)
        res = ep.poll(self.socket().fileno())
        print("res = ", res)
        f,x = res[0] if res else (0,0)
        if f==fileno:
            rc = self.loop_read(max_packets)
            if rc or (self._sock is None):
                return rc

        ep = select.epoll()
        print(self.socket())
        fileno = self.socket().fileno()
        #print("fileno =", self.socket().fileno())
        #ep.register(self.socket().fileno(), select.EPOLLIN)
        ep.register(fileno, select.EPOLLOUT)
        res = ep.poll(self.socket().fileno())
        print("res = ", res)
        f,x = res[0] if res else (0,0)
        if f==fileno:
            rc = self.loop_write(max_packets)
            if rc or (self._sock is None):
                return rc
        #except:
            #return MQTT_ERR_UNKNOWN
        #print("socklist =",socklist)
        #if self.socket() in socklist[0]:
        #    rc = self.loop_read(max_packets)
        #    if rc or (self._sock is None):
        #        return rc

        #if self.socket() in socklist[1]:
        #    rc = self.loop_write(max_packets)
        #    if rc or (self._sock is None):
        #        return rc
        return self.loop_misc()

#    def publish(self, topic, payload=None, qos=0, retain=False):
#        """Publish a message on a topic.
#
#        This causes a message to be sent to the broker and subsequently from
#        the broker to any clients subscribing to matching topics.
#
#        topic: The topic that the message should be published on.
#        payload: The actual message to send. If not given, or set to None a
#        zero length message will be used. Passing an int or float will result
#        in the payload being converted to a string representing that number. If
#        you wish to send a true int/float, use struct.pack() to create the
#        payload you require.
#        qos: The quality of service level to use.
#        retain: If set to true, the message will be set as the "last known
#        good"/retained message for the topic.
#
#        Returns a tuple (result, mid), where result is MQTT_ERR_SUCCESS to
#        indicate success or MQTT_ERR_NO_CONN if the client is not currently
#        connected.  mid is the message ID for the publish request. The mid
#        value can be used to track the publish request by checking against the
#        mid argument in the on_publish() callback if it is defined.
#
#        A ValueError will be raised if topic is None, has zero length or is
#        invalid (contains a wildcard), if qos is not one of 0, 1 or 2, or if
#        the length of the payload is greater than 268435455 bytes."""
#        if topic is None or len(topic) == 0:
#            raise ValueError('Invalid topic.')
#        if qos<0 or qos>2:
#            raise ValueError('Invalid QoS level.')
#        if isinstance(payload, str) or isinstance(payload, bytearray):
#            local_payload = payload
#        elif sys.version_info[0] < 3 and isinstance(payload, unicode):
#            local_payload = payload
#        elif isinstance(payload, int) or isinstance(payload, float):
#            local_payload = str(payload)
#        elif payload is None:
#            local_payload = None
#        else:
#            raise TypeError('payload must be a string, bytearray, int, float or None.')
#
#        if local_payload is not None and len(local_payload) > 268435455:
#            raise ValueError('Payload too large.')
#
#        if self._topic_wildcard_len_check(topic) != MQTT_ERR_SUCCESS:
#            raise ValueError('Publish topic cannot contain wildcards.')
#
#        local_mid = self._mid_generate()
#
#        if qos == 0:
#            rc = self._send_publish(local_mid, topic, local_payload, qos, retain, False)
#            return (rc, local_mid)
#        else:
#            message = MQTTMessage()
#            message.timestamp = time.time()
#
#            message.mid = local_mid
#            message.topic = topic
#            if local_payload is None or len(local_payload) == 0:
#                message.payload = None
#            else:
#                message.payload = local_payload
#
#            message.qos = qos
#            message.retain = retain
#            message.dup = False
#
#            self._out_message_mutex.acquire()
#            self._out_messages.append(message)
#            if self._max_inflight_messages == 0 or self._inflight_messages < self._max_inflight_messages:
#                self._inflight_messages = self._inflight_messages+1
#                if qos == 1:
#                    message.state = mqtt_ms_wait_for_puback
#                elif qos == 2:
#                    message.state = mqtt_ms_wait_for_pubrec
#                self._out_message_mutex.release()
#
#                rc = self._send_publish(message.mid, message.topic, message.payload, message.qos, message.retain, message.dup)
#
#                # remove from inflight messages so it will be send after a connection is made
#                if rc is MQTT_ERR_NO_CONN:
#                    with self._out_message_mutex:
#                        self._inflight_messages -= 1
#                        message.state = mqtt_ms_publish
#
#                return (rc, local_mid)
#            else:
#                message.state = mqtt_ms_queued;
#                self._out_message_mutex.release()
#                return (MQTT_ERR_SUCCESS, local_mid)
#
#    def username_pw_set(self, username, password=None):
#        """Set a username and optionally a password for broker authentication.
#
#        Must be called before connect() to have any effect.
#        Requires a broker that supports MQTT v3.1.
#
#        username: The username to authenticate with. Need have no relationship to the client id.
#        password: The password to authenticate with. Optional, set to None if not required.
#        """
#        self._username = username.encode('utf-8')
#        self._password = password

    def disconnect(self):
        """Disconnect a connected client from the broker."""
        self._state = mqtt_cs_disconnecting

        if self._sock is None:
            return MQTT_ERR_NO_CONN

        return self._send_disconnect()

    def subscribe(self, topic, qos=0):
        """Subscribe the client to one or more topics.

        This function may be called in three different ways:

        Simple string and integer
        -------------------------
        e.g. subscribe("my/topic", 2)

        topic: A string specifying the subscription topic to subscribe to.
        qos: The desired quality of service level for the subscription.
             Defaults to 0.

        String and integer tuple
        ------------------------
        e.g. subscribe(("my/topic", 1))

        topic: A tuple of (topic, qos). Both topic and qos must be present in
               the tuple.
        qos: Not used.

        List of string and integer tuples
        ------------------------
        e.g. subscribe([("my/topic", 0), ("another/topic", 2)])

        This allows multiple topic subscriptions in a single SUBSCRIPTION
        command, which is more efficient than using multiple calls to
        subscribe().

        topic: A list of tuple of format (topic, qos). Both topic and qos must
               be present in all of the tuples.
        qos: Not used.

        The function returns a tuple (result, mid), where result is
        MQTT_ERR_SUCCESS to indicate success or (MQTT_ERR_NO_CONN, None) if the
        client is not currently connected.  mid is the message ID for the
        subscribe request. The mid value can be used to track the subscribe
        request by checking against the mid argument in the on_subscribe()
        callback if it is defined.

        Raises a ValueError if qos is not 0, 1 or 2, or if topic is None or has
        zero string length, or if topic is not a string, tuple or list.
        """
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

    def unsubscribe(self, topic):
        """Unsubscribe the client from one or more topics.

        topic: A single string, or list of strings that are the subscription
               topics to unsubscribe from.

        Returns a tuple (result, mid), where result is MQTT_ERR_SUCCESS
        to indicate success or (MQTT_ERR_NO_CONN, None) if the client is not
        currently connected.
        mid is the message ID for the unsubscribe request. The mid value can be
        used to track the unsubscribe request by checking against the mid
        argument in the on_unsubscribe() callback if it is defined.

        Raises a ValueError if topic is None or has zero string length, or is
        not a string or list.
        """
        topic_list = None
        if topic is None:
            raise ValueError('Invalid topic.')
        if isinstance(topic, str):
            if len(topic) == 0:
                raise ValueError('Invalid topic.')
            topic_list = [topic.encode('utf-8')]
        elif isinstance(topic, list):
            topic_list = []
            for t in topic:
                if len(t) == 0 or not isinstance(t, str):
                    raise ValueError('Invalid topic.')
                topic_list.append(t.encode('utf-8'))

        if topic_list is None:
            raise ValueError("No topic specified, or incorrect topic type.")

        if self._sock is None and self._ssl is None:
            return (MQTT_ERR_NO_CONN, None)

        return self._send_unsubscribe(False, topic_list)

    def loop_read(self, max_packets=1):
        """Process read network events. Use in place of calling loop() if you
        wish to handle your client reads as part of your own application.

        Use socket() to obtain the client socket to call select() or equivalent
        on.

        Do not use if you are using the threaded interface loop_start()."""
        print("loop_read")
        if self._sock is None and self._ssl is None:
            return MQTT_ERR_NO_CONN

        max_packets = len(self._out_messages) + len(self._in_messages)
        if max_packets < 1:
            max_packets = 1

        for i in range(0, max_packets):
            rc = self._packet_read()
            if rc > 0:
                return self._loop_rc_handle(rc)
            elif rc == MQTT_ERR_AGAIN:
                return MQTT_ERR_SUCCESS
        return MQTT_ERR_SUCCESS

    def loop_write(self, max_packets=1):
        """Process read network events. Use in place of calling loop() if you
        wish to handle your client reads as part of your own application.

        Use socket() to obtain the client socket to call select() or equivalent
        on.

        Use want_write() to determine if there is data waiting to be written.

        Do not use if you are using the threaded interface loop_start()."""
        print("loop_write")
        if self._sock is None and self._ssl is None:
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
        """Process miscellaneous network events. Use in place of calling loop() if you
        wish to call select() or equivalent on.

        Do not use if you are using the threaded interface loop_start()."""
        print("loop_misc")
        if self._sock is None: # and self._ssl is None:
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

    def max_inflight_messages_set(self, inflight):
        """Set the maximum number of messages with QoS>0 that can be part way
        through their network flow at once. Defaults to 20."""
        if inflight < 0:
            raise ValueError('Invalid inflight.')
        self._max_inflight_messages = inflight

    def message_retry_set(self, retry):
        """Set the timeout in seconds before a message with QoS>0 is retried.
        20 seconds by default."""
        if retry < 0:
            raise ValueError('Invalid retry.')

        self._message_retry = retry

    def user_data_set(self, userdata):
        """Set the user data variable passed to callbacks. May be any data type."""
        self._userdata = userdata

    def will_set(self, topic, payload=None, qos=0, retain=False):
        """Set a Will to be sent by the broker in case the client disconnects unexpectedly.

        This must be called before connect() to have any effect.

        topic: The topic that the will message should be published on.
        payload: The message to send as a will. If not given, or set to None a
        zero length message will be used as the will. Passing an int or float
        will result in the payload being converted to a string representing
        that number. If you wish to send a true int/float, use struct.pack() to
        create the payload you require.
        qos: The quality of service level to use for the will.
        retain: If set to true, the will message will be set as the "last known
        good"/retained message for the topic.

        Raises a ValueError if qos is not 0, 1 or 2, or if topic is None or has
        zero string length.
        """
        if topic is None or len(topic) == 0:
            raise ValueError('Invalid topic.')
        if qos<0 or qos>2:
            raise ValueError('Invalid QoS level.')
        if isinstance(payload, str):
            self._will_payload = payload.encode('utf-8')
        elif isinstance(payload, bytearray):
            self._will_payload = payload
        elif isinstance(payload, int) or isinstance(payload, float):
            self._will_payload = str(payload)
        elif payload is None:
            self._will_payload = None
        else:
            raise TypeError('payload must be a string, bytearray, int, float or None.')

        self._will = True
        self._will_topic = topic.encode('utf-8')
        self._will_qos = qos
        self._will_retain = retain

    def will_clear(self):
        """ Removes a will that was previously configured with will_set().

        Must be called before connect() to have any effect."""
        self._will = False
        self._will_topic = ""
        self._will_payload = None
        self._will_qos = 0
        self._will_retain = False

    def socket(self):
        """Return the socket or ssl object for this client."""
        return self._sock

    def message_callback_add(self, sub, callback):
        """Register a message callback for a specific topic.
        Messages that match 'sub' will be passed to 'callback'. Any
        non-matching messages will be passed to the default on_message
        callback.
        
        Call multiple times with different 'sub' to define multiple topic
        specific callbacks.
        
        Topic specific callbacks may be removed with
        message_callback_remove()."""
        if callback is None or sub is None:
            raise ValueError("sub and callback must both be defined.")

        for i in range(0, len(self.on_message_filtered)):
            if self.on_message_filtered[i][0] == sub:
                self.on_message_filtered[i] = (sub, callback)
                return

        self.on_message_filtered.append((sub, callback))

    def message_callback_remove(self, sub):
        """Remove a message callback previously registered with
        message_callback_add()."""
        if sub is None:
            raise ValueError("sub must defined.")

        for i in range(0, len(self.on_message_filtered)):
            if self.on_message_filtered[i][0] == sub:
                self.on_message_filtered.pop(i)
                return

    # ============================================================
    # Private functions
    # ============================================================

    def _loop_rc_handle(self, rc):
        if rc:
            if self._ssl:
                self._ssl.close()
                self._ssl = None
            elif self._sock:
                self._sock.close()
                self._sock = None

            if self._state == mqtt_cs_disconnecting:
                rc = MQTT_ERR_SUCCESS
            if self.on_disconnect:
                self._in_callback = True
                self.on_disconnect(self, self._userdata, rc)
                self._in_callback = False

        return rc

    def _packet_read(self):
        # This gets called if pselect() indicates that there is network data
        # available - ie. at least one byte.  What we do depends on what data we
        # already have.
        # If we've not got a command, attempt to read one and save it. This should
        # always work because it's only a single byte.
        # Then try to read the remaining length. This may fail because it is may
        # be more than one byte - will need to save data pending next read if it
        # does fail.
        # Then try to read the remaining payload, where 'payload' here means the
        # combined variable header and actual payload. This is the most likely to
        # fail due to longer length, so save current data and current position.
        # After all data is read, send to _mqtt_handle_packet() to deal with.
        # Finally, free the memory and reset everything to starting conditions.
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

    def _easy_log(self, level, buf):
        if self.on_log:
            self.on_log(self, self._userdata, level, buf)

    def _check_keepalive(self):
        now = time.time()
        last_msg_out = self._last_msg_out
        last_msg_in = self._last_msg_in
        if (self._sock is not None or self._ssl is not None) and (now - last_msg_out >= self._keepalive or now - last_msg_in >= self._keepalive):
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
        self._last_mid = self._last_mid + 1
        if self._last_mid == 65536:
            self._last_mid = 1
        return self._last_mid

    def _topic_wildcard_len_check(self, topic):
        # Search for + or # in a topic. Return MQTT_ERR_INVAL if found.
         # Also returns MQTT_ERR_INVAL if the topic string is too long.
         # Returns MQTT_ERR_SUCCESS if everything is fine.
        if '+' in topic or '#' in topic or len(topic) == 0 or len(topic) > 65535:
            return MQTT_ERR_INVAL
        else:
            return MQTT_ERR_SUCCESS

    def _send_pingreq(self):
        self._easy_log(MQTT_LOG_DEBUG, "Sending PINGREQ")
        rc = self._send_simple_command(PINGREQ)
        if rc == MQTT_ERR_SUCCESS:
            self._ping_t = time.time()
        return rc

    def _send_pingresp(self):
        self._easy_log(MQTT_LOG_DEBUG, "Sending PINGRESP")
        return self._send_simple_command(PINGRESP)

    def _send_puback(self, mid):
        self._easy_log(MQTT_LOG_DEBUG, "Sending PUBACK (Mid: "+str(mid)+")")
        return self._send_command_with_mid(PUBACK, mid, False)

    def _send_pubcomp(self, mid):
        self._easy_log(MQTT_LOG_DEBUG, "Sending PUBCOMP (Mid: "+str(mid)+")")
        return self._send_command_with_mid(PUBCOMP, mid, False)

    def _pack_remaining_length(self, packet, remaining_length):
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
        if isinstance(data, bytearray) or isinstance(data, bytes):
            packet.extend(struct.pack("!H", len(data)))
            packet.extend(data)
        elif isinstance(data, str):
            udata = data.encode('utf-8')
            pack_format = "!H" + str(len(udata)) + "s"
            packet.extend(struct.pack(pack_format, len(udata), udata))
        else:
            raise TypeError

    def _send_publish(self, mid, topic, payload=None, qos=0, retain=False, dup=False):
        if self._sock is None and self._ssl is None:
            return MQTT_ERR_NO_CONN

        utopic = topic.encode('utf-8')
        command = PUBLISH | ((dup&0x1)<<3) | (qos<<1) | retain
        packet = bytearray()
        packet.extend(struct.pack("!B", command))
        if payload is None:
            remaining_length = 2+len(utopic)
            self._easy_log(MQTT_LOG_DEBUG, "Sending PUBLISH (d"+str(dup)+", q"+str(qos)+", r"+str(int(retain))+", m"+str(mid)+", '"+topic+"' (NULL payload)")
        else:
            if isinstance(payload, str):
                upayload = payload.encode('utf-8')
                payloadlen = len(upayload)
            elif isinstance(payload, bytearray):
                payloadlen = len(payload)
            elif isinstance(payload, unicode):
                upayload = payload.encode('utf-8')
                payloadlen = len(upayload)

            remaining_length = 2+len(utopic) + payloadlen
            self._easy_log(MQTT_LOG_DEBUG, "Sending PUBLISH (d"+str(dup)+", q"+str(qos)+", r"+str(int(retain))+", m"+str(mid)+", '"+topic+"', ... ("+str(payloadlen)+" bytes)")

        if qos > 0:
            # For message id
            remaining_length = remaining_length + 2

        self._pack_remaining_length(packet, remaining_length)
        self._pack_str16(packet, topic)

        if qos > 0:
            # For message id
            packet.extend(struct.pack("!H", mid))

        if payload is not None:
            if isinstance(payload, str):
                pack_format = str(payloadlen) + "s"
                packet.extend(struct.pack(pack_format, upayload))
            elif isinstance(payload, bytearray):
                packet.extend(payload)
            elif isinstance(payload, unicode):
                pack_format = str(payloadlen) + "s"
                packet.extend(struct.pack(pack_format, upayload))
            else:
                raise TypeError('payload must be a string, unicode or a bytearray.')

        return self._packet_queue(PUBLISH, packet, mid, qos)

    def _send_pubrec(self, mid):
        self._easy_log(MQTT_LOG_DEBUG, "Sending PUBREC (Mid: "+str(mid)+")")
        return self._send_command_with_mid(PUBREC, mid, False)

    def _send_pubrel(self, mid, dup=False):
        self._easy_log(MQTT_LOG_DEBUG, "Sending PUBREL (Mid: "+str(mid)+")")
        return self._send_command_with_mid(PUBREL|2, mid, dup)

    def _send_command_with_mid(self, command, mid, dup):
        # For PUBACK, PUBCOMP, PUBREC, and PUBREL
        if dup:
            command = command | 8

        remaining_length = 2
        packet = struct.pack('!BBH', command, remaining_length, mid)
        return self._packet_queue(command, packet, mid, 1)

    def _send_simple_command(self, command):
        # For DISCONNECT, PINGREQ and PINGRESP
        remaining_length = 0
        packet = struct.pack('!BB', command, remaining_length)
        return self._packet_queue(command, packet, 0, 0)

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

        if self._will:
            if self._will_payload is not None:
                remaining_length = remaining_length + 2+len(self._will_topic) + 2+len(self._will_payload)
            else:
                remaining_length = remaining_length + 2+len(self._will_topic) + 2

            connect_flags = connect_flags | 0x04 | ((self._will_qos&0x03) << 3) | ((self._will_retain&0x01) << 5)

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

        if self._will:
            self._pack_str16(packet, self._will_topic)
            if self._will_payload is None or len(self._will_payload) == 0:
                packet.extend(struct.pack("!H", 0))
            else:
                self._pack_str16(packet, self._will_payload)

        if self._username:
            self._pack_str16(packet, self._username)

            if self._password:
                self._pack_str16(packet, self._password)

        self._keepalive = keepalive
        return self._packet_queue(command, packet, 0, 0)

    def _send_disconnect(self):
        return self._send_simple_command(DISCONNECT)

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

    def _send_unsubscribe(self, dup, topics):
        remaining_length = 2
        for t in topics:
            remaining_length = remaining_length + 2+len(t)

        command = UNSUBSCRIBE | (dup<<3) | (1<<1)
        packet = bytearray()
        packet.extend(struct.pack("!B", command))
        self._pack_remaining_length(packet, remaining_length)
        local_mid = self._mid_generate()
        packet.extend(struct.pack("!H", local_mid))
        for t in topics:
            self._pack_str16(packet, t)
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
        # Write a single byte to sockpairW (connected to sockpairR) to break
        # out of select() if in threaded mode.
        #try:
        #    self._sockpairW.send(sockpair_data)
        #except socket.error as err:
        #    if err.errno != EAGAIN:
        #        raise
        print("self._in_callback =", self._in_callback)
        if not self._in_callback: 
            return self.loop_write()
        else:
            print(MQTT_ERR_SUCCESS)
            return MQTT_ERR_SUCCESS

    def _packet_handle(self):
        print("_packet_handle")
        cmd = self._in_packet['command']&0xF0
        if cmd == PINGREQ:
            return self._handle_pingreq()
        elif cmd == PINGRESP:
            return self._handle_pingresp()
        elif cmd == PUBACK:
            return self._handle_pubackcomp("PUBACK")
        elif cmd == PUBCOMP:
            return self._handle_pubackcomp("PUBCOMP")
        elif cmd == PUBLISH: #appear to need PUBLISH
            return self._handle_publish()
        elif cmd == PUBREC:
            return self._handle_pubrec()
        elif cmd == PUBREL:
            return self._handle_pubrel()
        elif cmd == CONNACK:
            return self._handle_connack()
        elif cmd == SUBACK:
            return self._handle_suback()
        elif cmd == UNSUBACK:
            return self._handle_unsuback()
        else:
            # If we don't recognise the command, return an error straight away.
            self._easy_log(MQTT_LOG_ERR, "Error: Unrecognised command "+str(cmd))
            return MQTT_ERR_PROTOCOL

    #def _handle_pingreq(self):
    #    if self._strict_protocol:
    #        if self._in_packet['remaining_length'] != 0:
    #            return MQTT_ERR_PROTOCOL

    #    self._easy_log(MQTT_LOG_DEBUG, "Received PINGREQ")
    #    return self._send_pingresp()

    #def _handle_pingresp(self):
    #    print("_handle_pingresp")
    #    if self._strict_protocol:
    #        if self._in_packet['remaining_length'] != 0:
    #            return MQTT_ERR_PROTOCOL

    #    # No longer waiting for a PINGRESP.
    #    self._ping_t = 0
    #    self._easy_log(MQTT_LOG_DEBUG, "Received PINGRESP")
    #    return MQTT_ERR_SUCCESS

    def _handle_connack(self):
        print("_handle_connack") #needed
        if self._strict_protocol:
            if self._in_packet['remaining_length'] != 2:
                return MQTT_ERR_PROTOCOL

        if len(self._in_packet['packet']) != 2:
            return MQTT_ERR_PROTOCOL

        (flags, result) = struct.unpack("!BB", self._in_packet['packet'])
        if result == CONNACK_REFUSED_PROTOCOL_VERSION and self._protocol == MQTTv311:
            self._easy_log(MQTT_LOG_DEBUG, "Received CONNACK ("+str(flags)+", "+str(result)+"), attempting downgrade to MQTT v3.1.")
            # Downgrade to MQTT v3.1
            self._protocol = MQTTv31
            return self.reconnect()

        if result == 0:
            self._state = mqtt_cs_connected

        self._easy_log(MQTT_LOG_DEBUG, "Received CONNACK ("+str(flags)+", "+str(result)+")")
        if self.on_connect:
            self._in_callback = True

            #argcount = self.on_connect.__code__.co_argcount

            #if argcount == 3:
            #    self.on_connect(self, self._userdata, result)
            #else:
            #    flags_dict = dict()
            #    flags_dict['session present'] = flags & 0x01
            #    self.on_connect(self, self._userdata, flags_dict, result)
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

    def _handle_suback(self):
        print("_handle_suback") #needed after _packet_handle
        self._easy_log(MQTT_LOG_DEBUG, "Received SUBACK")
        pack_format = "!H" + str(len(self._in_packet['packet'])-2) + 's'
        (mid, packet) = struct.unpack(pack_format, self._in_packet['packet'])
        pack_format = "!" + "B"*len(packet)
        granted_qos = struct.unpack(pack_format, packet)

        if self.on_subscribe:
            self._in_callback = True
            self.on_subscribe(self, self._userdata, mid, granted_qos)
            self._in_callback = False

        return MQTT_ERR_SUCCESS

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

        if sys.version_info[0] >= 3:
            message.topic = message.topic.decode('utf-8')

        if message.qos > 0:
            pack_format = "!H" + str(len(packet)-2) + 's'
            (message.mid, packet) = struct.unpack(pack_format, packet)

        message.payload = packet

        self._easy_log(
            MQTT_LOG_DEBUG,
            "Received PUBLISH (d"+str(message.dup)+
            ", q"+str(message.qos)+", r"+str(message.retain)+
            ", m"+str(message.mid)+", '"+message.topic+
            "', ...  ("+str(len(message.payload))+" bytes)")

        message.timestamp = time.time()
        if message.qos == 0:
            self._handle_on_message(message)
            return MQTT_ERR_SUCCESS
        elif message.qos == 1:
            rc = self._send_puback(message.mid)
            self._handle_on_message(message)
            return rc
        elif message.qos == 2:
            rc = self._send_pubrec(message.mid)
            message.state = mqtt_ms_wait_for_pubrel
            self._in_message_mutex.acquire()
            self._in_messages.append(message)
            self._in_message_mutex.release()
            return rc
        else:
            return MQTT_ERR_PROTOCOL

    def _handle_pubrel(self):
        if self._strict_protocol:
            if self._in_packet['remaining_length'] != 2:
                return MQTT_ERR_PROTOCOL

        if len(self._in_packet['packet']) != 2:
            return MQTT_ERR_PROTOCOL

        mid = struct.unpack("!H", self._in_packet['packet'])
        mid = mid[0]
        self._easy_log(MQTT_LOG_DEBUG, "Received PUBREL (Mid: "+str(mid)+")")

        self._in_message_mutex.acquire()
        for i in range(len(self._in_messages)):
            if self._in_messages[i].mid == mid:

                # Only pass the message on if we have removed it from the queue - this
                # prevents multiple callbacks for the same message.
                self._handle_on_message(self._in_messages[i])
                self._in_messages.pop(i)
                self._inflight_messages = self._inflight_messages - 1
                if self._max_inflight_messages > 0:
                    rc = self._update_inflight()
                    if rc != MQTT_ERR_SUCCESS:
                        return rc

                self._in_message_mutex.release()
                return self._send_pubcomp(mid)

        return MQTT_ERR_SUCCESS

    def _update_inflight(self):
        # Dont lock message_mutex here
        for m in self._out_messages:
            if self._inflight_messages < self._max_inflight_messages:
                if m.qos > 0 and m.state == mqtt_ms_queued:
                    self._inflight_messages = self._inflight_messages + 1
                    if m.qos == 1:
                        m.state = mqtt_ms_wait_for_puback
                    elif m.qos == 2:
                        m.state = mqtt_ms_wait_for_pubrec
                    rc = self._send_publish(m.mid, m.topic, m.payload, m.qos, m.retain, m.dup)
                    if rc != 0:
                        return rc
            else:
                return MQTT_ERR_SUCCESS
        return MQTT_ERR_SUCCESS

    def _handle_pubrec(self):
        if self._strict_protocol:
            if self._in_packet['remaining_length'] != 2:
                return MQTT_ERR_PROTOCOL

        mid = struct.unpack("!H", self._in_packet['packet'])
        mid = mid[0]
        self._easy_log(MQTT_LOG_DEBUG, "Received PUBREC (Mid: "+str(mid)+")")

        for m in self._out_messages:
            if m.mid == mid:
                m.state = mqtt_ms_wait_for_pubcomp
                m.timestamp = time.time()
                return self._send_pubrel(mid, False)

        return MQTT_ERR_SUCCESS

    def _handle_unsuback(self):
        if self._strict_protocol:
            if self._in_packet['remaining_length'] != 2:
                return MQTT_ERR_PROTOCOL

        mid = struct.unpack("!H", self._in_packet['packet'])
        mid = mid[0]
        self._easy_log(MQTT_LOG_DEBUG, "Received UNSUBACK (Mid: "+str(mid)+")")
        if self.on_unsubscribe:
            self._in_callback = True
            self.on_unsubscribe(self, self._userdata, mid)
            self._in_callback = False
        return MQTT_ERR_SUCCESS

    def _handle_pubackcomp(self, cmd):
        if self._strict_protocol:
            if self._in_packet['remaining_length'] != 2:
                return MQTT_ERR_PROTOCOL

        mid = struct.unpack("!H", self._in_packet['packet'])
        mid = mid[0]
        self._easy_log(MQTT_LOG_DEBUG, "Received "+cmd+" (Mid: "+str(mid)+")")

        for i in range(len(self._out_messages)):
            try:
                if self._out_messages[i].mid == mid:
                    # Only inform the client the message has been sent once.
                    if self.on_publish:
                        self._in_callback = True
                        self.on_publish(self, self._userdata, mid)
                        self._in_callback = False

                    self._out_messages.pop(i)
                    self._inflight_messages = self._inflight_messages - 1
                    if self._max_inflight_messages > 0:
                        rc = self._update_inflight()
                        if rc != MQTT_ERR_SUCCESS:
                            return rc
                    return MQTT_ERR_SUCCESS
            except IndexError:
                # Have removed item so i>count.
                # Not really an error.
                pass

        return MQTT_ERR_SUCCESS

    def _handle_on_message(self, message):
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
