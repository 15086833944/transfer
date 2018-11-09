import os
import urllib2
import time
import json

def fn1():
    url = 'http://127.0.0.1:9995/selectinfo/2222'
    req = urllib2.Request(url=url)
    res = urllib2.urlopen(req)
    data = res.read()
    time.sleep(1)
    print data

def fn2():
    url = 'http://127.0.0.1:9995/selectinfo/1111111111111'
    req = urllib2.Request(url=url)
    res = urllib2.urlopen(req)
    data = res.read()
    time.sleep(1)
    print data

pid=os.fork()
if pid==0:
    for x in range(20):
        fn1()
else:
    for x in range(20):
        fn2()


