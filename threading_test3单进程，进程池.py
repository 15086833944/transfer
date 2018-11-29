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


# 调取selectinfo接口的函数
def fn():
    for x in range(1):
        try:
            req = urllib2.Request(url='http://127.0.0.1:9995/test/172.30.130.126')
            res = urllib2.urlopen(req)
            data = res.read()
            with open('fail.log', 'a') as f:
                if not data:
                    f.write('f'+'\n')
                else:
                    print '访问成功！'
        except:
            with open('fail.log', 'a') as f:
                f.write('f' + '\n')

def main():
    if os.path.exists('fail.log'):
        os.remove('fail.log')
    data_queue1 = []  # 用来装所有的调取selectinfo接口的线程
    p = Pool()  # 并发数量为10

    for x in range(1, 101):
        data_queue1.append(p.apply_async(fn))

    p.close()
    for x in data_queue1:
        x.get()

    with open('fail.log','r+') as fz:
        print '执行selectinfo接口调取完成，出现错误数量为：' + str(len(fz.readlines()))
    os.remove('fail.log')

if __name__ == '__main__':
    main()





