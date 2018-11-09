#-*- coding:utf-8 -*-

from socket import *
import sys
reload(sys)
sys.setdefaultencoding('utf8')


server_addr = ('127.0.0.1',8888)
# 创建套接字
sockfd = socket(AF_INET, SOCK_DGRAM)
data = input("消息:")
# 给服务器发送
sockfd.sendto(data,server_addr)
# 收到服务器回复
data,addr=sockfd.recvfrom(1024)
print '从服务器收到:'+data.encode()
#关闭套接字
sockfd.close()