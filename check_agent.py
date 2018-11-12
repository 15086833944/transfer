#!/usr/bin/env python
# -*- coding:utf-8 -*-

import time
import cx_Oracle
import sys
import datetime

reload(sys)
sys.setdefaultencoding('utf8')


# 定时遍历数据库，确认agent主机是否掉线
def check_agent():
    while True:
        # 每隔60秒执行一次
        time.sleep(60)
        try:
            now_time = datetime.datetime.now()
            db = cx_Oracle.connect('umsproxy', 'ums1234', '172.30.130.126:1521/umsproxy')
            cur = db.cursor()
            cur.execute("select * from process_info")
            all_process_info = cur.fetchall()
            for x in all_process_info:
                time_diff = now_time - x[1]  #记录的时间与当前的时间差
                time_diff1 = str(time_diff).split(':')
                time_diff2 = int(time_diff1[0]) * 3600 + int(time_diff1[1]) * 60 + int(float(time_diff1[2]))  #以秒钟来记录差时
                if x[-3] == 0:  #按照分钟的定时
                    time_cycle = x[-4]*60
                    if time_cycle + 60 < time_diff2:    #判断buffer 1分钟
                        print '-----------------> 发现有主机失联！失联主机biz_ip:' + x[2]
                    else:
                        continue
                else:           #按照小时的定时
                    time_cycle = x[-4] * 3600
                    if time_cycle + 60 < time_diff2:    #判断buffer 1分钟
                        print '-----------------> 发现有主机失联！失联主机biz_ip:' + x[2]
                    else:
                        continue
        except Exception as e:
            print e
        finally:
            cur.close()
            db.close()
check_agent()


