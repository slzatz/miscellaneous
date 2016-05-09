'''
This micropython script does two things:
1) if songs are being scrobbled by sonos_scrobble.py it displays them on the feather OLED
   and also displays the time the song has been playing
2) The top bottom (A) increases the volume and the bottom button (B) decreases the volume
'''

import gc
from time import sleep
import socket
import json
import network
from config import host, ssid, pw
from ssd1306_min import SSD1306 as SSD
import umqtt
from machine import Pin, I2C

i2c = I2C(scl=Pin(5), sda=Pin(4), freq=400000)

d = SSD(i2c)
d.init_display()
d.draw_text(0, 0, "HELLO STEVE")
d.display()

def callback_louder(p):
  b[0] = s.send(louder)
  print("change pin", p, b[0])
 
def callback_quieter(p):
  b[0] = s.send(quieter)
  print("change pin", p, b[0])

b = bytearray(2)
quieter = umqtt.mtpPublish('sonos/ct', '{"action":"quieter"}')
louder = umqtt.mtpPublish('sonos/ct', '{"action":"louder"}')
s = socket.socket()
p0 = Pin(0, Pin.IN, Pin.PULL_UP)
p2 = Pin(2, Pin.IN, Pin.PULL_UP)
p0.irq(trigger=Pin.IRQ_RISING, handler=callback_louder)
p2.irq(trigger=Pin.IRQ_RISING, handler=callback_quieter)

def run():
  wlan = network.WLAN(network.STA_IF)
  wlan.active(True)
  if not wlan.isconnected():
    print('connecting to network...')
    wlan.connect(ssid, pw)
    while not wlan.isconnected():
      pass
  print('network config:', wlan.ifconfig())     

  #s = socket.socket()
  s.connect((host, 1883))
  s.send(umqtt.mtpConnect("somename"))
  m = s.recv(100)
  print("CONNACK = ",m)
  s.send(umqtt.mtpUnsubscribe("sonos/nyc/current_track"))
  m = s.recv(100)
  s.send(umqtt.mtpSubscribe("sonos/ct/current_track"))
  m = s.recv(100)
  print("SUBACK = ",m)
  sleep(3) 

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
      zzz = json.loads(msg.decode('utf-8'))

      if 'position' in zzz:
        # not clearing the display because adding current position to display
        d.draw_text(75, 24, zzz['position']) 
      
      else:
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
