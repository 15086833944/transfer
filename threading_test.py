#!/usr/bin/env python
# -*- coding:utf-8 -*-
import os
import sys
from threading import Thread
import urllib
import urllib2
# from multiprocessing import Queue
import Queue


reload(sys)
sys.setdefaultencoding('utf8')

m = 0  # 用来记录selectinfo接口出现错误的次数
n = 0  # 用来记录storeinfo接口出现错误的次数

data_queue1 = Queue.Queue()  # 用来装所有的调取selectinfo接口的线程
data_queue2 = Queue.Queue()  # 用来装所有的调取storeinfo接口的线程


# 调取selectinfo接口的函数
def fn():
    global m
    for x in range(10):
        try:
            req = urllib2.Request(url='http://172.30.130.126:9995/selectinfo/172.30.130.126')
            res = urllib2.urlopen(req)
            data = res.read()
            if not data:
                m+=1
            else:
                print data
        except:
            m+=1


# 调取storeinfo接口的函数
def ff():
    global n
    msg = {}
    msg["id"]=10000,
    msg["biz_ip"]="172.30.130.134",
    msg["manage_ip"]="172.30.130.134",
    msg["process_name"]="01test.py",
    msg["key_word"]="01test",
    msg["trigger_compare"]=3,
    msg["trigger_value"]=1,
    msg["trigger_level"]=1,
    msg["trigger_cycle_value"]=1,
    msg["trigger_cycle_unit"]=0,
    msg["should_be"]=1
    msg["new_count"]=1
    data = urllib.urlencode(msg)
    print data
    try:
        for y in range(10):
            req = urllib2.Request(url="http://172.30.130.126:9995/storeinfo/",data=data)
            res = urllib2.urlopen(req)
            fanhui = res.read()
            print fanhui
            if fanhui == 'ok':
                pass
            else:
                print fanhui
                n += 1
    except:
        n+=1

def main():
    for x in range(1,11):
        data_queue1.put(x)
    for y in range(101,111):
        data_queue2.put(y)

    pid = os.fork()
    if pid == 0:
        global m
        while True:
            try:
                item1 = data_queue1.get() #获取线程
                print '调取selectinfo的线程：'+str(item1)
                if item1:
                    t = Thread(target=fn)
                    t.setDaemon(True)
                    t.start()
                if data_queue1.empty():
                    print '调取selectinfo执行完，退出循环'
                    break
            except:
                print '创建线程失败'
        if m == 0:
            print '调取selectinfo接口执行成功,错误数量为：'+str(m)
        else:
            print '调取selectinfo接口执行出现错误，错误数量为：'+str(m)
        sys.exit('selectinfo退出进程')
    else:
        global n
        while True:
            try:
                item2 = data_queue2.get() #获取线程
                print '调取storeinfo的线程：' + str(item2)
                if item2:
                    t = Thread(target=ff)
                    t.setDaemon(True)
                    t.start()
                if data_queue2.empty():
                    print '调取storeinfo线程执行完，退出循环'
                    break
            except:
                print '创建线程失败'
        if n == 0:
            print '调取storeinfo接口执行成功,错误数量为：'+str(n)
        else:
            print '调取storeinfo接口执行出现错误，错误数量为：'+str(n)
        sys.exit('storeinfo退出进程')


if __name__ == '__main__':
    main()





