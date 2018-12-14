# # -*- coding: utf-8 -*-
import sys
import pandas
import matplotlib
matplotlib.use("Agg")
from matplotlib import pylab
reload(sys)
sys.setdefaultencoding('utf8')

file = sys.argv[1]
#X轴，Y轴数据
x=[]
y=[]
with open(file,'r') as f:
    for line in f.readlines():
        x.append(pandas.to_datetime(line.split(',')[0]))
        y.append(line.split(',')[1].split('：')[1].strip())

# pylab.gca().xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d %H:%M:%S"))
# pylab.gca().xaxis.set_major_locator(mdates.MonthLocator(interval=2))

pylab.plot(x,y)   #在当前绘图对象绘图（X轴，Y轴，蓝色虚线，线宽度）
pylab.xlabel("Time(m)") #X轴标签
pylab.ylabel("Count")  #Y轴标签
pylab.title("9994 port visitor volume") #图标题
# pylab.show()  #显示图
pylab.savefig("table.png") #保存图

