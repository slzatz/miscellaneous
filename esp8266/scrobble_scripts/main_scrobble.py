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

def run():
  wlan = network.WLAN(network.STA_IF)
  wlan.active(True)
  if not wlan.isconnected():
    print('connecting to network...')
    wlan.connect(ssid, pw)
    while not wlan.isconnected():
      pass
  print('network config:', wlan.ifconfig())     

  while 1:
      s = socket.socket()
      s.connect((host, 5000))
      s.send('GET /sonos_check HTTP/1.0\r\n\r\n')
      z = s.recv(64)
      z = s.recv(1024)
      s.close()
      zz = z.decode('ascii', 'replace')
      i = zz.find('{')
      zzz = json.loads(zz[i:])

      if zzz['updated']:
        d.clear()
        d.display()
        d.draw_text(0, 0, zzz['artist'][:20])
        d.draw_text(0, 12, zzz['title'][:20])
        d.draw_text(0, 24, zzz['title'][20:])
        d.display()

      sleep(3)

run()
