#!/usr/bin/env python
# -*- coding:utf-8 -*-
import os
import sys
from threading import Thread
import urllib
import urllib2
from multiprocessing import Queue


reload(sys)
sys.setdefaultencoding('utf8')

# 调取selectinfo接口的函数
def fn(m):
    for x in range(10):
        try:
            req = urllib2.Request(url='http://172.30.130.126:9995/selectinfo/172.30.130.126')
            res = urllib2.urlopen(req)
            data = res.read()
            if not data:
                m+=1
        except:
            m+=1


# 调取storeinfo接口的函数
def ff(n):
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
    try:
        req = urllib2.Request(url="http://172.30.130.126:9995/storeinfo/",data=data)
        res = urllib2.urlopen(req)
        fanhui = res.read()
        if fanhui != 'ok':
            n+=1
    except:
        n+=1



def main():
    m = 0  # 用来记录selectinfo接口出现错误的次数
    n = 0  # 用来记录storeinfo接口出现错误的次数

    data_queue1 = Queue()  # 用来装所有的调取selectinfo接口的线程
    data_queue2 = Queue()  # 用来装所有的调取storeinfo接口的线程

    for x in range(10):
        data_queue1.put(x)

    for y in range(10,20):
        data_queue2.put(y)

    print data_queue1
    print data_queue2

    pid = os.fork()
    if pid == 0:
        while True:
            print data_queue1
            try:
                item = data_queue1.get() #获取线程
                if item:
                    t = Thread(target=fn,args=(m,))
                    t.setDaemon(True)
                    t.start()
                else:
                    break
            except:
                print '线程退出'
        if m == 0:
            print '调取selectinfo接口执行成功！'
        else:
            print '调取selectinfo接口执行出现错误，错误数量为：'+str(m)
    else:
        while True:
            print data_queue2
            try:
                item = data_queue2.get() #获取线程
                if item:
                    t = Thread(target=ff,args=n)
                    t.setDaemon(True)
                    t.start()
                else:
                    break
            except:
                print '线程退出'
        if n == 0:
            print '调取storeinfo接口执行成功！'
        else:
            print '调取storeinfo接口执行出现错误，错误数量为：'+str(n)


if __name__ == '__main__':
    main()





