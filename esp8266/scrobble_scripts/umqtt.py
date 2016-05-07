# Borrowed heavily from Andrew http://forum.micropython.org/viewtopic.php?t=1101#p6545

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
def mtpPublish(topic, data):
  return  mtPacket(0b00110001, mtStr(topic), data)

def mtpSubscribe(topic):
    return mtPacket(
        0b10000010, #subscribe command byte
        bytes([0x00,0x00]), #MSB, LSB for packet identifier; test case no identifier
        mtStr(topic) + bytes([0x00])) #last two bits of last byte is QoS; test case = 0

def mtpUnsubscribe(topic):
    return mtPacket(
        0b10100010, #unsubscribe command byte
        bytes([0x00,0x00]), #MSB, LSB for packet identifier; test case no identifier
        mtStr(topic) ) #last two bits of last byte is QoS; test case = 0

