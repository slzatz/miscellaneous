from umqtt import MQTTClient as m
import time

c = m('abc', '54.173.234.69')
c.connect()
c.subscribe('test')
cur_time = time.time()
while 1:
    z = c.check_msg()
    if z:
        print(z)
    #print(c.check_msg())
    #print(time.time())
    t = time.time()
    print(t)
    if t > cur_time + 10:
        print(c.ping())
        cur_time = t
    time.sleep(1)
