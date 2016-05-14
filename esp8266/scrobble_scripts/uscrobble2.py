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
from umqtt_client import MQTTClient as umc
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

  c = umc('abc', host)
  c.connect()
  c.subscribe('sonos/ct/current_track')

  cur_time = time.time()
  b = True
  sleep(2) 

  while 1:
    z = c.check_msg()
    if z:
      print(z)
      if isinstance(z, int):
        print("returned a command")
        if b:
          d.draw_text(128, 24, '|') 
        else:
          d.draw_text(125, 24, '-') 
        b = not b
        d.display()
        continue

      topic, msg = z
      zz = json.loads(msg.decode('utf-8'))
      print("returned a tuple")
      d.clear()
      d.display()
      d.draw_text(0, 0, zz.get('artist', '')[:20]) 
      d.draw_text(0, 12, zz.get('title', '')[:20]) 
      d.draw_text(0, 24, zz.get('title', '')[20:])
      d.display()

    t = time.time()
    print(t)
    if t > cur_time + 10:
        c.ping()
        cur_time = t
    gc.collect()
    print(gc.mem_free())
    sleep(1)

