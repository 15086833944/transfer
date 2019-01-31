#!/usr/bin/env python
# -*- coding:utf-8 -*-
# write by: LiuDeQian
# data: 2018.10.30
# work env: python2.7+Oracle(cx_Oracle)+flask+gevent

import os
import subprocess
import sys
import re
import time
import datetime
from cloghandler import ConcurrentRotatingFileHandler
from gevent import monkey
from gevent.pywsgi import WSGIServer
import socket
from flask import Flask, request
import cx_Oracle
import json
import logging
from threading import Thread
from multiprocessing import Lock

reload(sys)
sys.setdefaultencoding('utf8')

# 日志路径
if not os.path.exists('/home/opvis/transfer_server/log/'):
    os.makedirs('/home/opvis/transfer_server/log/')
log_path = "/home/opvis/transfer_server/log/"
config_path = "/home/opvis/transfer_server/"

# 由于每个机房数据库账号密码不一样，所以需要确认数据库账号密码
db_user = ''
db_pwd = ''
db_name = ''
db_list = [('umsproxy','"UMsproXY@)!*"','preumsproxy'),  #南京测试用服务器10.181.45.7
           ('umsproxy','UMsproXY','devumsproxy'),  #南京测试用服务器10.181.45.6
           ('umsproxy','ums1234','umsproxy'),   #杭州机房 172.30.130.126
           ('umsproxy','ums1234','umstest'),   #北京机房 10.124.5.163
           ]
for x in db_list:
    try:
        conn = cx_Oracle.connect(x[0],x[1], '127.0.0.1:1521/'+x[2])
        db_user = x[0]
        db_pwd = x[1]
        db_name = x[2]
        conn.close()
        break
    except:
        continue

# 日志按照文件大小来切分,所有日志
logfile_info = log_path + "transfer.log"
info_filesize = 100*1024*1024
log_info = logging.getLogger()
info_handler = ConcurrentRotatingFileHandler(logfile_info, "a", info_filesize, encoding="utf-8",backupCount=30)
datefmt_str1 = '%Y-%m-%d %H:%M:%S'
format_str1 = '%(asctime)s-%(levelname)s-%(message)s '
formatter1 = logging.Formatter(format_str1, datefmt_str1)
info_handler.setFormatter(formatter1)
log_info.addHandler(info_handler)
log_info.setLevel(logging.INFO)

# error日志
logfile_error = log_path + "transfer_error.log"
error_filesize = 20*1024*1024
log_error = logging.getLogger()
error_handler = ConcurrentRotatingFileHandler(logfile_error, "a", error_filesize, encoding="utf-8",backupCount=30)
datefmt_str2 = '%Y-%m-%d %H:%M:%S'
format_str2 = '%(asctime)s-%(levelname)s-no.:%(lineno)d-%(message)s '
formatter2 = logging.Formatter(format_str2, datefmt_str2)
error_handler.setFormatter(formatter2)
log_error.addHandler(error_handler)
error_handler.setLevel(logging.ERROR)

monkey.patch_all()

# 创建flask对象
app = Flask(__name__)

