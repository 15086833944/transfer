#!/usr/bin/env python
# -*- coding:utf-8 -*-
# wirte by: LiuDeQian
# data: 2018.10.30
# work env: python2.7+Oracle(cx_Oracle)+flask+gevent

'''
功能说明：主要为3个模块
模块1 → selectinfo模块为agent提供接口，需接收到调用者的ip信息，为调用者反馈数据库中该主机相关的所有进程信息。
模块2 → storeinfo模块主要是为agent提供的接口，保存agent上报的数据，存入数据库。后期进行数据处理
模块3 → transfer模块主要是信息转接的作用，接收到proxy传输的host_id信息后，将该信息传送给对应的agent主机。
'''

import os
import sys

import time

import datetime
from gevent import monkey
from gevent.pywsgi import WSGIServer
import socket
from flask import Flask, request
import cx_Oracle
import json
import logging
from logging.handlers import TimedRotatingFileHandler

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

monkey.patch_all()
# 创建flask对象
app = Flask(__name__)


@app.route('/selectinfo/<ips>', methods=['POST', 'GET'])
# 查询数据库接口，将数据传给agent
def selectinfo(ips):
    ip_list = ips.strip("'").strip('"').split(',')
    # logger.info('selectinfo start to be invoked ......by'+str(ip_list))
    try:
        db = cx_Oracle.connect('umsproxy', 'ums1234', '172.30.130.126:1521/umsproxy')
        cur = db.cursor()
        count = 0
        for ip in ip_list:
            cur.execute("select id,biz_ip,manage_ip from cmdb_host where biz_ip='%s'" % ip)
            host_info = cur.fetchall()
            if host_info:
                count += 1
                cur.execute("select * from cmdb_host_process where host_id = %s" %
                    host_info[0][0])
                infos = cur.fetchall()  # 得到所有hostid相关的进程信息，元祖
                if infos:
                    # 将查询内容反馈给agent
                    D = {}  # 用来装一个进程的信息
                    L = []  # 用来装所有进程信息
                    for x in infos:
                        D['id'] = x[0]
                        D['biz_ip'] = host_info[0][1]
                        D['manage_ip'] = host_info[0][2]
                        D['process_name'] = x[2]
                        D['key_word'] = x[3]
                        D['trigger_compare'] = x[4]
                        D['trigger_value'] = x[5]
                        D['trigger_level'] = x[6]
                        D['trigger_cycle_value'] = x[8]
                        D['trigger_cycle_unit'] = x[9]
                        L.append(D)
                        D = {}
                    cur.close()
                    db.close()
                    logger.info('selectinfo success to be invoked by '+str(ip_list))
                    return json.dumps(L)
                # 如果Agent能找到对应的host_id,但找不到对应的进程信息，则返回提示
                else:
                    logger.info('No data error 1 --> there is no process info in cmdb_host_process table with agent ips:'+str(ip_list))
                    return ''
            else:
                continue
        # 如果Agent所有ip都没有找到对应的host_id，则返回提示
        if count == 0:
            logger.info('No data error 2 --> there is no host_id info in cmdb_host table with this agent ips:'+str(ip_list))
            return ''
    except Exception as e:
        logger.info(' selectinfo module connect to Oracle db has error:' + str(e))
        cur.close()
        db.close()
        return ''


