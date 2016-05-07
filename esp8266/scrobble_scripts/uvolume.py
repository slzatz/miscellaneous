from machine import Pin
import umqtt
import socket
from config import host

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
p0.irq(Pin.IRQ_RISING, callback_louder)
p2.irq(Pin.IRQ_RISING, callback_quieter)

s = socket.socket()
s.connect((host, 1883))
s.send(umqtt.mtpConnect("hello"))

