#!/usr/bin/env python
# -*- coding:utf-8 -*-
# write by: LiuDeQian
# data: 2018.10.30
# work env: python2.7+Oracle(cx_Oracle)+flask+gevent

'''
功能说明：主要为7个模块,兼容linux系统和windows系统
模块1 → selectinfo为agent提供接口，需接收到调用者的ip信息，为调用者反馈数据库中该主机相关的所有进程信息。
模块2 → storeinfo为agent提供的接口，保存agent上报的数据，存入数据库。后期进行数据处理
模块3 → transfer模块主要是信息转接的作用，接收到proxy传输的信息后，将该信息传送给对应的agent主机.
模块4 → check_agent模块主要是定时循环检测agent主机是否保持联系。默认每2分钟执行一次搜索，若主机在监控周期+1分钟后仍没有信息，则判定为失联。
模块5 → check_count模块主要是定时循环检测当前端口号9995的并发访问量是多少。默认每隔30秒触发一次
模块6 → check_agent_sudo为agent提供的接口，agent检测sudu权限是否被修改，若被修改就会调用该接口上传被修改的agent主机的ip地址。
模块7 → check_logfile模块主要是每天检查一次访问量记录和丢失信息记录， 若超出1个月的就删掉。
'''

import os
import sys
import re
import platform
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
from multiprocessing import Lock,Process
# from flask_cache import Cache
# import urllib

reload(sys)
sys.setdefaultencoding('utf8')


# 确认系统是Windows还是Linux
if platform.system() == "Windows":
    if not os.path.exists("D:\\transfer_server\\log\\"):
        os.makedirs("D:\\transfer_server\\log\\")
    log_path = "D:\\transfer_server\\log\\"
    config_path = "D:\\transfer_server\\"
else:
    if not os.path.exists('/home/opvis/transfer_server/log/'):
        os.makedirs('/home/opvis/transfer_server/log/')
    log_path = "/home/opvis/transfer_server/log/"
    config_path = "/home/opvis/transfer_server/"

# 由于每个机房数据库账号密码不一样，所以需要确认数据库账号密码和库名
db_user = ''
db_pwd = ''
db_name = ''
db_list = [('umsproxy','"UMsproXY@)!*"','preumsproxy'),
           ('umsproxy','ums1234','umsproxy'),
           ('umsproxy','ums1234','umstest')]
for x in db_list:
    try:
        conn = cx_Oracle.connect(x[0],x[1], '127.0.0.1:1521/'+x[2])
        db_user = x[0]
        db_pwd = x[1]
        db_name = x[2]
        conn.close()
    except:
        continue

# 日志记录
# 先确认主日志保存时间，默认为30天
with open(config_path+'transfer_config.txt','a+') as f:
    msg = f.read()
    day = re.findall("log_save_time=\[(.*?)\]",msg)
    if day:
        try:
            day_value = int(day[0])
        except:
            day_value = 30
    else:
        day_value = 30
