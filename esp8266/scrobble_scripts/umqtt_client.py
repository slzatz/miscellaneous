'''
>>> from umqtt import MQTTClient as m
>>> c = m('abc', '54.173.234.69')
server = 54.173.234.69
54.173.234.69 1883
>>> c.connect()
>>> c.publish('test', 'hello world')
>>>
MicroPython rawsocket module supports file interface directly
'''

import socket as socket
import struct as struct
#from binascii import hexlify
import time

class MQTTClient:

    def __init__(self, client_id, server, port=1883):
        self.client_id = client_id.encode('utf-8')
        self.sock = socket.socket()
        print("server =",server)
        print(server,port)
        self.addr = socket.getaddrinfo(server, port)[0][-1]
        self.pid = 0

    def send_str(self, s):
        self.sock.send(struct.pack("!H", len(s)))
        self.sock.send(s)

    def connect(self):
        self.sock.connect(self.addr)
        msg = bytearray(b"\x10\0\0\x04MQTT\x04\x02\0\0")
        msg[1] = 10 + 2 + len(self.client_id)
        self.sock.send(msg)
        #print(hex(len(msg)), hexlify(msg, ":"))
        self.send_str(self.client_id)
        resp = self.sock.recv(4)
        assert resp == b"\x20\x02\0\0", resp

    def disconnect(self):
        self.sock.send(b"\xe0\0")
        self.sock.close()

    def publish(self, topic, msg, qos=0, retain=False):
        assert qos == 0
        pkt = bytearray(b"\x30\0")
        pkt[0] |= qos << 1 | retain
        pkt[1] = 2 + len(topic) + len(msg)
        #print(hex(len(pkt)), hexlify(pkt, ":"))
        self.sock.send(pkt)
        self.send_str(topic.encode('utf-8'))
        self.sock.send(msg.encode('utf-8'))

    def subscribe(self, topic):
        pkt = bytearray(b"\x82\0\0\0")
        self.pid += 1
        struct.pack_into("!BH", pkt, 1, 2 + 2 + len(topic) + 1, self.pid)
        #print(hex(len(pkt)), hexlify(pkt, ":"))
        self.sock.send(pkt)
        self.send_str(topic.encode('utf-8'))
        self.sock.send(b"\0")
        resp = self.sock.recv(5)
        print(resp)
        assert resp[0] == 0x90
        assert resp[2] == pkt[2] and resp[3] == pkt[3]
        assert resp[4] == 0

    def wait_msg(self):
        try:
            res = self.sock.recv(1) #read(1)
            print("res = ",res)
            #print(bin(res))
        except:
            #print("Exception: No data")
            return None
        #if res[0] >> 4 !=3: #more general but not handling QoS > 0
        if res[0] not in (48,49):
            return res
        self.sock.setblocking(True)
        sz = self.sock.recv(1)[0]
        if sz > 127:
            sz1 = self.sock.recv(1)[0]
            sz = sz1*128 + sz - 128

        z = self.sock.recv(sz)
        # topic length is first two bytes of variable header
        # it's just a 16 bit integer
        # first byte is bits 9 - 16
        # So that is shifting the first bit 8 places
        # the second bit is just the second bit
        topic_len = z[:2]
        topic_len = (topic_len[0] << 8) | topic_len[1]
        topic = z[2:topic_len+2]
        msg = z[topic_len+2:]
        return (topic, msg)

    def check_msg(self):
        self.sock.setblocking(False)
        return self.wait_msg()

    def ping(self):
        pkt = bytearray([0b11000000,0x0])
        self.sock.send(pkt)
        time.sleep(1)
        self.sock.setblocking(False)
        try:
            res = self.sock.recv(2) #read(1)
            print("res = ",res)
            return res[0]>>4
            #print(bin(res))
        except:
            print("Exception: No data")
            return None
