#!/usr/bin/env python
# -*- coding:utf-8 -*-
import os
import sys
import urllib
import urllib2
from multiprocessing import Pool
import datetime


reload(sys)
sys.setdefaultencoding('utf8')


# 调取selectinfo接口的函数
def fn():
    for x in range(1):
        try:
            req = urllib2.Request(url='http://10.181.45.7:9995/selectinfo/172.30.130.126')
            res = urllib2.urlopen(req)
            data = res.read()
            with open('fail1.log', 'a') as f:
                if not data:
                    f.write('f')
                else:
                    print 'selectinfo 调用成功！'
        except:
            with open('fail1.log', 'a') as f:
                f.write('m')


# 调取storeinfo接口的函数
def ff():
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
    msg["current_time"]=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    data = urllib.urlencode(msg)
    print data
    try:
        for y in range(1):
            req = urllib2.Request(url="http://10.181.45.7:9995/storeinfo/",data=data)
            res = urllib2.urlopen(req)
            fanhui = res.read()
            if fanhui == 'ok':
                print 'storeinfo ------调用成功！'
            else:
                with open('fail1.log', 'a') as f:
                    f.write('f')
    except:
        with open('fail1.log', 'a') as f:
            f.write('m')

def main():
    if not os.path.exists('fail1.log'):
        os.mknod('fail1.log')
    start_time = datetime.datetime.now()
    data_queue1 = []  # 用来装所有的调取接口的线程
    p1 = Pool(1)

    for x in range(1,2):
        data_queue1.append(p1.apply_async(ff))

    p1.close()
    for y in data_queue1:
        y.get()
    with open('fail1.log', 'r+') as fz:
        total_file = fz.readline()
        print '执行接口调取完成，出现错误数量为：' + str(len(total_file))
        print '其中http请求出现错误数量为：'+str(total_file.count('m'))
        print '其中数据库操作错误数量为：' + str(total_file.count('f'))

    os.remove('fail1.log')
    end_time = datetime.datetime.now()
    print '执行时长为：'+str(end_time-start_time)+'秒'


if __name__ == '__main__':
    main()