@app.route('/storeinfo/', methods=['POST','GET'])
# 记录agent传过来的主机信息, 将信息记录到文件
def storeinfo():
    # logger.info('storeinfo start to be invoked ......')
    process_id = request.form.get('id')
    biz_ip = request.form.get('biz_ip')
    manage_ip = request.form.get('manage_ip')
    process_name = request.form.get('process_name')
    key_word = request.form.get('key_word')
    trigger_compare = request.form.get('trigger_compare')
    trigger_value = request.form.get('trigger_value')
    trigger_level = request.form.get('trigger_level')
    trigger_cycle_value = request.form.get('trigger_cycle_value')
    trigger_cycle_unit = request.form.get('trigger_cycle_unit')
    should_be = request.form.get('should_be')
    new_count = request.form.get('new_count')
    current_time = datetime.datetime.now().strftime("%Y-%m=%d %H:%M:%S")
    # current_time = request.form.get('current_time')
    # 比对当前进程数与应该的进程数，若触发报警值则记录
    if trigger_compare == 0:
        if new_count > should_be:
            logger.info('************报警值已触发！请注意！************ process_id:' + str(process_id) + ' biz_ip:' + str(biz_ip))
    elif trigger_compare == 2:
        if new_count == should_be:
            logger.info('************报警值已触发！请注意！************ process_id:' + str(process_id) + ' biz_ip:' + str(biz_ip))
    else:
        if new_count < should_be:
            logger.info('************报警值已触发！请注意！************ process_id:' + str(process_id) + ' biz_ip:' + str(biz_ip))

    if id and biz_ip and manage_ip and process_name and key_word and trigger_compare and trigger_value and (
        trigger_level and trigger_cycle_value and trigger_cycle_unit and should_be and new_count and current_time):
        # 接收agent传送的信息写入文件
        # msgs = ''
        # msgs += ' process_id:' + str(process_id)                         #agent主机id
        # msgs += 'report_time:' + current_time                            #agent上传问题的时间,以transfer主机时间为准
        # msgs += ' biz_ip:' + str(biz_ip)                                 #业务ip
        # msgs += ' manage_ip:' + str(manage_ip)                           #管理ip
        # msgs += ' process_name:' + process_name                          #进程名称
        # msgs += ' key_word:' + key_word                                  #关键字
        # msgs += ' trigger_compare:' + str(trigger_compare)               #触发比较,0:大于，1：小于，2：等于
        # msgs += ' trigger_level:' + str(trigger_level)                   #警告等级
        # msgs += ' trigger_cycle_value:' + str(trigger_cycle_value)       #检测的时间周期
        # msgs += ' trigger_cycle_unit:' + str(trigger_cycle_unit)         #检测分钟还是小时
        # msgs += ' should_be_count:' + str(should_be)                     #触发值,agent应该有的进程数量
        # msgs += ' current_count:' + str(new_count)                       #当前agent主机的实际进程数量
        # try:
        #     with open('/home/opvis/transfer_server/log/agent_info_' + str(biz_ip) + '.log', 'a') as f:
        #         if not os.path.exists('/home/opvis/transfer_server/log/'):
        #             os.makedirs('/home/opvis/transfer_server/log/')
        #         # 读取文件信息，若不存在则添加
        #         f.write(msgs+'\n')
        #         f.close()
        #     logger.info('storeinfo success to be invoked by ip:' + str(biz_ip))
        #     return 'ok'
        # except Exception as e:
        #     logger.info('store info has error:' + str(e))
        #     return 'transfer store info failed ! maybe some error has occur on the transfer,please check transfer!'

        #接收agent传送的信息存入数据库
        try:
            db = cx_Oracle.connect('umsproxy', 'ums1234', '172.30.130.126:1521/umsproxy')
            cur = db.cursor()
            cur.execute("select * from process_info where process_id = {}".format(process_id))
            data = cur.fetchall()
            if not data:
                sql1 = "insert into process_info values({},to_date('{}','yyyy-mm-dd hh24:mi:ss'),'{}','{}','{}',{},{},{},{},{},{},{})".format(process_id,str(current_time),
                str(biz_ip),str(manage_ip),str(process_name),str(key_word),trigger_compare,trigger_level,trigger_cycle_value,trigger_cycle_unit,should_be,new_count)
                cur.execute(sql1)
            else:
                sql2 = "update process_info set report_time = to_date('{}','yyyy-mm-dd hh24:mi:ss'),current_count = {} where process_id = {}".format(str(current_time),new_count,process_id)
                cur.execute(sql2)
            db.commit()
            cur.close()
            db.close()
            logger.info('storeinfo success to be invoked by ip:' + str(biz_ip))
            return 'ok'
        except Exception as e:
            cur.close()
            db.close()
            logger.info('storeinfo module connect to oracle fail:'+str(e))
            return 'transfer store info failed ! maybe some error has occur on the transfer,please check transfer!'
        ##
    else:
        logger.info('the data from agent_ip:'+str(biz_ip)+', is not complete, so save info failed !')
        return 'upload agent information failed ! maybe some data has been lost,please check agent!'

