#!/bin/env python
# -*- coding:utf-8 -*-
import datetime

import cx_Oracle
import tornado.httpserver
import tornado.ioloop
import tornado.options
import tornado.web

import tornado.gen
from tornado.concurrent import run_on_executor
from concurrent.futures import ThreadPoolExecutor
import time
from tornado.options import define, options

import tornadoredis

import socket
from threading import Thread
import json
import sys,os
import logging
from logging.handlers import TimedRotatingFileHandler
reload(sys)
sys.setdefaultencoding('utf8')


# 日志记录
LOG_FILE = "/home/opvis/transfer_server/log/transfer.log"   #日志文档的地址
if not os.path.exists('/home/opvis/transfer_server/log'):   #如果没有这个路径的话自动创建该路径
    os.makedirs('/home/opvis/transfer_server/log/')
logger = logging.getLogger()                                #创建logging的实例对象
logger.setLevel(logging.INFO)                               #设置日志保存等级，低于INFO等级就不记录
fh = TimedRotatingFileHandler(LOG_FILE, when='D', interval=1, backupCount=30)  # 以day保存，间隔1天，最多保留30天的日志
datefmt = '%Y-%m-%d %H:%M:%S'                               #定义每条日志的时间显示格式
format_str = '%(asctime)s %(levelname)s %(message)s '       #定义日志内容显示格式
formatter = logging.Formatter(format_str, datefmt)          #定义日志前面显示时间， 后面显示内容
fh.setFormatter(formatter)                                  #执行定义
logger.addHandler(fh)                                       #执行定义

define("port", default=9995, type=int)

#设置连接池
CONNECTION_POOL = tornadoredis.ConnectionPool(max_connections=5000,wait_for_available=True)
c = tornadoredis.Client(host="127.0.0.1", port="6379",connection_pool=CONNECTION_POOL)

class selectinfo(tornado.web.RequestHandler):
    executor = ThreadPoolExecutor(2000)
    @tornado.gen.coroutine
    def post(self, *args, **kwargs):
        ips = self.get_body_arguments('ip')[0]
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
                        logger.info('selectinfo success to be invoked by ' + str(ip_list))
                        self.write(json.dumps(L))
                    # 如果Agent能找到对应的host_id,但找不到对应的进程信息，则返回提示
                    else:
                        logger.info(
                            'No data error 1 --> there is no process info in cmdb_host_process table with agent ips:' + str(
                                ip_list))
                        self.write('')
                else:
                    continue
            # 如果Agent所有ip都没有找到对应的host_id，则返回提示
            if count == 0:
                logger.info(
                    'No data error 2 --> there is no host_id info in cmdb_host table with this agent ips:' + str(
                        ip_list))
                self.write('')
        except Exception as e:
            logger.info(' selectinfo module connect to Oracle db has error:' + str(e))
            cur.close()
            db.close()
            self.write('')


class storeinfo(tornado.web.RequestHandler):
    @tornado.gen.coroutine
    def post(self, *args, **kwargs):
        process_id = self.get_body_arguments('id')[0]
        biz_ip = self.get_body_arguments('biz_ip')[0]
        manage_ip = self.get_body_arguments('manage_ip')[0]
        process_name = self.get_body_arguments('process_name')[0]
        key_word = self.get_body_arguments('key_word')[0]
        trigger_compare = self.get_body_arguments('trigger_compare')[0]
        trigger_value = self.get_body_arguments('trigger_value')[0]
        trigger_level = self.get_body_arguments('trigger_level')[0]
        trigger_cycle_value = self.get_body_arguments('trigger_cycle_value')[0]
        trigger_cycle_unit = self.get_body_arguments('trigger_cycle_unit')[0]
        should_be = self.get_body_arguments('should_be')[0]
        new_count = self.get_body_arguments('new_count')[0]
        current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        agent_send_time = self.get_body_arguments('current_time')[0]
        is_alarm = 0

        # 比对主机当前实际进程数与应该有的进程数
        if trigger_compare == 0:  # 如果用户设置的报警值为0，表示大于时触发
            if new_count > should_be:
                is_alarm = 1
        elif trigger_compare == 2:  # 如果用户设置的报警值为2，表示等于时触发
            if new_count == should_be:
                is_alarm = 1
        else:  # 如果设置为其他，表示小于时触发
            if new_count < should_be:
                is_alarm = 1

        # 如果agent传来的值都存在则进行后续操作
        if id and biz_ip and manage_ip and process_name and key_word and trigger_compare and trigger_value and (
                                    trigger_level and trigger_cycle_value and trigger_cycle_unit and should_be and new_count and current_time):
            # 接收agent传送的信息存入数据库
            try:
                db = cx_Oracle.connect('umsproxy', '"UMsproXY@)!*"', '127.0.0.1:1521/preumsproxy')
                cur = db.cursor()
                cur.execute("select is_alarm from process_info where process_id = {}".format(process_id))
                alarm_info = cur.fetchall()
                # 若不存在该报警值说明，该数据是新增的。需要执行添加操作
                if not alarm_info:
                    if is_alarm == 1:
                        logger.info('***报警值已触发！请注意！*** process_id:' + str(process_id) + ', biz_ip:' + str(
                            biz_ip) + ', agent_send_time:' + str(agent_send_time))
                        logger.info('此处需调用proxy接口，触发报警')
                    # 执行添加数据操作
                    sql1 = "insert into process_info values({},to_date('{}','yyyy-mm-dd hh24:mi:ss'),'{}','{}','{}',{},{},{},{},{},{},{},{})".format(
                        process_id, str(current_time), str(biz_ip), str(manage_ip), str(process_name), str(key_word),
                        trigger_compare, trigger_level,
                        trigger_cycle_value, trigger_cycle_unit, should_be, new_count, is_alarm)
                    cur.execute(sql1)

                # 若存在该报警值说明该数据需要更新， 当原报警值为0（正常）的情况下需要调用proxy的接口触发报警
                if alarm_info and alarm_info[0][0] == 0:
                    if is_alarm == 1:
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
                db.commit()
                cur.close()
                db.close()
                logger.info('storeinfo success to be invoked by ip:' + str(biz_ip))
                self.write('ok')
            except Exception as e:
                cur.close()
                db.close()
                logger.info('storeinfo module connect to oracle fail:' + str(e))
                self.write('transfer store info failed ! maybe some error has occur on the transfer,please check transfer!')
        else:
            logger.info('the data from agent_ip:' + str(biz_ip) + ', is not complete, so save info failed !')
            self.write('upload agent information failed ! maybe some data has been lost,please check agent!')


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
        logger.info('create UDP socket error:' + str(e))
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


