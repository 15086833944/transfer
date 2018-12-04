#!/usr/bin/env python
# -*- coding:utf-8 -*-
# write by: LiuDeQian
# data: 2018.10.30
# work env: python2.7+Oracle(cx_Oracle)+flask+gevent

'''
功能说明：主要为4个模块
模块1 → selectinfo模块为agent提供接口，需接收到调用者的ip信息，为调用者反馈数据库中该主机相关的所有进程信息。
模块2 → storeinfo模块主要是为agent提供的接口，保存agent上报的数据，存入数据库。后期进行数据处理
模块3 → transfer模块主要是信息转接的作用，接收到proxy传输的host_id信息后，将该信息传送给对应的agent主机。
模块4 → check_agent模块主要是定时循环检测agent主机是否保持联系。每2分钟执行一次搜索，若主机在监控周期+1分钟后仍没有信息，则判定为失联。
模块5 → check_count模块主要是定时循环检测当前端口号9995的并发访问量是多少。每隔30秒触发一次
'''
import ast
import os
import sys
import re
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
from threading import Thread
from multiprocessing import Lock
# from flask_cache import Cache
# import urllib

reload(sys)
sys.setdefaultencoding('utf8')

# 日志记录
with open('transfer_config.txt','r') as f:
    msg = f.read()
    day = re.findall("log_save_time=\[(.*?)\]",msg)
    if day:
        try:
            day_value = int(day[0])
        except:
            day_value = 30
    else:
        day_value = 30

LOG_FILE = "/home/opvis/transfer_server/log/transfer.log"   #日志文档的地址
if not os.path.exists('/home/opvis/transfer_server/log'):   #如果没有这个路径的话自动创建该路径
    os.makedirs('/home/opvis/transfer_server/log/')
logger = logging.getLogger()                                #创建logging的实例对象
logger.setLevel(logging.INFO)                               #设置日志保存等级，低于INFO等级就不记录
fh = TimedRotatingFileHandler(LOG_FILE, when='D', interval=1, backupCount=day_value)  # 以day保存，间隔1天，最多保留30天的日志
datefmt = '%Y-%m-%d %H:%M:%S'                               #定义每条日志的时间显示格式
format_str = '%(asctime)s %(levelname)s %(message)s '       #定义日志内容显示格式
formatter = logging.Formatter(format_str, datefmt)          #定义日志前面显示时间， 后面显示内容
fh.setFormatter(formatter)                                  #执行定义
logger.addHandler(fh)                                       #执行定义

monkey.patch_all()

# 配置redis缓存
# cache = Cache()
# config = {
#     'CACHE_TYPE':'redis',
#     'CACHE_REDIS_HOST':'127.0.0.1',
#     'CACHE_REDIS_PORT':6379,
#     'CACHE_REDIS_DB':'',
#     'CACHE_REDIS_PASSWORD':''
# }
# 创建flask对象
app = Flask(__name__)
# app.config.from_object(config)
# cache.init_app(app,config)

# 设置redis缓存的键
# def redis_key():
#     key_vaule = str(time.time())
#     return key_vaule


