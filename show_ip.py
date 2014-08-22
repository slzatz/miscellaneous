import socket
import pygame
import os
import platform
from time import sleep

if platform.machine() == 'armv6l':
    # from https://github.com/adafruit/adafruit-pi-cam/blob/master/cam.py
    os.putenv('SDL_VIDEODRIVER', 'fbcon')
    os.putenv('SDL_FBDEV', '/dev/fb1')
elif platform.system() == 'Windows':
    os.environ['SDL_VIDEODRIVER'] = 'windib'
elif platform.system() == "Linux":
    os.putenv('SDL_VIDEODRIVER', 'x11')
else:
    sys.exit("Currently unsupported hardware/OS")

pygame.init()
pygame.mouse.set_visible(0)

screen = pygame.display.set_mode((320, 240))
screen.fill((0,0,0))

font = pygame.font.SysFont('Sans', 16)

s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.connect(("gmail.com",80))

t = s.getsockname()[0]

text = font.render(t, True, (255, 0, 0))

s.close()

screen.blit(text, (0,0)) 
pygame.display.flip()

sleep(30)

