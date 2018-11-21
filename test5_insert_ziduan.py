#coding=utf-8


import cx_Oracle

conn = cx_Oracle.connect('umsproxy', 'ums1234', '127.0.0.1:1521/umsproxy')
print '连接成功!'
cursor = conn.cursor()

# 增加信息操作
sql2 = "alter table process_info add (agent_send_time date)"
# cursor.execute(sql1)
cursor.execute(sql2)

print '执行添加字段成功！'
cursor.close()
conn.commit()
conn.close()