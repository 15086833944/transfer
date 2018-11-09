#-*- coding:utf-8 -*-

import sys
reload(sys)
sys.setdefaultencoding('utf8')


from socket import *

ADD = ('127.0.0.1',8888)
    #创建套接字
sockfd=socket(AF_INET, SOCK_DGRAM)
    #绑定地址
sockfd.bind(ADD)
    #消息收发
data,addr = sockfd.recvfrom(1024)
print 'Receive from %s:%s' % (addr,data.encode())
sockfd.sendto('收到你的消息',addr)
    #关闭套接字
sockfd.close()