# 循环接收proxy传来的信息
def transfer():
    HOST = '0.0.0.0'
    PORT = 9994
    ADDR = (HOST, PORT)
    try:
        sockfd = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sockfd.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sockfd.bind(ADDR)
    except Exception as e:
        logger.info('create UDP socket error:' + str(e))
    else:
        while True:
            # 循环接收proxy传来的信息,收到的是json串
            data, addr = sockfd.recvfrom(10240)
            if data:
                logger.info('already receive host_id:'+str(data)+' from proxy, start to transfer...... !')
                # 每次收到消息后新建一个子进程来执行传输，避免UDP消息冲突
                pid = os.fork()
                if pid == 0:
                    do_trans(sockfd, data)
                    sys.exit()
                else:
                    continue

# 具体执行传输任务
def do_trans(sockfd, data):
    try:
        db = cx_Oracle.connect('umsproxy', 'ums1234', '172.30.130.126:1521/umsproxy')
        cur = db.cursor()
        cur.execute("select biz_ip from cmdb_host where id=%d"%int(data))
        agent_ip = cur.fetchall()
        if not agent_ip:
            logger.info('the cmdb_host table has no ip info about hostid:' + str(data))
        else:
            msg = {"pstatus": 7, 'host_id': data, 'ip': agent_ip[0][0]}
            agent_ip_port = (agent_ip[0][0], 9997)
            sockfd.sendto(json.dumps(msg), agent_ip_port)
            logger.info('the hostid:' + str(data) + ' info has already send to agent successed !')
    except Exception as e:
        logger.info('do_trans module connect to oracle db error:' + str(e))
    finally:
        cur.close()
        db.close()
        sockfd.close()


# 定时遍历数据库，确认agent主机是否掉线
def check_agent():
    while True:
        # 每隔60秒执行一次
        time.sleep(60)
        try:
            now_time = datetime.datetime.now()
            db = cx_Oracle.connect('umsproxy', 'ums1234', '172.30.130.126:1521/umsproxy')
            cur = db.cursor()
            cur.execute("select biz_ip from process_info")
            all_process_ip = cur.fetchall()
            for x in set(all_process_ip):
                cur.execute("select * from process_info where biz_ip = '{}' limit 1".format(x[0]))
                info = cur.fetchall()
                time_diff = now_time - info[0][1]  #记录的时间与当前的时间差
                time_diff1 = str(time_diff).split(':')
                time_diff2 = int(time_diff1[0]) * 3600 + int(time_diff1[1]) * 60 + int(float(time_diff1[2]))  #以秒钟来记录差时
                if x[-3] == 0:  #按照分钟的定时
                    time_cycle = x[-4]*60
                    if time_cycle + 60 < time_diff2:    #判断buffer 1分钟
                        logger.info('-----------------> 发现有主机失联！失联主机biz_ip:' + x[2])
                    else:
                        continue
                else:           #按照小时的定时
                    time_cycle = x[-4] * 3600
                    if time_cycle + 60 < time_diff2:    #判断buffer 1分钟
                        logger.info('-----------------> 发现有主机失联！失联主机biz_ip:' + x[2])
                    else:
                        continue
        except Exception as e:
            print e
        finally:
            cur.close()
            db.close()


# 创建守护进程,让该程序由linux系统控制，不受用户退出而影响
def daemon():
    try:
        pid1 = os.fork()
        if pid1 > 0:
            sys.exit(0)
    except Exception as e:
        logging.info("create first fork failed!"+str(e))
        sys.exit(1)
    os.chdir("/")
    os.setsid()
    os.umask(0)
    try:
        pid2 = os.fork()
        if pid2 > 0:
            sys.exit(0)
    except Exception as e:
        logging.info("create second fork failed!"+str(e))
        sys.exit(1)

# 创建子进程来负责处理proxy的信息
def fn1():
    pid = os.fork()
    if pid < 0:
        logger.info('create transfer child_process failed!')
    elif pid == 0:
        transfer()

# 创建子进程来负责处理周期检查agent是否存在
def fn2():
    pid = os.fork()
    if pid < 0:
        logger.info('create check_agent child_process failed!')
    elif pid == 0:
        check_agent()

daemon()
fn1()
fn2()

if __name__ == '__main__':
    # app.run(host='0.0.0.0', port=9995)
    WSGIServer(('0.0.0.0', 9995), app).serve_forever()


