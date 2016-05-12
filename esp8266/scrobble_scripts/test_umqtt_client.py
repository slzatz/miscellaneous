'''
server = 54.173.234.69
54.173.234.69 1883
connect
b' \x02\x00\x00'
subscribe
b'\x90\x03\x00\x01\x00'
1462978855.068099
res =  b'1'
(b'test', b'This is a new message')
1462978856.0821
1462978857.096102
1462978858.096319
Traceback (most recent call last):
'''

from umqtt_client import MQTTClient as m
import time

c = m('abc', '54.173.234.69')
c.connect()
c.subscribe('test')
cur_time = time.time()
while 1:
    z = c.check_msg()
    if z:
        print(z)
        if isinstance(z, int):
            print("returned a command")
        else:
            print("returned a tuple")
    t = time.time()
    print(t)
    if t > cur_time + 10:
        c.ping()
        cur_time = t
    time.sleep(1)
