
import urllib
import urllib2

n=0

def ff():
    global n
    msg = {}
    msg["id"]=10000,
    msg["biz_ip"]="172.30.130.134",
    msg["manage_ip"]="172.30.130.134",
    msg["process_name"]="01test.py",
    msg["key_word"]="01test",
    msg["trigger_compare"]=3,
    msg["trigger_value"]=1,
    msg["trigger_level"]=1,
    msg["trigger_cycle_value"]=1,
    msg["trigger_cycle_unit"]=0,
    msg["should_be"]=1
    msg["new_count"]=1
    data = urllib.urlencode(msg)
    try:
        for y in range(10):
            req = urllib2.Request(url="http://172.30.130.126:9995/storeinfo/",data=data)
            res = urllib2.urlopen(req)
            fanhui = res.read()
            print fanhui
            if fanhui == 'ok':
                pass
            else:
                print fanhui
                n += 1
    except:
        n+=1

ff()