@app.route('/selectinfo/', methods=['POST', 'GET'])
# 查询数据库接口，将数据传给agent
def selectinfo():
    ips = request.form.get('ip')
    ip_list = ips.split(',')[0:-1]
    try:
        db = cx_Oracle.connect(db_user,db_pwd,'127.0.0.1:1521/'+db_name)
        cur = db.cursor()
        count = 0
        for ip in ip_list:
            sql = "select id,biz_ip,manage_ip,process_name,key_word,trigger_compare,trigger_value,trigger_level," \
                  "trigger_cycle_value,trigger_cycle_unit from cmdb_host_process where biz_ip='{}' and is_alive=1".format(ip)
            cur.execute(sql)
            infos = cur.fetchall()
            if infos:
                # 将查询内容反馈给agent
                D = {}  # 用来装一个进程的信息
                L = []  # 用来装所有进程信息
                for x in infos:
                    D['id'] = x[0]
                    D['biz_ip'] = x[1]
                    D['manage_ip'] = x[2]
                    D['process_name'] = x[3]
                    D['key_word'] = x[4]
                    D['trigger_compare'] = x[5]
                    D['trigger_value'] = x[6]
                    D['trigger_level'] = x[7]
                    D['trigger_cycle_value'] = x[8]
                    D['trigger_cycle_unit'] = x[9]
                    L.append(D)
                    D = {}
                cur.close()
                db.close()
                logging.info('selectinfo success to be invoked by ' + str(ip_list))
                count += 1
                return json.dumps(L)
            else:
                continue
        # 如果所有ip都没能找到信息，则返回提示
        if count == 0:
            logging.info('No data --> there is no process info in cmdb_host_process table with agent ips:' + str(ip_list))
            return 'no data'
    except Exception as e:
        logging.error(' selectinfo module has error:' + str(e))
        return ''

