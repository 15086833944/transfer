#!/usr/bin/env python
# -*- coding:utf-8 -*-
# wirte by: LiuDeQian
# data: 2018.10.30
# work env: python2.7+Oracle(cx_Oracle)+flask

'''
功能说明：主要为3个模块
模块1 → selectinfo模块为agent提供接口，需接收到调用者的ip信息，为调用者反馈数据库中该主机相关的所有进程信息。
模块2 → getinfo模块主要是为agent提供的接口，保存agent传送的报警信息，记录到文件中
模块3 → transfer模块主要是信息转接的作用，接收到proxy传输的host_id信息后，将该信息传送给对应的agent主机。
'''
import time
import sys
from flask import Flask, request

reload(sys)
sys.setdefaultencoding('utf8')


# 创建flask对象
app = Flask(__name__)


@app.route('/selectinfo/<ips>', methods=['POST', 'GET'])
# 查询数据库接口，将数据传给agent
def selectinfo(ips):
    time.sleep(2)
    return 'aaaaaaaaaaaaaaaaaa:'+str(ips)


@app.route('/storeinfo/', methods=['POST','GET'])
# 记录agent传过来的主机信息, 将信息记录到文件
def storeinfo():
    time.sleep(1)
    return 'bbbbb'


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=9995)


