'''
This micropython script displays songs that are being scrobbled to the mqtt 
broker running in AWS EC2 and also the top bottom (A) increases the volume 
and the bottom button (B) decreases the volume
Unlike earlier version, this version does ping the broker to keep it alive
'''

import gc
from time import sleep, time
import json
import network
from config import host, ssid, pw, loc
from ssd1306_min import SSD1306 as SSD
from umqtt_client import MQTTClient as umc
from machine import Pin, I2C

i2c = I2C(scl=Pin(5), sda=Pin(4), freq=400000)

d = SSD(i2c)
d.init_display()
d.draw_text(0, 0, "HELLO STEVE")
d.display()

c = umc('abc', host)

b = bytearray(1)
# mtpPublish is a class method that produces a bytes object that is used in
# the callback where we can't allocate any memory on the heap
quieter = umc.mtpPublish('sonos/'+loc, '{"action":"quieter"}')
louder = umc.mtpPublish('sonos/'+loc, '{"action":"louder"}')

def callback_louder(p):
  b[0] = c.sock.send(louder)
  print("change pin", p, b[0])
 
def callback_quieter(p):
  b[0] = c.sock.send(quieter)
  print("change pin", p, b[0])

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

  #c = umc('abc', host)
  c.connect()
  c.subscribe('sonos/{}/current_track'.format(loc))

  cur_time = time()
  b = True
  sleep(2) 

  while 1:
    z = c.check_msg()
    if z:
      print(z)
      if isinstance(z, int):
        print("returned a integer")
        d.draw_text(123, 24, ' ')
        if b:
          d.draw_text(123, 24, '|') 
        else:
          d.draw_text(123, 24, '-') 
        b = not b
        d.display()
        continue

      topic, msg = z
      zz = json.loads(msg.decode('utf-8'))
      print("assuming a tuple")
      d.clear()
      d.display()
      d.draw_text(0, 0, zz.get('artist', '')[:20]) 
      d.draw_text(0, 12, zz.get('title', '')[:20]) 
      d.draw_text(0, 24, zz.get('title', '')[20:])
      d.display()

    t = time()
    if t > cur_time + 30:
        c.ping()
        cur_time = t
    gc.collect()
    #print(gc.mem_free())
    sleep(1)

run()