LOG_FILE = log_path + "transfer.log"   #日志文档的地址
logger = logging.getLogger()                                #创建logging的实例对象
logger.setLevel(logging.INFO)                               #设置日志保存等级，低于INFO等级就不记录
fh = TimedRotatingFileHandler(LOG_FILE, when='D', interval=1, backupCount=day_value) # 以day保存，间隔1天，最多保留30天的日志
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
        db = cx_Oracle.connect(db_user,db_pwd,'127.0.0.1:1521/'+db_name)
        cur = db.cursor()
        count = 0
        for ip in ip_list:
            cur.execute("select * from cmdb_host_process where biz_ip='{}'".format(ip))
            infos = cur.fetchall()
            if infos:
                # 将查询内容反馈给agent
                D = {}  # 用来装一个进程的信息
                L = []  # 用来装所有进程信息
                for x in infos:
                    D['id'] = x[0]
                    D['biz_ip'] = x[1]
                    D['manage_ip'] = x[14]
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
                logger.info('selectinfo success to be invoked by ' + str(ip_list))
                count += 1
                return json.dumps(L)
            else:
                continue
        # 如果所有ip都没能找到信息，则返回提示
        if count == 0:
            logger.info('No data error --> there is no process info in cmdb_host_process table with agent ips:' + str(ip_list))
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
    with open(config_path+'transfer_config.txt', 'a+') as f:
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
        db = cx_Oracle.connect(db_user, db_pwd, '127.0.0.1:1521/' + db_name)
        cur = db.cursor()
        biz_ip = ''
        for msg in total_msg_list:
            process_id = msg.get('id')
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
            is_alive = 1

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
                cur.execute("select is_alarm,is_alive from process_info where process_id = {}".format(process_id))
                alarm_info = cur.fetchall()
                # 若不存在这两个值说明，该数据是新增的。需要执行添加操作
                if not alarm_info:
                    if is_alarm == 1:
                        if alarm_mode == 2:
                            logger.info('***报警值已触发！请注意！*** process_id:' + str(process_id) + ', biz_ip:' + str(
                                biz_ip) + ', agent_send_time:' + str(agent_send_time))
                        logger.info('此处是该接口第一次触发-----> 触发报警')
                    # 执行添加数据操作
                    sql1 = "insert into process_info values({},to_date('{}','yyyy-mm-dd hh24:mi:ss'),'{}','{}','{}',{},{},{},{},{},{},{},{},{})".format(
                        process_id, str(current_time),str(biz_ip), str(manage_ip), str(process_name), str(key_word), trigger_compare, trigger_level,
                        trigger_cycle_value, trigger_cycle_unit, should_be, new_count, is_alarm, is_alive)
                    cur.execute(sql1)

                # 若is_alive=1， 且存在该报警值说明该数据需要更新， 当原报警值为0（正常）的情况下需要调用proxy的接口触发报警
                elif alarm_info[0][1] == 1 and alarm_info[0][0] == 0:
                    if is_alarm == 1:
                        if alarm_mode == 2:
                            logger.info('***报警值已触发！请注意！*** process_id:' + str(process_id) + ', biz_ip:' + str(
                                biz_ip) + ', agent_send_time:' + str(agent_send_time))
                        logger.info('此处是该接口第一次触发-----> 触发报警')
                    sql2 = "update process_info set report_time = to_date('{}','yyyy-mm-dd hh24:mi:ss'),current_count = {},is_alarm = {} where process_id = {}".format(
                        str(current_time), new_count, is_alarm, process_id)
                    cur.execute(sql2)

                # 若is_alive=1， 且存在该报警值说明该数据需要更新， 当原报警值为1（已报警）的情况下需要调用proxy的接口解除报警
                elif alarm_info[0][1] == 1 and alarm_info[0][0] == 1:
                    if is_alarm == 0:
                        logger.info('---报警已经解除！--- process_id:' + str(process_id) + ', biz_ip:' + str(
                            biz_ip) + ', agent_send_time:' + str(agent_send_time))
                        logger.info('此处是该接口最后一次触发-----> 解除报警')
                    sql3 = "update process_info set report_time = to_date('{}','yyyy-mm-dd hh24:mi:ss'),current_count = {},is_alarm = {} where process_id = {}".format(
                        str(current_time), new_count, is_alarm, process_id)
                    cur.execute(sql3)

                # 若is_alive=0， 说明该数据是之前被删除监控的信息， 需要将原数据删掉后新增最新的数据
                elif alarm_info[0][1] == 0:
                    if is_alarm == 1:
                        if alarm_mode == 2:
                            logger.info('***报警值已触发！请注意！*** process_id:' + str(process_id) + ', biz_ip:' + str(
                                biz_ip) + ', agent_send_time:' + str(agent_send_time))
                        logger.info('此处是该接口第一次触发-----> 触发报警')
                    # 执行添加数据操作
                    sql4 = "delete from process_info where process_id = {}".format(process_id)
                    cur.execute(sql4)
                    sql5 = "insert into process_info values({},to_date('{}','yyyy-mm-dd hh24:mi:ss'),'{}','{}','{}',{},{},{},{},{},{},{},{},{})".format(
                        process_id, str(current_time),str(biz_ip), str(manage_ip), str(process_name), str(key_word), trigger_compare, trigger_level,
                        trigger_cycle_value, trigger_cycle_unit, should_be, new_count, is_alarm, is_alive)
                    cur.execute(sql5)
            else:
                logger.info('the data from agent_ip:' + str(biz_ip) +', process_id:'+ str(process_id) +', is not complete, so save info failed !')
                return 'upload agent information failed ! maybe some data has been lost,please check agent!'
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

# 新增接口，查询agent的sudo权限是否被修改
@app.route('/check_agent_sudo/', methods=['POST', 'GET'])
def check_agent_sudo():
    agent_ip = request.form.get('ip')
    logger.info("the sudo privilege has been changed !"+" agent_ip:"+str(agent_ip))
    return "ok"

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
                logger.info('already receive message:'+str(data)+' from proxy, start to transfer...... !')
                # 每次收到消息后新建一个子进程来执行传输任务，避免UDP消息冲突而丢失数据
                pid = os.fork()
                if pid == 0:
                    do_trans(sockfd, data)
                    sys.exit()
                else:
                    continue

