# Borrowed from Andrew http://forum.micropython.org/viewtopic.php?t=1101#p6545

#Each of these strings is prefixed with a two byte length field that gives the number of bytes in the UTF-8 encoded string (python bytes). Byte 1 is string length MSB and byte 2 is LSB and bytes 3 .. is the utf-8 encoded data

import network
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


def mtPacket(cmd, variable, payload):
  return bytes([cmd, len(variable) + len(payload)]) + variable + payload

def mtpConnect(name):
  return mtPacket(
       0b00010000,
       mtStr("MQTT") + # protocol name
       b'\x04' +       # protocol level
       b'\x00' +       # connect flag
       b'\xFF\xFF',    # keepalive
       mtStr(name)
                 )

#disconnect byte 1: 111000 and byte 2: 0000000
def mtpDisconnect():
  return bytes([0b11100000, 0b00000000])

#0011XXXX ->00110000 - note last bit is retain so that could be zero.
def mtpPub(topic, data):
  return  mtPacket(0b00110001, mtStr(topic), data)

wlan = network.WLAN(network.STA_IF) 
wlan.active(True)    
wlan.connect('essid', 'password') 
print('Connected =',wlan.isconnected())      

s = socket.socket()
s.connect('xx.xx...', 1883)
s.send(mtpConnect("somename"))
time.sleep(2) 
s.send(mtpPub("topic...", b'message'))
s.send(mtpDisconnect())
s.close()