# 定时遍历数据库，确认agent主机是否掉线
def check_agent():
    while True:
        # 每隔120秒执行一次
        time.sleep(120)
        try:
            now_time = datetime.datetime.now()
            db = cx_Oracle.connect('umsproxy', '"UMsproXY@)!*"', '127.0.0.1:1521/preumsproxy')
            cur = db.cursor()
            # 搜索所有的主机biz_ip
            cur.execute("select distinct biz_ip from process_info")
            all_process_ip = cur.fetchall()
            if all_process_ip:
                for x in all_process_ip:
                    # 每个主机biz_ip查询1条记录，通过这一条记录来判断主机是否在线
                    cur.execute("select * from process_info where biz_ip = '{}' and rownum = 1".format(x[0]))
                    info = cur.fetchall()
                    # 获取记录的时间与当前的时间差
                    time_diff = now_time - info[0][1]
                    if ',' in str(time_diff):
                        time_diff1 = str(time_diff).split(',')[1].split(':')
                    else:
                        time_diff1 = str(time_diff).split(':')
                    # 换算成秒钟来记录差时
                    time_diff2 = int(time_diff1[0]) * 3600 + int(time_diff1[1]) * 60 + int(float(time_diff1[2]))
                    if info[0][-3] == 0:  #监控周期为分钟的定时任务
                        time_cycle = info[0][-4]*60
                        if time_cycle + 60 < time_diff2:    #判断标准为监控周期 + 1分钟，若不在线则判断为失联状态
                            logger.info('---> 发现有主机失联！失联主机biz_ip: ' + info[0][2] + ', 判定数据来源于process_id:' + str(info[0][0]))
                        else:
                            continue
                    else:                 #监控周期为小时的定时任务
                        time_cycle = info[0][-4] * 3600
                        if time_cycle + 60 < time_diff2:    #判断标准为监控周期 + 1分钟，若不在线则判断为失联状态
                            logger.info('---> 发现有主机失联！失联主机biz_ip: ' + info[0][2] + ', 判定数据来源于process_id:' + str(info[0][0]))
                        else:
                            continue
            else:
                continue
        except Exception as e:
            logger.info('check_agent moudle has error: '+str(e))
        finally:
            cur.close()
            db.close()

# 定时每60秒查询一次当前端口的并发量并记录在文档里面
def check_count():
    while True:
        msg = os.popen('netstat -nat |grep 9995 |wc -l')
        count = msg.read()
        current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open('/home/opvis/transfer_server/log/check_count_'+str(datetime.date.today())+'.log', 'a') as f:
            f.write(current_time + ', 当前时间的并发访问量为：' + count)
        msg.close()
        time.sleep(60)

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

# 创建子进程来负责处理周期检查agent是否存在
def fn2():
    pid = os.fork()
    if pid < 0:
        logger.info('create check_agent child_process failed!')
    elif pid == 0:
        check_agent()


# 创建一个线程来循环执行检测端口的访问量
t = Thread(target=check_count)
t.setDaemon(True)
t.start()

daemon()
fn2()
fn1()

if __name__ == "__main__":
    tornado.options.parse_command_line()
    app = tornado.web.Application(handlers=[
            (r"/selectinfo/", selectinfo), (r"/storeinfo/", storeinfo)])
    http_server = tornado.httpserver.HTTPServer(app)
    http_server.listen(options.port)
    tornado.ioloop.IOLoop.instance().start()


