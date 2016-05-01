# Borrowed from Andrew http://forum.micropython.org/viewtopic.php?t=1101#p6545

#Each of these strings is prefixed with a two byte length field that gives the number of bytes in the UTF-8 encoded string (python bytes). Byte 1 is string length MSB and byte 2 is LSB and bytes 3 .. is the utf-8 encoded data

#import network
import socket
from time import sleep

#x >> y Returns x with the bits shifted to the right by y places. This is the same as dividing x by 2**y
# 256 >> 8 = 1; 255 >> 8 = 0
# encoding means making bytes; decoding means making unicode
# & is bitwise anding
# note 255 is 11111111
# len(s) & 255 is taking the first 8 bits of the length
# len(s) >> 8 is how the higher order bytes look and len(s) & 255 is the lower order bits
# so 602 >> 8 = and could be used as 2*(2**8) and len(s) & 255 = 0b1011010 = the first 8 bits = 90
# below n[0] =2, n[1] = 90
#b'\x02ZThe rain in spain falls mainly on the plainThe rain in spain falls mainly on the plainThe rain in spain #falls mainly on the plainThe rain in spain falls mainly on the plainThe
# rain in spain falls mainly on the plainThe rain in spain falls mainly on the plainThe rain in spain falls #...

def mtStr(s):
 return bytes([len(s) >> 8, len(s) & 255]) + s.encode('utf-8')

#Bytes and bytearray objects contain single bytes – the former is immutable while the latter is a mutable sequence.
#Bytes objects can be constructed the constructor, bytes(), and from literals; use a b prefix with normal string syntax: b'xyzzy'. To construct byte arrays, use the bytearray() function.
#b = bytes([0xf4,0x12,0xb7])
def mtPacket(cmd, variable, payload):
  #returns 2 bytes and also a variable section and a payload
  return bytes([cmd, len(variable) + len(payload)]) + variable + payload

def mtpConnect(name):
  return mtPacket(
       0b00010000,     # command byte 
       mtStr("MQTT") + # protocol name part of variable header
       b'\x04' +       # protocol level part of variable header
       b'\x00' +       # connect flag part of variable header
       b'\xFF\xFF',    # keepalive part of variable header
       mtStr(name)     # payload
                 )

#disconnect byte 1: 111000 and byte 2: 0000000
def mtpDisconnect():
  return bytes([0b11100000, 0b00000000])

#0011XXXX ->00110000 - note last bit is retain so that could be zero.
def mtpPub(topic, data):
  return  mtPacket(0b00110001, mtStr(topic), data)

def mtpSubscribe(topic):
    #SUBSCRIBE = const(0x80) - > 0b10000000
    # According to spec the fixed header is 0b10000010 
    # According to spec the second byte is the remaining length = 2 bytes of variable header + payload
    # If QoS is zero the variable header is 0,0 or if > 1 would be some unique identifier
    # dup = 0 (I think)
    # 1<<1 -> 0b00000010
    return mtPacket(
        0b10000010, #subscribe command byte
        bytes([0x00,0x00]), #bytes([0b00000000, 0b00000000]), #bytes(2)
        mtStr(topic) + bytes([0x00])) #bytes([0b00000000]))

if 0:
    wlan = network.WLAN(network.STA_IF) 
    wlan.active(True)    
    wlan.connect('essid', 'password') 
    print('Connected =',wlan.isconnected())      

s = socket.socket()
s.connect(('54.173.234.69', 1883))
s.send(mtpConnect("somename"))
m = s.recv(100)
print("CONNACK = ",m)
sleep(1) 
#s.send(mtpPub("topic...", b'message'))
s.send(mtpSubscribe("test"))
m = s.recv(100)
print("SUBACK = ",m)

#try:
while 1:
    m = s.recv(1024)
    if m:
        topic = m[4:4+m[3]]
        msg = m[4+m[3]:]
        print("topic: {}; msg: {}".format(topic.decode('utf-8'), msg.decode('utf-8')))
        print(m)
    sleep(1)
#except KeyboardInterrupt:
#    pass

s.send(mtpDisconnect())
s.close()
