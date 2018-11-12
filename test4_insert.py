#coding=utf-8


import cx_Oracle

conn = cx_Oracle.connect('umsproxy', 'ums1234', '127.0.0.1:1521/umsproxy')
print '连接成功!'
cursor = conn.cursor()

# 增加信息操作
# sql1 = "insert into cmdb_host values (666,11,22,33,44,'0','172.30.130.126','127.2.1.1','127.3.1.2',1,1,1,1,'0',1,1," \
#        "'0','0',1,'0',to_date('2018-11-01','yyyy-mm-dd'),'0',to_date('2018-11-01','yyyy-mm-dd'),'0',1,0,0,'0',1,'0','0','0','0',1,'0','0','0','0')"
sql2 = "insert into cmdb_host_process values (111113,666,'03test.py','03test.py',3,1,1,1,1,0,'aa','bb',to_date('2018-11-01','yyyy-mm-dd'),to_date('2018-11-01','yyyy-mm-dd'))"
# cursor.execute(sql1)
cursor.execute(sql2)

print '执行添加成功！'
cursor.close()
conn.commit()
conn.close()