#coding=utf-8


import cx_Oracle

conn = cx_Oracle.connect('umsproxy', 'ums1234', '127.0.0.1:1521/umsproxy')
print '连接成功!'
cursor = conn.cursor()


sql3 = "delete from process_info where current_count=0"
cursor.execute(sql3)

print '执行删除成功！'
cursor.close()
conn.commit()
conn.close()