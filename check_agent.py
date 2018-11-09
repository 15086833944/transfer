#!/usr/bin/env python

import time
import cx_Oracle
import sys

reload(sys)
sys.setdefaultencoding('utf8')


# 定时遍历数据库，确认agent主机是否掉线
def check_agent():
    while True:
        # 每隔60秒执行一次
        time.sleep(60)
        try:
            db = cx_Oracle.connect('umsproxy', 'ums1234', '172.30.130.126:1521/umsproxy')
            cur = db.cursor()
            cur.execute("select * from process_info")
            all_process_info = cur.fetchall()
            print all_process_info
        except Exception as e:
            print e
        finally:
            cur.close()
            db.close()
check_agent()