# 具体执行传输任务
def do_trans(sockfd, data):
    data = json.loads(data)
    status = data["status"]
    biz_ip = data["biz_ip"]
    # 状态码为1时，新增监控进程
    if status == 1:
        try:
            db = cx_Oracle.connect(db_user, db_pwd, '127.0.0.1:1521/' + db_name)
            cur = db.cursor()
            sql1 = "select * from cmdb_host_process where biz_ip='{}'".format(biz_ip)
            cur.execute(sql1)
            process_list = cur.fetchall()
            if not process_list:
                logger.info('the cmdb_host_process table has no process info about biz_id:' + biz_ip)
            else:
                msg = {"pstatus": 7,'ip': biz_ip}
                agent_ip_port = (biz_ip, 9997)
                sockfd.sendto(json.dumps(msg), agent_ip_port)
                logger.info('add monitor --> the biz_ip:' + biz_ip + ' info has already send to agent successed !')
        except Exception as e:
            logger.info('do_trans module status=1 , connect to oracle db error:' + str(e))
        finally:
            cur.close()
            db.close()
            sockfd.close()

    # 状态码为2时，删除监控进程
    # 状态码为3时，修改监控进程
    elif status == 2 or status == 3:
        try:
            db = cx_Oracle.connect(db_user, db_pwd, '127.0.0.1:1521/' + db_name)
            cur = db.cursor()
            sql1 = "select * from cmdb_host_process where biz_ip='{}'".format(biz_ip)
            cur.execute(sql1)
            process_list = cur.fetchall()
            if not process_list:
                logger.info('the cmdb_host_process table has no process info about biz_id:' + biz_ip)
            else:
                msg = {"pstatus": 7, 'ip': biz_ip}
                agent_ip_port = (biz_ip, 9997)
                sockfd.sendto(json.dumps(msg), agent_ip_port)
                if status == 2:
                    logger.info('dell monitor --> the biz_ip:' + biz_ip + ' info has already send to agent successed !')
                else:
                    logger.info('update monitor --> the biz_ip:' + biz_ip + ' info has already send to agent successed !')
            #删除掉process_info表中该进程的相关数据,实际是将is_alive激活字段的值更改为0
            #修改process_info表中该进程的相关数据,实际也是将is_alive激活字段的值更改为0,agent上传保存的信息后会自动更新数据
            sql2 = "update process_info set is_alive = 0 where process_id = {}".format(int(data["process_id"]))
            cur.execute(sql2)
            db.commit()
            if status ==2:
                logger.info('already delete process_id: ' + str(data["process_id"]) + ' from process_info table successful!')
            else:
                logger.info('already update process_id: ' + str(data["process_id"]) + ' from process_info table successful!')
        except Exception as e:
            logger.info('do_trans module status == 2 or status == 3, connect to oracle db error:' + str(e))
        finally:
            cur.close()
            db.close()
            sockfd.close()


# # 定时遍历数据库，确认agent主机是否掉线
# def check_agent():
#     #先确认循环检测周期时间
#     with open(config_path+'transfer_config.txt', 'a+') as f:
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
#             db = cx_Oracle.connect(db_user,db_pwd,'127.0.0.1:1521/'+db_name)
#             cur = db.cursor()
#             # 搜索所有的主机biz_ip
#             cur.execute("select distinct biz_ip from process_info")
#             all_process_ip = cur.fetchall()
#             if all_process_ip:
#                 for x in all_process_ip:
#                     # 每个主机biz_ip查询1条记录，通过这一条记录来判断主机是否在线
#                     cur.execute("select * from process_info where biz_ip = '{}' and is_alive = 1 and rownum = 1".format(x[0]))
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

# 定时默认每30秒查询一次当前端口的并发量并记录在文档里面
def check_count():
    with open(config_path+'transfer_config.txt', 'a+') as f:
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
        if platform.system() == "Windows":
            msg = os.popen('netstat -nat | find /c "9995"')       # Windows系统下的端口访问量
        else:
            msg = os.popen('netstat -nat | grep 9995 |wc -l')     #linux系统下的端口访问量
        count = int(msg.read())
        current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(log_path+'check_count_msg'+str(datetime.date.today())+'.log', 'a') as f:
            f.write(current_time + ', 当前时间的访问量为：' + str(count) + '\n')
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
        file_lock = Lock()
        while True:
            # 循环接收proxy传来的信息,收到的是json串
            data, addr = sockfd.recvfrom(4096)
            if data:
                # 每次收到消息后新建一个子进程来执行传输任务，避免UDP消息冲突而丢失数据
                pid = os.fork()
                if pid == 0:
                    logger.info('already receive fail_msg from agent:' + str(addr[0]))
                    do_write_fail_msg(data,file_lock)
                    sys.exit()
                else:
                    continue

