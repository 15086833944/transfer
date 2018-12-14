import redis
import random

pool = redis.ConnectionPool(host='locahost',port=6379,decode_responses=True)
r = redis.Redis(connection_pool=pool)

for x in range(1,10):
    print x
    rkey = random.randint(100,200)
    print rkey
    r.set(rkey,x)
    print '111'
    r.expire(rkey,time=60)
    print '222'

# for y in r.keys():
#     print y