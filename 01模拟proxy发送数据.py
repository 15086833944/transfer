#coding=utf-8

from socket import *
import time
import sys
import json
reload(sys)
sys.setdefaultencoding('utf8')

# 创建套接字
sockfd=socket(AF_INET, SOCK_DGRAM)

# L=[]
# for x in range(100):
#     L.append(460)
sockfd.sendto(666,('172.30.130.126',9994))
sockfd.close()