@app.route('/selectinfo/', methods=['POST', 'GET'])
#@cache.cached(timeout=60*2,key_prefix=redis_key)
# 查询数据库接口，将数据传给agent
def selectinfo():
    ips = request.form.get('ip')
    ip_list = ips.split(',')[0:-1]
    # logger.info('selectinfo start to be invoked ......by'+str(ip_list))
    try:
        db = cx_Oracle.connect('umsproxy', '"UMsproXY@)!*"', '127.0.0.1:1521/preumsproxy')
        cur = db.cursor()
        count = 0
        for ip in ip_list:
            cur.execute("select id,biz_ip,manage_ip from cmdb_host where biz_ip='%s'" % ip)
            host_info = cur.fetchall()
            if host_info:
                count += 1
                cur.execute("select * from cmdb_host_process where host_id = %s" %
                    host_info[0][0])
                infos = cur.fetchall()
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
#@cache.cached(timeout=60*2,key_prefix=redis_key)
# 记录agent传过来的主机信息, 将信息记录到文件
def storeinfo():
    # 先确认报警模式
    with open('/home/opvis/transfer_server/transfer_config.txt', 'r') as f:
        msg = f.read()
        data = re.findall("alarm_mode=\[(.*?)\]", msg)
        if data:
            try:
                alarm_mode = int(data[0])
                if alarm_mode not in [1,2]:
                    alarm_mode = 1
            except:
                alarm_mode = 1
        else:
            alarm_mode = 1
    # 获取agent上传的信息
    total_msg = request.form.get('msg')
    total_msg_list = json.loads(total_msg)
    try:
        db = cx_Oracle.connect('umsproxy', '"UMsproXY@)!*"', '127.0.0.1:1521/preumsproxy')
        cur = db.cursor()
        biz_ip = ''
        # trigger_cycle_value = 0
        # trigger_cycle_unit = 0
        # process_id_list = []
        for msg in total_msg_list:
            process_id = msg.get('id')
            # process_id_list.append(process_id)
            biz_ip = msg.get('biz_ip')
            manage_ip = msg.get('manage_ip')
            process_name = msg.get('process_name')
            key_word = msg.get('key_word')
            trigger_compare = msg.get('trigger_compare')
            trigger_value = msg.get('trigger_value')
            trigger_level = msg.get('trigger_level')
            trigger_cycle_value = msg.get('trigger_cycle_value')
            trigger_cycle_unit = msg.get('trigger_cycle_unit')
            should_be = msg.get('should_be')
            new_count = msg.get('new_count')
            current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            agent_send_time = msg.get('current_time')
            is_alarm = 0

            # 比对主机当前实际进程数与应该有的进程数
            if trigger_compare == 0:    # 如果用户设置的报警值为0，表示大于时触发
                if int(new_count) > int(should_be):
                    is_alarm = 1
                    if alarm_mode == 1:
                        logger.info('***报警值已触发！请注意！*** process_id:' + str(process_id) + ', biz_ip:' + str(
                        biz_ip) + ', agent_send_time:' + str(agent_send_time))
            elif trigger_compare == 2:  # 如果用户设置的报警值为2，表示等于时触发
                if int(new_count) == int(should_be):
                    is_alarm = 1
                    if alarm_mode == 1:
                        logger.info('***报警值已触发！请注意！*** process_id:' + str(process_id) + ', biz_ip:' + str(
                        biz_ip) + ', agent_send_time:' + str(agent_send_time))
            else:                       # 如果设置为其他，表示小于时触发
                if int(new_count) < int(should_be):
                    is_alarm = 1
                    if alarm_mode == 1:
                        logger.info('***报警值已触发！请注意！*** process_id:' + str(process_id) + ', biz_ip:' + str(
                        biz_ip) + ', agent_send_time:' + str(agent_send_time))
            # 如果agent传来的值都存在则进行后续操作
            if process_id and biz_ip and manage_ip and process_name and key_word:
                # 接收agent传送的信息存入数据库
                cur.execute("select is_alarm from process_info where process_id = {}".format(process_id))
                alarm_info = cur.fetchall()
                # 若不存在该报警值说明，该数据是新增的。需要执行添加操作
                if not alarm_info:
                    if is_alarm == 1:
                        if alarm_mode == 2:
                            logger.info('***报警值已触发！请注意！*** process_id:' + str(process_id) + ', biz_ip:' + str(
                                biz_ip) + ', agent_send_time:' + str(agent_send_time))
                        logger.info('此处需调用proxy接口，触发报警')
                    # 执行添加数据操作
                    sql1 = "insert into process_info values({},to_date('{}','yyyy-mm-dd hh24:mi:ss'),'{}','{}','{}',{},{},{},{},{},{},{},{})".format(
                        process_id, str(current_time),str(biz_ip), str(manage_ip), str(process_name), str(key_word), trigger_compare, trigger_level,
                        trigger_cycle_value, trigger_cycle_unit, should_be, new_count, is_alarm)
                    cur.execute(sql1)

                # 若存在该报警值说明该数据需要更新， 当原报警值为0（正常）的情况下需要调用proxy的接口触发报警
                if alarm_info and alarm_info[0][0] == 0:
                    if is_alarm == 1:
                        if alarm_mode == 2:
                            logger.info('***报警值已触发！请注意！*** process_id:' + str(process_id) + ', biz_ip:' + str(
                                biz_ip) + ', agent_send_time:' + str(agent_send_time))
                        logger.info('此处需调用proxy接口-----> 触发报警')
                    sql2 = "update process_info set report_time = to_date('{}','yyyy-mm-dd hh24:mi:ss'),current_count = {},is_alarm = {} where process_id = {}".format(
                        str(current_time), new_count, is_alarm, process_id)
                    cur.execute(sql2)

                # 若存在该报警值说明该数据需要更新， 当原报警值为1（已报警）的情况下需要调用proxy的接口解除报警
                if alarm_info and alarm_info[0][0] == 1:
                    if is_alarm == 0:
                        logger.info('---报警已经解除！--- process_id:' + str(process_id) + ', biz_ip:' + str(
                            biz_ip) + ', agent_send_time:' + str(agent_send_time))
                        logger.info('此处需调用proxy接口-----> 解除报警')
                    sql3 = "update process_info set report_time = to_date('{}','yyyy-mm-dd hh24:mi:ss'),current_count = {},is_alarm = {} where process_id = {}".format(
                        str(current_time), new_count, is_alarm, process_id)
                    cur.execute(sql3)
            else:
                logger.info('the data from agent_ip:' + str(biz_ip) +', process_id:'+ str(process_id) +', is not complete, so save info failed !')
                return 'upload agent information failed ! maybe some data has been lost,please check agent!'

        # 若传送来的process_id比数据库的少， 说明是删除了监控项， 这时需要根据process_id同步减少process_info表中的进程信息
        # sql4 = "select process_id from process_info where biz_ip='{}' and trigger_cycle_value={} and trigger_cycle_unit={}".format(biz_ip,trigger_cycle_value,trigger_cycle_unit)
        # cur.execute(sql4)
        # process_id_info = cur.fetchall()
        # process_id_table =[]
        # for y in process_id_info:
        #     process_id_table.append(y[0])
        # difference = set(process_id_table) - set(process_id_list)
        # if difference:
        #     for diff_process_id in difference:
        #         sql5 = "delete from process_info where process_id={}".format(diff_process_id)
        #         print "sql5 = " + str(sql5)
        #         cur.execute(sql5)
        #         logger.info('process_id:'+str(diff_process_id)+', has been deleted from process_info table successful!'+' ip:' + str(biz_ip))
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

