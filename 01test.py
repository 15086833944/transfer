
#coding=utf-8

import json
import datetime
import urllib2
import os
import socket
import time
import sys
reload(sys)
sys.setdefaultencoding('utf8')

# res = urllib2.urlopen('http://192.168.178.130:5000/selectinfo/"172.17.11.22,172.20.33.44"')
# msg=res.read().decode('utf-8')

try:
    if os.fork() > 0:
        sys.exit(0)
except OSError, error:
    sys.exit(1)
os.chdir("/")
os.setsid()
os.umask(0)
try:
    if os.fork() > 0:
        sys.exit(0)
except OSError, error:
    sys.exit(1)

def receive_msg():
    socketfd = socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
    socketfd.bind(('0.0.0.0',9000))
    while True:
        data,addr = socketfd.recvfrom(1024)
        print '收到信息：'+data.decode()

receive_msg()