'''
Current script that does continual volume as well as play_pause
'''
from machine import ADC, Pin
from umqtt_client import MQTTClient as umc
from time import sleep
from config import host, loc, mqtt_id
import json

b = bytearray(1)

play_pause = umc.mtpPublish('sonos/'+loc, '{"action":"play_pause"}')

def callback(p):
  if b[0]:
    print("debounced", p, b[0])
    return
  #b[0] = c.sock.send(play_pause)
  print("change pin", p, b[0])

p14 = Pin(14, Pin.IN, Pin.PULL_UP)
p14.irq(trigger=Pin.IRQ_RISING, handler=callback)

c = umc(mqtt_id, host)
c.connect()

adc = ADC(0)
level = 300

def run():
  while 1:
    new_level = adc.read()
    if abs(new_level-level) > 50:
      try:
        c.publish('sonos/'+loc, json.dumps({"action":"volume", "level":new_level}))
      except Exception as e:
        print(e)
        c = umc(mqtt_id, host)
        c.connect()
      level = new_level
      print(level)
  
    b[0] = 0 # for debouncing
  
    sleep(.5)

run()
