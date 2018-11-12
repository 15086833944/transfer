#coding=utf-8


import cx_Oracle

conn = cx_Oracle.connect('umsproxy', 'ums1234', '127.0.0.1:1521/umsproxy')
print '连接成功!'
cursor = conn.cursor()

sql3 = "select * from cmdb_host_process where host_id=666"
cursor.execute(sql3)

alldata = cursor.fetchall()
if alldata:
    for x in alldata:
        print x
else:
    print '没有搜索到数据。。。。。。。。'
print '执行查询成功！'


print '执行查询成功！'
cursor.close()
conn.commit()
conn.close()