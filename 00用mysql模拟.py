#!/usr/bin/env python
# -*- coding:utf-8 -*-

import os
import sys
import socket
from flask import Flask,request
import cx_Oracle
import json
import logging
from logging.handlers import TimedRotatingFileHandler
import datetime
reload(sys)
sys.setdefaultencoding('utf8')
import pymysql

# 日志记录
LOG_FILE = "/home/tarena/opvis/opvis_transfer/transfer_server/log/transfer.log"
logger = logging.getLogger()
logger.setLevel(logging.INFO)
fh = TimedRotatingFileHandler(LOG_FILE, when='D', interval=1, backupCount=30)
datefmt = '%Y-%m-%d %H:%M:%S'
format_str = '%(asctime)s %(levelname)s %(message)s '
formatter = logging.Formatter(format_str, datefmt)
fh.setFormatter(formatter)
logger.addHandler(fh)

# 创建flask对象
app = Flask(__name__)

@app.route('/selectinfo/<ips>')
# 查询数据库接口，将数据传给agent
def selectinfo(ips):
    ip_list=ips.strip("'").strip('"').split(',')
    print ip_list
    try:
        db = pymysql.connect(host='localhost',user='root',passwd='1234567',db='project01',charset='utf8')
        cur = db.cursor()
        logger.info('链接数据库成功，病创建了游标')
        logging.info('创建数据库成功了')
        for ip in ip_list:
            print ip
            cur.execute('select process_name,key_word,trigger_cycle_value from cmdb_host_process where host_id=(select id from cmdb_host where biz_ip="%s")'%str(ip))
            infos = cur.fetchall()  #得到所有hostid相关的进程信息，元祖
            print infos
            if infos:
                break
            else:
                continue
    except Exception as e:
        print '链接数据库有问题'
        print e
        logger.info('**********')
        logger.info(e)
        logger.info('**********')
    else:
        #将查询内容反馈给agent
        D={}   #用来装一个进程的信息
        L=[]   #用来装所有进程信息
        for x in infos:
            D['process_name']=x[0]
            D['key_word']=x[1]
            D['trigger_cycle_value']=x[2]
            L.append(D)
        cur.close()
        db.close()
        return json.dumps(L)  # 反馈给agent的信息格式：‘[{'process_name':xx,'key_word':yy,'trigger_cycle_value':zz},{'process_name':xx,'key_word':yy,'trigger_cycle_value':zz},...]’


@app.route('/getinfo/',methods=['POST'])
# 记录agent传过来的异常信息, 将信息记录到文件
def getinfo():
    if request.method == 'POST':
        msg = request.form.get('name')
        #接收agent传送的信息写入文件
        msgs = ''
        msgs += ' error_time:' + str(datetime.datetime.today())
        msgs += ' error_msg' + msg + '\n'
        with open('/home/opvis/opvis_transfer/transfer_server/log/agent_warning.log', 'a') as f:
            f.write(msgs)


# 接收proxy传来的信息，转接给agent
def transfer():
    HOST = '0.0.0.0'
    PORT = 9995
    ADDR = (HOST,PORT)
    try:
        sockfd = socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
        sockfd.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
        sockfd.bind(ADDR)
    except Exception as e:
        logger.info('creat UDP socket errer:',e)
        pass
    else:
        while True:
            #循环接收proxy传来的信息,收到的是json串
            data,addr = sockfd.recvfrom(1024)
            if data:
                hostIds = json.loads(data)
                try:
                    print hostIds
                    db = pymysql.connect(host='localhost',user='root',passwd='123456',db='project01',charset='utf8')
                    cur = db.cursor()
                    # 遍历所有hostid,将每个每个hostid对应的agent ip地址查询出来后， 再将信息以udp方式传送给agent.
                    for hostid in hostIds:
                        cur.execute('select biz_ip from cmdb_host where id=%s'%hostid)
                        agent_ip = cur.fetchall()
                        print agent_ip
                        if not agent_ip:
                            # logger.info('the cmdb_host has no biz_ip about hostid:',hostid)
                            print '没有数据'
                            pass
                        else:
                            agent_ip_port = ('127.0.0.1',8888)
                            print '传输开始，，，'
                            msg = [hostid,agent_ip[0][0]]
                            sockfd.sendto(json.dumps(msg), agent_ip_port)
                            print '已发送。。。。'
                            # logger.info('the hostid:'+hostid+'info has already send to agent!')
                            pass
                except Exception as e:
                    # logger.info('oracle db error:', e)
                    pass
                finally:
                    cur.close()
                    db.close()


if __name__ == '__main__':
    pid = os.fork()
    if pid < 0:
        # logger.info('create transfer child_process failed!')
        pass
    elif pid == 0:
        transfer()
    else:
        app.run(host='0.0.0.0',port=9995)


