#!/usr/bin/env python
# -*- coding:utf-8 -*-
# write by: LiuDeQian
# data: 2018.10.30
# work env: python2.7+Oracle(cx_Oracle)+flask+gevent


import os
import datetime
import time
import sys
reload(sys)
sys.setdefaultencoding('utf8')

print datetime.date.today()
print datetime.datetime.now()


# 定时每60秒查询一次当前端口的并发量并记录在文档里面
def check_count():
    while True:
        msg = os.popen('netstat -nat |grep 9995 |wc -l')
        count = msg.read()
        current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open('check_count_'+str(datetime.date.today())+'.log', 'a') as f:
            f.write(current_time + ', 当前时间的并发访问量为：' + count)
        msg.close()
        time.sleep(60)

check_count()