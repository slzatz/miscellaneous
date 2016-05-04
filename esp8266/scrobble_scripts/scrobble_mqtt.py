# Borrowed heavily from Andrew http://forum.micropython.org/viewtopic.php?t=1101#p6545

import gc
from time import sleep
import socket
import json
import network
from config import host, ssid, pw
from ssd1306_min import SSD1306 as SSD
from machine import Pin, I2C

i2c = I2C(scl=Pin(5), sda=Pin(4), freq=400000)

d = SSD(i2c)
d.init_display()
d.draw_text(0, 0, "HELLO STEVE")
d.display()

def mtStr(s):
 return bytes([len(s) >> 8, len(s) & 255]) + s.encode('utf-8')

def mtPacket(cmd, variable, payload):
  #returns 2 bytes and also a variable section and a payload
  return bytes([cmd, len(variable) + len(payload)]) + variable + payload

def mtpConnect(name):
  return mtPacket(
       0b00010000,     #connect command byte 
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
    return mtPacket(
        0b10000010, #subscribe command byte
        bytes([0x00,0x00]), #MSB, LSB for packet identifier; test case no identifier
        mtStr(topic) + bytes([0x00])) #last two bits of last byte is QoS; test case = 0

###########################################################

def run():
  wlan = network.WLAN(network.STA_IF)
  wlan.active(True)
  if not wlan.isconnected():
    print('connecting to network...')
    wlan.connect(ssid, pw)
    while not wlan.isconnected():
      pass
  print('network config:', wlan.ifconfig())     

  s = socket.socket()
  #s.settimeout(0)
  s.connect((host, 1883))
  s.send(mtpConnect("somename"))
  m = s.recv(100)
  # need to get the return code
  print("CONNACK = ",m)
  sleep(1) 
  s.send(mtpSubscribe("sonos/nyc/current_track"))
  m = s.recv(100)
  # need to get the return code
  print("SUBACK = ",m)

  #s.settimeout(5)
  #try:
  #  s.recv(200)
  #except:
  #  pass

  while 1:
    m = s.recv(200)
    if m:
      #print("first byte =", m[0]) #first byte should be 48
      #print("second byte =", m[1])
      # see spec but basically if first remaining length byte is 
      # > 128 then the highest bit is signalling continuation
      # and the following byte contributes 128 x it's value

      # note that remaining_length and topic used for debugging but not otherwise used
      if m[1] > 127:
        remaining_length = m[2]*128 + m[1] - 128
        i = 5
      else:
        remaining_length = m[1]
        i = 4

      #print("remaining length =", remaining_length)

      #topic = m[i:i+m[i-1]]
      #print("topic =", topic.decode('utf-8'))

      msg = m[i+m[i-1]:]
      #print("msg =", msg.decode('utf-8'))

      zzz = json.loads(msg.decode('utf-8'))
  
      d.clear()
      d.display()
      d.draw_text(0, 0, zzz['artist'][:20]) 
      d.draw_text(0, 12, zzz['title'][:20]) 
      d.draw_text(0, 24, zzz['title'][20:])
      d.display()

    gc.collect()
    print(gc.mem_free())
    sleep(3)

#s.send(mtpDisconnect())
#s.close()
run()
