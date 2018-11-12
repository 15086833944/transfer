#!/usr/bin/env python
# -*- coding:utf-8 -*-
#wirte by: LiuDeQian
#data: 2018.10.30
#work env: python2.7+Oracle(cx_Oracle)+flask

'''
功能说明：主要为3个模块
模块1 → selectinfo模块为agent提供接口，需接收到调用者的ip信息，为调用者反馈数据库中该主机相关的所有进程信息。
模块2 → getinfo模块主要是为agent提供的接口，保存agent传送的报警信息，记录到文件中
模块3 → transfer模块主要是信息转接的作用，接收到proxy传输的host_id信息后，将该信息传送给对应的agent主机。
       目前设计每次最多可接收并处理proxy发送来的2000个host_id数据信息。
'''

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

# 日志记录
LOG_FILE = "/home/opvis/transfer_server/log/transfer.log"
if not os.path.exists('/home/opvis/transfer_server/log'):
    os.makedirs('/home/opvis/transfer_server/log/')
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

@app.route('/selectinfo/<ips>',methods=['POST','GET'])
# 查询数据库接口，将数据传给agent
def selectinfo(ips):
    ip_list=ips.strip("'").strip('"').split(',')
    print 'start to be invoked ......'
    print ip_list
    try:
        db = cx_Oracle.connect('umsproxy', 'ums1234', '172.30.130.126:1521/umsproxy')
        cur = db.cursor()
        count = 0
        for ip in ip_list:
            # print ip
            cur.execute("select id from cmdb_host where biz_ip='%s'"%ip)
            host_id = cur.fetchall()
            # print host_id
            if host_id:
                count += 1
                cur.execute("select process_name,key_word,trigger_cycle_value,trigger_value from cmdb_host_process where host_id = %s"%host_id[0][0])
                infos = cur.fetchall()  #得到所有hostid相关的进程信息，元祖
                # print infos
                if infos:
                    # 将查询内容反馈给agent
                    D = {}  # 用来装一个进程的信息
                    L = []  # 用来装所有进程信息
                    for x in infos:
                        D['ip'] = ip
                        D['process_name'] = x[0]
                        D['key_word'] = x[1]
                        D['trigger_cycle_value'] = x[2]
                        D['trigger_value'] = x[3]
                        L.append(D)
                    cur.close()
                    db.close()
                    print 'success to be invoked !'
                    return json.dumps(L)
                    # 反馈给调用者的信息格式：‘[{'ip':mm,'process_name':xx,'key_word':yy,'trigger_cycle_value':zz,'trigger_value':nn},
                    #                       {'ip':mm,'process_name':xx,'key_word':yy,'trigger_cycle_value':zz,'trigger_value':nn},
                    #                       ......]’
                # 如果Agent能找到对应的host_id,但找不到对应的进程信息，则返回提示
                else:
                    print 'No data error 1 --> with agent ips, cmdb_host table has host_id info, but no process info in cmdb_host_process table！'
                    logger.info('No data error 1 --> with agent ips, cmdb_host table has host_id info, but no process info in cmdb_host_process table！')
                    return 'No data error 1 --> with agent ips, cmdb_host table has host_id info, but no process info in cmdb_host_process table！'
            else:
                continue
        # 如果Agent所有ip都没有找到对应的host_id，则返回提示
        if count == 0:
            print 'No data error 2 --> there is no host_id info from cmdb_host table with agent ips !'
            logger.info('No data error 2 --> there is no host_id info from cmdb_host table with agent ips !')
            return 'No data error 2 --> there is no host_id info from cmdb_host table with agent ips !'
    except Exception as e:
        print e
        logger.info(' selectinfo module connect to Oracle db has error:'+str(e))
        cur.close()
        db.close()


@app.route('/getinfo/',methods=['POST'])
# 记录agent传过来的异常信息, 将信息记录到文件
def getinfo():
    if request.method == 'POST':
        msg = request.form.get('name')
        #接收agent传送的信息写入文件
        msgs = ''
        msgs += ' error_time:' + str(datetime.datetime.today())
        msgs += ' error_msg' + msg + '\n'
        with open('/home/opvis/transfer_server/log/agent_warning.log', 'a') as f:
            if not os.path.exists('/home/opvis/transfer_server/log/'):
                os.makedirs('/home/opvis/transfer_server/log/')
            f.write(msgs)


# 循环接收proxy传来的信息
def transfer():
    HOST = '0.0.0.0'
    PORT = 9994
    ADDR = (HOST,PORT)
    try:
        sockfd = socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
        sockfd.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
        sockfd.bind(ADDR)
    except Exception as e:
        logger.info('create UDP socket error:'+str(e))
    else:
        while True:
            #循环接收proxy传来的信息,收到的是json串
            data,addr = sockfd.recvfrom(10240)
            if data:
                print 'already receive msg, start to trans !'
                # 每次收到消息后新建一个子进程来执行传输，避免UDP消息冲突
                pid = os.fork()
                if pid == 0:
                    do_trans(sockfd,data)
                    sys.exit()
                else:
                    continue

# 具体执行传输任务
def do_trans(sockfd,data):
    print 'get host_ids from proxy:'+data
    hostIds = json.loads(data)
    try:
        db = cx_Oracle.connect('umsproxy', 'ums1234', '172.30.130.126:1521/umsproxy')
        cur = db.cursor()
        # 遍历所有hostid,将每个每个hostid对应的agent ip地址查询出来后， 再将信息以udp方式传送给agent.
        for hostid in hostIds:
            print 'start to select host_id: '+str(hostid)
            cur.execute("select biz_ip from cmdb_host where id=%d" % hostid)
            agent_ip = cur.fetchall()
            print agent_ip
            if not agent_ip:
                logger.info('the cmdb_host has no biz_ip about hostid:'+str(hostid))
                print 'the cmdb_host has no biz_ip about hostid:'+str(hostid)
            else:
                msg = {"pststus":7,'host_id':hostid, 'ip':agent_ip[0][0]}
                agent_ip_port = ('172.30.130.126', 9997)
                sockfd.sendto(json.dumps(msg), agent_ip_port)
                logger.info('the hostid:' + str(hostid) + ' info has already send to agent successed !')
                print 'the hostid:' + str(hostid) + ' info has already send to agent successed !'
    except Exception as e:
        print e
        logger.info('do_trans module connect to oracle db error:'+str(e))
    finally:
        cur.close()
        db.close()
        sockfd.close()


if __name__ == '__main__':
    pid = os.fork()
    if pid < 0:
        logger.info('create transfer child_process failed!')
    elif pid == 0:
        transfer()
    else:
        app.run(host='0.0.0.0',port=9995)