# 循环接收proxy传来的信息，完善信息后，将信息传送给agent
def transfer():
    HOST = '0.0.0.0'
    PORT = 9994
    ADDR = (HOST, PORT)
    try:
        sockfd = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sockfd.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sockfd.bind(ADDR)
    except Exception as e:
        logger.info('create transfer UDP socket error:' + str(e))
    else:
        while True:
            # 循环接收proxy传来的信息,收到的是json串
            data, addr = sockfd.recvfrom(4096)
            if data:
                logger.info('already receive host_id:'+str(data)+' from proxy, start to transfer...... !')
                # 每次收到消息后新建一个子进程来执行传输任务，避免UDP消息冲突而丢失数据
                pid = os.fork()
                if pid == 0:
                    do_trans(sockfd, data)
                    sys.exit()
                else:
                    continue

# 具体执行传输任务
def do_trans(sockfd, data):
    try:
        db = cx_Oracle.connect('umsproxy', '"UMsproXY@)!*"', '127.0.0.1:1521/preumsproxy')
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


# # 定时遍历数据库，确认agent主机是否掉线
# def check_agent():
#     #先确认循环检测周期时间
#     with open('/home/opvis/transfer_server/transfer_config.txt', 'r') as f:
#         msg = f.read()
#         data = re.findall("chenk_agent_cycle=\[(.*?)\]", msg)
#         if data:
#             try:
#                 chenk_cycle = int(data[0])
#                 if chenk_cycle < 60:
#                     chenk_cycle = 120
#             except:
#                 chenk_cycle = 120
#         else:
#             chenk_cycle = 120
#     while True:
#         # 每隔chenk_cycle秒执行一次
#         time.sleep(chenk_cycle)
#         try:
#             now_time = datetime.datetime.now()
#             db = cx_Oracle.connect('umsproxy', '"UMsproXY@)!*"', '127.0.0.1:1521/preumsproxy')
#             cur = db.cursor()
#             # 搜索所有的主机biz_ip
#             cur.execute("select distinct biz_ip from process_info")
#             all_process_ip = cur.fetchall()
#             if all_process_ip:
#                 for x in all_process_ip:
#                     # 每个主机biz_ip查询1条记录，通过这一条记录来判断主机是否在线
#                     cur.execute("select * from process_info where biz_ip = '{}' and rownum = 1".format(x[0]))
#                     info = cur.fetchall()
#                     # 获取记录的时间与当前的时间差
#                     time_diff = now_time - info[0][1]
#                     if ',' in str(time_diff):
#                         time_diff1 = str(time_diff).split(',')[1].split(':')
#                     else:
#                         time_diff1 = str(time_diff).split(':')
#                     # 换算成秒钟来记录差时
#                     time_diff2 = int(time_diff1[0]) * 3600 + int(time_diff1[1]) * 60 + int(float(time_diff1[2]))
#                     if info[0][-3] == 0:  #监控周期为分钟的定时任务
#                         time_cycle = info[0][-4]*60
#                         if time_cycle + 60 < time_diff2:    #判断标准为监控周期 + 1分钟，若不在线则判断为失联状态
#                             logger.info('---> 发现有主机失联！失联主机biz_ip: ' + info[0][2] + ', 判定数据来源于process_id:' + str(info[0][0]))
#                         else:
#                             continue
#                     else:                 #监控周期为小时的定时任务
#                         time_cycle = info[0][-4] * 3600
#                         if time_cycle + 60 < time_diff2:    #判断标准为监控周期 + 1分钟，若不在线则判断为失联状态
#                             logger.info('---> 发现有主机失联！失联主机biz_ip: ' + info[0][2] + ', 判定数据来源于process_id:' + str(info[0][0]))
#                         else:
#                             continue
#             else:
#                 continue
#         except Exception as e:
#             logger.info('check_agent moudle has error: '+str(e))
#         finally:
#             cur.close()
#             db.close()

