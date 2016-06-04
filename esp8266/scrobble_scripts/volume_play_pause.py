'''
Current script that does continual volume as well as play_pause
'''
from machine import ADC, Pin
from umqtt_client import MQTTClient as umc
from time import sleep
from config import host, mqtt_id
import json
import gc
try:
  from location import loc
except ImportError:
  from config import loc

b = bytearray(1)
play_pause = umc.mtpPublish('sonos/'+loc, '{"action":"play_pause"}')
c = umc(mqtt_id, host)

def callback(p):
  if b[0]:
    print("debounced", p, b[0])
    return
  b[0] = c.sock.send(play_pause)
  print("change pin", p, b[0])

p14 = Pin(14, Pin.IN, Pin.PULL_UP)
p14.irq(trigger=Pin.IRQ_FALLING, handler=callback)

adc = ADC(0)

def run():
  c.connect()
  sleep(2)
  print("loc =", loc)
  level = 300
  while 1:
    new_level = adc.read()
    if abs(new_level-level) > 50:
      try:
        c.publish('sonos/'+loc, json.dumps({"action":"volume", "level":new_level}))
      except Exception as e:
        print(e)
        c.sock.close()
        c.connect()
      level = new_level
      print(level)
  
    b[0] = 0 # for debouncing
    gc.collect() 
    sleep(1)

run()
