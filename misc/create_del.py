import time
ts = time.time()
nu = 0#2000000
l1 =[]
wes = ['wewdwdwd' for i in range(10000)]
# print (len(wes))
for i in range(nu):
    l1=[]
    # l1.clear()
    l1.append(wes)
print (f'{time.time()-ts:.5f}')
# clear работает дольше чем создание нового объекта на 15%

li = {'a':2, "d":3, "w":4}
for i in li.values():
    # print(li.values())
    print(i)