# 具体执行写入文件的任务，需要考虑同步互斥的问题,加锁
def do_write_fail_msg(data,file_lock):
    data = json.loads(data)
    with file_lock:
        with open(log_path+'agent_fail_msg'+str(datetime.date.today())+'.log','a') as ff:
            for x in data:
                x=json.loads(x)
                ff.write(json.dumps(x)+'\n')

# 检测log文件，若超过1个月就删除掉(如：记录到3月后，就删掉1月的记录)
def check_logfile():
    while True:
        # 延时每天执行一次
        time.sleep(86400)
        file_list = os.listdir(log_path)
        list_all = []  #得到需要进行管理的记录
        delete_data_year = 0
        delete_data_month = 0
        for x in file_list:
            if "msg" in x:
                list_all.append(x)
        del_msg = 0
        month_list = []
        for y in list_all:
            data = y.split("msg")
            data_year = int(data[1][:4])
            data_month = int(data[1][5:7])
            month_list.append(data_month)
            if data_month == 1:
                delete_data_year = data_year-1
                delete_data_month = 11
            elif data_month == 2:
                delete_data_year = data_year - 1
                delete_data_month = 12
            elif data_month == 3:
                delete_data_year = data_year
                delete_data_month = 1
            elif data_month == 4:
                delete_data_year = data_year
                delete_data_month = 2
            elif data_month == 5:
                delete_data_year = data_year
                delete_data_month = 3
            elif data_month == 6:
                delete_data_year = data_year
                delete_data_month = 4
            elif data_month == 7:
                delete_data_year = data_year
                delete_data_month = 5
            elif data_month == 8:
                delete_data_year = data_year
                delete_data_month = 6
            elif data_month == 9:
                delete_data_year = data_year
                delete_data_month = 7
            elif data_month == 10:
                delete_data_year = data_year
                delete_data_month = 8
            elif data_month == 11:
                delete_data_year = data_year
                delete_data_month = 9
            elif data_month == 12:
                delete_data_year = data_year
                delete_data_month = 10
            if platform.system() == "Windows":
                order1 = "del " + log_path + "agent_fail_msg{0}-{1:02d}-*".format(delete_data_year, delete_data_month)
                order2 = "del " + log_path + "check_count_msg{0}-{1:02d}-*".format(delete_data_year, delete_data_month)
            else:
                order1 = "rm -rf "+log_path+"agent_fail_msg{0}-{1:02d}-*".format(delete_data_year,delete_data_month)
                order2 = "rm -rf "+log_path+"check_count_msg{0}-{1:02d}-*".format(delete_data_year,delete_data_month)
            if delete_data_month in month_list:
                del_msg = 1
            os.system(order1)
            os.system(order2)
        if del_msg == 1:
            logger.info("delete log successful, which existed one month ago! ")


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


def main():
    # 如果是在Window环境下就让程序在后台运行
    if platform.system() == "Windows":
        import win32api, win32gui
        ct = win32api.GetConsoleTitle()
        hd = win32gui.FindWindow(0,ct)
        win32gui.ShowWindow(hd,0)
    else:
        # 如果是在Linux环境下就调用创建守护进程
        daemon()

    # 创建子进程来负责处理proxy的信息
    p1 = Process(target=transfer)
    p1.daemon = True
    p1.start()

    # 创建子进程来循环接收agent传来的失败的记录信息
    p2 = Process(target=check_fail_msg)
    p2.daemon = True
    p2.start()

    # # 创建一个线程来负责处理周期检查agent是否存在
    # t1 = Thread(target=check_agent)
    # t1.setDaemon(True)
    # t1.start()

    # 创建一个线程来循环执行检测端口的访问量
    t2 = Thread(target=check_count)
    t2.setDaemon(True)
    t2.start()

    # 创建一个线程来循环执行检测log文档，超出1个月的就删掉
    t3 = Thread(target=check_logfile)
    t3.setDaemon(True)
    t3.start()

if __name__ == '__main__':
    main()
    WSGIServer(('0.0.0.0', 9995), app).serve_forever()