@app.route('/storeinfo/', methods=['POST','GET'])
# 存储agent数据接口，记录agent传过来的主机信息
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
                        logging.error('***报警值已触发！请注意！*** process_id:' + str(process_id) + ', biz_ip:' + str(
                        biz_ip) + ', agent_send_time:' + str(agent_send_time))
            elif trigger_compare == 2:  # 如果用户设置的报警值为2，表示等于时触发
                if int(new_count) == int(should_be):
                    is_alarm = 1
                    if alarm_mode == 1:
                        logging.error('***报警值已触发！请注意！*** process_id:' + str(process_id) + ', biz_ip:' + str(
                        biz_ip) + ', agent_send_time:' + str(agent_send_time))
            else:                       # 如果设置为其他，表示小于时触发
                if int(new_count) < int(should_be):
                    is_alarm = 1
                    if alarm_mode == 1:
                        logging.error('***报警值已触发！请注意！*** process_id:' + str(process_id) + ', biz_ip:' + str(
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
                            logging.error('***报警值已触发！请注意！*** process_id:' + str(process_id) + ', biz_ip:' + str(
                                biz_ip) + ', agent_send_time:' + str(agent_send_time))
                        logging.error('此处是该接口第一次触发-----> 触发报警')
                    # 执行添加数据操作
                    sql1 = "insert into process_info values({},to_date('{}','yyyy-mm-dd hh24:mi:ss'),'{}','{}','{}',{}," \
                           "{},{},{},{},{},{},{},{})".format(process_id, str(current_time),str(biz_ip), str(manage_ip),
                            str(process_name), str(key_word), trigger_compare, trigger_level,trigger_cycle_value,
                            trigger_cycle_unit, should_be, new_count, is_alarm, is_alive)
                    cur.execute(sql1)

                # 若is_alive=1， 且存在该报警值说明该数据需要更新， 当原报警值为0（正常）的情况下需要调用proxy的接口触发报警
                elif alarm_info[0][1] == 1 and alarm_info[0][0] == 0:
                    if is_alarm == 1:
                        if alarm_mode == 2:
                            logging.error('***报警值已触发！请注意！*** process_id:' + str(process_id) + ', biz_ip:' + str(
                                biz_ip) + ', agent_send_time:' + str(agent_send_time))
                        logging.error('此处是该接口第一次触发-----> 触发报警')
                    sql2 = "update process_info set report_time = to_date('{}','yyyy-mm-dd hh24:mi:ss'),current_count = {}," \
                           "is_alarm = {} where process_id = {}".format(str(current_time), new_count, is_alarm, process_id)
                    cur.execute(sql2)

                # 若is_alive=1， 且存在该报警值说明该数据需要更新， 当原报警值为1（已报警）的情况下需要调用proxy的接口解除报警
                elif alarm_info[0][1] == 1 and alarm_info[0][0] == 1:
                    if is_alarm == 0:
                        logging.error('---报警已经解除！--- process_id:' + str(process_id) + ', biz_ip:' + str(
                            biz_ip) + ', agent_send_time:' + str(agent_send_time))
                        logging.error('此处是该接口最后一次触发-----> 解除报警')
                    sql3 = "update process_info set report_time = to_date('{}','yyyy-mm-dd hh24:mi:ss'),current_count = {}," \
                           "is_alarm = {} where process_id = {}".format(str(current_time), new_count, is_alarm, process_id)
                    cur.execute(sql3)

                # 若is_alive=0， 说明该数据是之前被删除监控的信息， 需要将原数据删掉后新增最新的数据
                elif alarm_info[0][1] == 0:
                    if is_alarm == 1:
                        if alarm_mode == 2:
                            logging.error('***报警值已触发！请注意！*** process_id:' + str(process_id) + ', biz_ip:' + str(
                                biz_ip) + ', agent_send_time:' + str(agent_send_time))
                        logging.error('此处是该接口第一次触发-----> 触发报警')
                    # 执行添加数据操作
                    sql4 = "delete from process_info where process_id = {}".format(process_id)
                    cur.execute(sql4)
                    sql5 = "insert into process_info values({},to_date('{}','yyyy-mm-dd hh24:mi:ss'),'{}','{}','{}',{}," \
                           "{},{},{},{},{},{},{},{})".format(process_id, str(current_time),str(biz_ip), str(manage_ip),
                            str(process_name), str(key_word), trigger_compare, trigger_level,trigger_cycle_value,
                            trigger_cycle_unit, should_be, new_count, is_alarm, is_alive)
                    cur.execute(sql5)
            else:
                logging.error('the data from agent_ip:' + str(biz_ip) +', process_id:'+ str(process_id) +
                            ', is not complete, so save info failed !')
                return 'upload agent information failed ! maybe some data has been lost,please check agent!'
        db.commit()
        cur.close()
        db.close()
        logging.info('storeinfo success to be invoked by ip:' + str(biz_ip))
        return 'ok'
    except Exception as e:
        logging.error('the storeinfo module has error:'+str(e))
        return 'transfer store info failed ! maybe some error has occur on the transfer,please check transfer!'

# 新增接口，查询agent的sudo权限是否被修改
@app.route('/check_agent_sudo/', methods=['POST', 'GET'])
def check_agent_sudo():
    agent_ip = request.form.get('ip')
    logging.error("the sudo privilege has been changed !"+" agent_ip:"+str(agent_ip))
    return "ok"

# 新增接口，接收agent在线调试的结果
@app.route('/online_debug/', methods=['POST', 'GET'])
def debug_online():
    id = request.form.get('id')
    result = request.form.get('result').strip()
    have_result = int(request.form.get('have_result'))
    update_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if id and have_result:
        # 存入数据库
        try:
            db = cx_Oracle.connect(db_user, db_pwd, '127.0.0.1:1521/' + db_name)
            cur = db.cursor()
            if have_result == 1:    # 如果正常执行完
                if result:          # 如果结果不为空时，更新结果， 状态， 和时间
                    clob_data = cur.var(cx_Oracle.CLOB)    #存入超过4000字节的大数据时，必须先将数据转换成clob对象
                    clob_data.setvalue(0,result)
                    sql1 = "update debug_online set execute_result=(:1),overt_alarm={},update_time=to_date('{}'," \
                           "'yyyy-mm-dd hh24:mi:ss') where flow_id='{}'".format(have_result,str(update_time),id)
                    pares = [result]
                    cur.execute(sql1,pares)
                else:               # 如果结果为空时， 更新状态， 和时间
                    sql1 = "update debug_online set overt_alarm={},update_time=to_date('{}','yyyy-mm-dd hh24:mi:ss')" \
                           " where flow_id='{}'".format(have_result,str(update_time),id)
                    cur.execute(sql1)
            elif have_result == 2:  # 如果超时后， 更新状态， 和时间
                sql1 = "update debug_online set overt_alarm={},update_time=to_date('{}','yyyy-mm-dd hh24:mi:ss')" \
                       " where flow_id='{}'".format(have_result,str(update_time), id)
                cur.execute(sql1)
            db.commit()
            cur.close()
            db.close()
            logging.info("already update debug_onine info of flow_id: {}".format(id))
            return "ok"
        except Exception as e:
            logging.error("the online_debug module has error:"+str(e))
            return 'online_debug result store failed ! please check the transfer'
    else:
        logging.error("the online_debug message has something wrong!")
        return "the online_debug message has something wrong!"

#新增接口，将在线调试的信息反馈给agent
@app.route('/debug_info/', methods=['POST', 'GET'])
def debug_info():
    id = request.form.get('id')
    if id:
        # 从数据库将该ID相关在线调试的信息查出来给agent
        try:
            db = cx_Oracle.connect(db_user, db_pwd, '127.0.0.1:1521/' + db_name)
            cur = db.cursor()
            sql1 = "select execute_time,data from debug_online where flow_id='{}'".format(id)
            cur.execute(sql1)
            info = cur.fetchall()
            if info:
                execute_time = info[0][0]
                data = info[0][1].read().replace('\r','')
                total_info = {
                    "execute_time":execute_time,
                    "data":data,
                }
                cur.close()
                db.close()
                logging.info('the debug_online info use HTTP return to agent successful!')
                return json.dumps(total_info)
            else:
                cur.close()
                db.close()
                logging.error('the database has no debug_info of flow_id:{}'.format(id))
                return 'the database has no debug_info of flow_id:{}'.format(id)
        except Exception as e:
            logging.error("the debug_info module has error:"+str(e))
            return 'debug_info search info failed ! please check the transfer'


# 新增接口，接收agent定点监控的结果
@app.route('/fixed_point_result/', methods=['POST', 'GET'])
def fixed_point_result():
    id = request.form.get('id')
    result = request.form.get('result').strip()
    update_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if id:
        # 存入数据库
        if result:
            try:
                db = cx_Oracle.connect(db_user, db_pwd, '127.0.0.1:1521/' + db_name)
                cur = db.cursor()
                clob_data = cur.var(cx_Oracle.CLOB)  # 存入超过4000字节的大数据时，必须先将数据转换成clob对象
                clob_data.setvalue(0, result)
                sql1 = "update fixed_point_monitor set execute_result=(:1),update_time=to_date('{}'," \
                               "'yyyy-mm-dd hh24:mi:ss') where is_alive=1 and flow_id='{}'".format(str(update_time),id)
                pares = [result]
                cur.execute(sql1, pares)
                db.commit()
                cur.close()
                db.close()
                logging.info("already update fixed_point_result info of flow_id:{} successful!".format(id))
                return "ok"
            except Exception as e:
                logging.error("the fixed_point_result module has error:" + str(e))
                return 'fixed_point_result result store failed ! please check the transfer'
        else:
            logging.info('the fixed_point_result is empty! flow_id:{}'.format(id))
    else:
        logging.error("the fixed_point_result message has something wrong!")
        return "the fixed_point_result message has something wrong!"

# 新增接口，将定点监控的信息反馈给agent
@app.route('/fixed_point_data/', methods=['POST', 'GET'])
def fixed_point_data():
    id = request.form.get('id')
    if id:
        # 从数据库将该ID相关在线调试的信息查出来给agent
        try:
            db = cx_Oracle.connect(db_user, db_pwd, '127.0.0.1:1521/' + db_name)
            cur = db.cursor()
            sql1 = "select execute_cycle,execute_data,collection_name from fixed_point_monitor where is_alive=1 and flow_id='{}'".format(id)
            cur.execute(sql1)
            info = cur.fetchall()
            if info:
                total_info = {
                    "execute_cycle": info[0][0],
                    "data": info[0][1].read().replace('\r',''),
                    "collection_name": info[0][2],
                }
                if "delete" in request.form:    #判断是否是执行删除定点任务时的调用
                    sql2 = "update fixed_point_monitor set is_alive=0 where flow_id='{}'".format(id)
                    cur.execute(sql2)
                    db.commit()
                cur.close()
                db.close()
                logging.info('the fixed_point_data info use HTTP return to agent successful!')
                return json.dumps(total_info)
            else:
                logging.error('the fixed_point_monitor database has no data of flow_id:{}'.format(id))
                return 'the fixed_point_monitor database has no data of flow_id:{}'.format(id)
        except Exception as e:
            logging.error("the fixed_point_data module has error:" + str(e))
            return 'fixed_point_data search info failed ! please check the transfer'


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
        logging.error('create transfer UDP socket error:' + str(e))
    else:
        while True:
            # 循环接收proxy传来的信息,收到的是json串
            data, addr = sockfd.recvfrom(4096)
            if data:
                # 每次收到消息后新建一个子进程来执行传输任务，避免UDP消息冲突而丢失数据
                pid = os.fork()
                if pid == 0:
                    logging.info('already receive message:' + str(data) + ' from proxy, start to transfer...... !')
                    do_trans(sockfd, data)
                    sys.exit(0)
                else:
                    continue

# 具体执行传输任务
def do_trans(sockfd, data):
    data = json.loads(data)
    status = data["status"]
    # 状态码为1时，新增监控进程
    if status == 1:
        try:
            biz_ip = data["biz_ip"]
            db = cx_Oracle.connect(db_user, db_pwd, '127.0.0.1:1521/' + db_name)
            cur = db.cursor()
            sql1 = "select * from cmdb_host_process where biz_ip='{}'".format(biz_ip)
            cur.execute(sql1)
            process_list = cur.fetchall()
            if not process_list:
                logging.error('the cmdb_host_process table has no process info about biz_id:' + biz_ip)
            else:
                msg = {"pstatus": 7,'ip': biz_ip}
                agent_ip_port = (biz_ip, 9997)
                sockfd.sendto(json.dumps(msg), agent_ip_port)
                logging.info('add monitor --> add info already use UDP send to the biz_ip:' + biz_ip + ' successful !')
        except Exception as e:
            logging.error('do_trans module status=1 , has error:' + str(e))
        finally:
            sockfd.close()

    # 状态码为2时，删除监控进程.
    # 将cmdb_host_process中的is_alive字段设置为0，这样agent就不会再获取该条监控信息
    # 将process_info表中的is_alive激活字段的值更改为0，agent上传保存的信息后会自动更新数据。
    elif status == 2:
        try:
            biz_ip = data["biz_ip"]
            id = data["process_id"]
            db = cx_Oracle.connect(db_user, db_pwd, '127.0.0.1:1521/' + db_name)
            cur = db.cursor()
            sql1 = "update cmdb_host_process set is_alive = 0 where id = {}".format(int(id))
            cur.execute(sql1)
            sql2 = "update process_info set is_alive = 0 where process_id = {}".format(int(id))
            cur.execute(sql2)
            db.commit()
            cur.close()
            db.close()
            logging.info('already delete process_id: ' + str(data["process_id"]) + ' info in DB successful!')
            msg = {"pstatus": 7, 'ip': biz_ip}
            agent_ip_port = (biz_ip, 9997)
            sockfd.sendto(json.dumps(msg), agent_ip_port)
            logging.info('dell monitor --> dell info already use UDP send to the biz_ip:' + biz_ip + ' successful !')

        except Exception as e:
            logging.error('do_trans module status=2 , has error:' + str(e))
        finally:
            sockfd.close()

    # 状态码为3时， 修改监控信息
    # 将process_info表中的is_alive激活字段的值更改为0，agent上传保存的信息后会自动更新数据。
    elif status == 3:
        try:
            biz_ip = data["biz_ip"]
            id = data["process_id"]
            db = cx_Oracle.connect(db_user, db_pwd, '127.0.0.1:1521/' + db_name)
            cur = db.cursor()
            sql1 = "update process_info set is_alive = 0 where process_id = {}".format(int(id))
            cur.execute(sql1)
            db.commit()
            cur.close()
            db.close()
            logging.info('already update process_id: ' + str(data["process_id"]) + ' info in DB successful!')
            msg = {"pstatus": 7, 'ip': biz_ip}
            agent_ip_port = (biz_ip, 9997)
            sockfd.sendto(json.dumps(msg), agent_ip_port)
            logging.info('update monitor --> update info already use UDP send to the biz_ip:' + biz_ip + ' successful !')
        except Exception as e:
            logging.error('do_trans module status=3 , has error:' + str(e))
        finally:
            sockfd.close()

    # 状态码为4时，表示需要执行在线调试功能
    elif status == 4:
        try:
            biz_ip = data["biz_ip"]
            msg = {'status':9, 'id':data["id"]}
            agent_ip_port = (biz_ip, 9997)
            sockfd.sendto(json.dumps(msg), agent_ip_port)
            logging.info("debug_online info use UDP send to agent:{} successful!".format(biz_ip))
        except Exception as e:
            logging.error('do_trans module status == 4 has error:' + str(e))

    # 状态码为5时， 表示需要 新增 定点调试功能
    elif status == 5:
        try:
            biz_ip = data["biz_ip"]
            msg = {'status':10, 'id':data["id"]}
            agent_ip_port = (biz_ip, 9997)
            sockfd.sendto(json.dumps(msg), agent_ip_port)
            logging.info("fixed_point_monitor add monitor info use UDP send to agent:{} successful!".format(biz_ip))
        except Exception as e:
            logging.error('do_trans module status == 5 has error:' + str(e))

    # 状态码为6时， 表示需要 删除 定点调试功能
    elif status == 6:
        try:
            biz_ip = data["biz_ip"]
            msg = {'status': 11, 'id': data["id"]}
            agent_ip_port = (biz_ip, 9997)
            sockfd.sendto(json.dumps(msg), agent_ip_port)
            logging.info("fixed_point_monitor delete monitor info use UDP send to agent:{} successful!".format(biz_ip))
        except Exception as e:
            logging.error('do_trans module status == 6 has error:' + str(e))

    # 状态码为7时， 表示需要 修改 定点调试功能
    elif status == 7:
        try:
            biz_ip = data["biz_ip"]
            msg = {'status': 12, 'id': data["id"]}
            agent_ip_port = (biz_ip, 9997)
            sockfd.sendto(json.dumps(msg), agent_ip_port)
            logging.info("fixed_point_monitor modify monitor info use UDP send to agent:{} successful!".format(biz_ip))
        except Exception as e:
            logging.error('do_trans module status == 7 has error:' + str(e))


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
#                             logging.info('---> 发现有主机失联！失联主机biz_ip: ' + info[0][2] + ', 判定数据来源于process_id:' + str(info[0][0]))
#                         else:
#                             continue
#                     else:                 #监控周期为小时的定时任务
#                         time_cycle = info[0][-4] * 3600
#                         if time_cycle + 60 < time_diff2:    #判断标准为监控周期 + 1分钟，若不在线则判断为失联状态
#                             logging.info('---> 发现有主机失联！失联主机biz_ip: ' + info[0][2] + ', 判定数据来源于process_id:' + str(info[0][0]))
#                         else:
#                             continue
#             else:
#                 continue
#         except Exception as e:
#             logging.info('check_agent moudle has error: '+str(e))
#         finally:
#             cur.close()
#             db.close()

# 定时默认每30秒查询一次当前端口的并发量并记录在文档里面
def check_count():
    # 查看配置文件，确定查看周期时间
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
        msg = os.popen('netstat -nat | grep 9995 |wc -l')     #linux系统下的端口访问量
        count = int(msg.read())
        current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(log_path+'check_count_msg'+str(datetime.datetime.today().strftime("%Y-%m-%d"))+'.log', 'a') as f:
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
        logging.error('create check_fail_msg UDP socket error:' + str(e))
    else:
        file_lock = Lock()
        while True:
            # 循环接收agent传来的信息,收到的是json串
            data, addr = sockfd.recvfrom(65507)
            if data:
                # 每次收到消息后新建一个子进程来执行传输任务，避免UDP消息冲突而丢失数据
                pid = os.fork()
                if pid == 0:
                    logging.info('already receive fail_msg from agent:' + str(addr[0]))
                    do_write_fail_msg(data,file_lock)
                    sys.exit(0)
                else:
                    continue

# 具体执行写入文件的任务，需要考虑同步互斥的问题,加锁
def do_write_fail_msg(data,file_lock):
    data = json.loads(data)
    with file_lock:
        with open(log_path+'agent_fail_msg'+str(datetime.datetime.today().strftime("%Y-%m-%d"))+'.log','a') as ff:
            for x in data:
                ff.write(x+'\n')

# 检测log文件，若超过30天就删除掉
def check_logfile():
    # 设置一个target_date标准为30天
    d1 = "2018-10-01"
    d2 = "2018-10-31"
    target_date = datetime.datetime.strptime(d2,'%Y-%m-%d')-datetime.datetime.strptime(d1,'%Y-%m-%d')
    while True:
        # 延时每天执行一次,测试时每分钟运行一次
        time.sleep(86400)
        file_list = os.listdir(log_path)
        if file_list:
            list_all = []  #得到需要进行管理的记录
            for x in file_list:
                if "msg" in x:
                    list_all.append(x)
            if list_all:
                for y in list_all:
                    try:
                        file_date = y.split("msg")[1].split(".")[0].strip()
                        now_date = datetime.datetime.today().strftime("%Y-%m-%d")
                        file_date_length = datetime.datetime.strptime(now_date,'%Y-%m-%d')-datetime.datetime.strptime(file_date,'%Y-%m-%d')
                        if file_date_length > target_date:
                            os.remove(log_path+y)
                            logging.info("delete log successful, which existed 30 days ago! file name: "+y)
                    except:
                        continue

# 创建守护进程,让该程序由系统控制，不受用户退出而影响
def daemon():
    try:
        pid1 = os.fork()
        if pid1 > 0:
            sys.exit(0)
    except Exception as e:
        logging.error("create first fork failed!"+str(e))
        sys.exit(1)
    os.chdir("/")
    os.setsid()
    os.umask(0)
    try:
        pid2 = os.fork()
        if pid2 > 0:
            sys.exit(0)
    except Exception as e:
        logging.error("create second fork failed!"+str(e))
        sys.exit(1)

# 创建子进程来负责处理proxy的信息
def fn1():
    pid = os.fork()
    if pid < 0:
        logging.error('create transfer child_process failed!')
    elif pid == 0:
        transfer()

# 创建子进程来循环接收agent传来的失败的记录信息
def fn2():
    pid = os.fork()
    if pid < 0:
        logging.error('create check_agent child_process failed!')
    elif pid == 0:
        check_fail_msg()

def main():
    # 调用创建子进程
    fn2()
    # 调用创建子进程
    fn1()

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
    # 为横向扩展设计的接口
    port = 9995
    try:
        port = sys.argv[1]
        try:
            port = int(port)
        except:
            print '端口输入有误，已将端口设置为默认端口号：9995'
            port = 9995
    except:
        pass
    print '------------------------------------'
    print '   http port:{} now has start!'.format(port)
    print '------------------------------------'
    # 调用创建守护进程
    daemon()
    # 判断是否已经有主程序启动,若没有就启动main()函数， 若有就不启动main(),方便后面进行flask端口横向扩展
    try:
        msg = 'ps aux|grep transfer_run|grep -v grep|wc -l'
        pipe = subprocess.Popen(msg, shell=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        process_count,err = pipe.communicate()
        if int(process_count) <= 3:
            main()
    except Exception as e:
        logging.error("__name__ has error: "+str(e))

    WSGIServer(('0.0.0.0', port), app).serve_forever()


