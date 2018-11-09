#coding=utf-8

import urllib
import urllib2

upload_data = {}
upload_data["process_name"] = "nginx"
upload_data["old_count"] = "2"
upload_data["new_count"] = "2"
upload_data["current_time"] = "2018-10-31 10:01:10"
upload_data["localip"] = "172.30.130.126"
upload_data = urllib.urlencode(upload_data)
print(upload_data)
get_process_url = "http://172.30.130.126:9995/getinfo/"+'?'+upload_data
req = urllib2.Request(get_process_url)
res = urllib2.urlopen(req)
get_data = res.read()
print(get_data)
