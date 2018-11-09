#-*- coding:utf-8 -*-
import datetime

lm = []
lh = []
arg = 'cycle=1m'
j={"biz_ip": "172.30.130.126", "trigger_compare": 4, "key_word": "key", "process_name": "processname", "trigger_cycle_unit": 0,
"trigger_level": 343, "manage_ip": "127.3.1.2", "id": 377, "trigger_cycle_value": 1, "trigger_value": 32}
arg_number = arg.split("=")[1].replace("\n","")[-2:-1]
arg_time = arg.split("=")[1].replace("\n","")[-1:]
if arg_time == "m":
    if int(j["trigger_cycle_unit"]) == 0 and int(j["trigger_cycle_value"]) == int(arg_number):
      lm.append(j)
else:
    if int(j["trigger_cycle_unit"]) != 0 and int(j["trigger_cycle_value"]) == int(arg_number):
      lh.append(j)
print lm
print lh
print datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


b='a b' 
if ' ' in b:
    print '里面有空格'