# 定时每60秒查询一次当前端口的并发量并记录在文档里面
def check_count():
    with open('/home/opvis/transfer_server/transfer_config.txt', 'r') as f:
        msg = f.read()
        data = re.findall("traffic_triger_cycle=\[(.*?)\]", msg)
        if data:
            try:
                alarm_mode = int(data[0])
                if alarm_mode < 10 or alarm_mode > 60:
                    alarm_mode = 30
            except:
                alarm_mode = 30
        else:
            alarm_mode = 30
    while True:
        msg = os.popen('netstat -nat |grep 9995 |wc -l')
        count = msg.read()
        current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open('/home/opvis/transfer_server/log/check_count_'+str(datetime.date.today())+'.log', 'a') as f:
            f.write(current_time + ', 当前时间的访问量为：' + count)
        msg.close()
        time.sleep(alarm_mode)

# 搜集agent传输失败的信息
def check_fail_msg():
    HOST = '0.0.0.0'
    PORT = 9993
    ADDR = (HOST, PORT)
    try:
        sockfd = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sockfd.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sockfd.bind(ADDR)
    except Exception as e:
        logger.info('create check_fail_msg UDP socket error:' + str(e))
    else:
        lock = Lock()
        while True:
            # 循环接收proxy传来的信息,收到的是json串
            data, addr = sockfd.recvfrom(4096)
            if data:
                # 每次收到消息后新建一个子进程来执行传输任务，避免UDP消息冲突而丢失数据
                pid = os.fork()
                if pid == 0:
                    logger.info('already receive fail_msg from agent:' + str(addr[0]))
                    do_write_fail_msg(data,lock)
                    sys.exit()
                else:
                    continue

# 具体执行写入文件的任务，需要考虑同步互斥的问题,加锁
def do_write_fail_msg(data,lock):
    data = json.loads(data)
    with lock:
        with open('/home/opvis/transfer_server/log/agent_fail_msg'+str(datetime.date.today())+'.log','a') as ff:
            for x in data:
                x=json.loads(x)
                ff.write(json.dumps(x)+'\n')


# 创建守护进程,让该程序由系统控制，不受用户退出而影响
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

# 创建子进程来循环接收agent传来的失败的记录信息
def fn2():
    pid = os.fork()
    if pid < 0:
        logger.info('create check_agent child_process failed!')
    elif pid == 0:
        check_fail_msg()

daemon()
fn2()
fn1()

# # 创建一个线程来负责处理周期检查agent是否存在
# t1 = Thread(target=check_agent)
# t1.setDaemon(True)
# t1.start()

# 创建一个线程来循环执行检测端口的访问量
t2 = Thread(target=check_count)
t2.setDaemon(True)
t2.start()

if __name__ == '__main__':
    # app.run(host='0.0.0.0', port=9995)
    WSGIServer(('0.0.0.0', 9995), app).serve_forever()


