#!/usr/bin/env python
# -*- coding:utf-8 -*-
import os
import sys
from threading import Thread
import urllib
import urllib2
from multiprocessing import Pool


reload(sys)
sys.setdefaultencoding('utf8')

m = 0  # 用来记录selectinfo接口出现错误的次数
n = 0  # 用来记录storeinfo接口出现错误的次数

# 调取selectinfo接口的函数
def fn():
    global m
    for x in range(1):
        try:
            req = urllib2.Request(url='http://172.30.130.126:9995/selectinfo/172.30.130.126')
            res = urllib2.urlopen(req)
            data = res.read()
            if not data:
                m+=1
        except:
            m+=1


# 调取storeinfo接口的函数
def ff():
    global n
    msg = {}
    msg["id"]=10000
    msg["biz_ip"]="172.30.130.134"
    msg["manage_ip"]="172.30.130.134"
    msg["process_name"]="01test.py"
    msg["key_word"]="01test"
    msg["trigger_compare"]=3
    msg["trigger_value"]=1
    msg["trigger_level"]=1
    msg["trigger_cycle_value"]=1
    msg["trigger_cycle_unit"]=0
    msg["should_be"]=1
    msg["new_count"]=1
    data = urllib.urlencode(msg)
    try:
        for y in range(1):
            req = urllib2.Request(url="http://172.30.130.126:9995/storeinfo/",data=data)
            res = urllib2.urlopen(req)
            fanhui = res.read()
            if fanhui == 'ok':
                pass
            else:
                n += 1
    except:
        n+=1

def main():
    data_queue1 = []  # 用来装所有的调取selectinfo接口的线程
    data_queue2 = []  # 用来装所有的调取storeinfo接口的线程
    p = Pool(processes=10)  # 并发数量为10

    for x in range(1,100):
        data_queue1.append(p.apply_async(fn))
    for y in range(101,201):
        data_queue2.append(p.apply_async(ff))

    pid = os.fork()
    if pid == 0:
        p.close()
        global m
        for x in data_queue1:
            x.get()
        print '执行selectinfo接口调取完成，出现错误数量为：'+m
        
    else:
        p.close()
        global n
        for y in data_queue2:
            y.get()
        print '执行storeinfo接口调取完成，出现错误数量为：'+n

if __name__ == '__main__':
    main()





