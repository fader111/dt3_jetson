import os, json
def get_ip():
    # print('Come in get_ip!!! ')
    # ifconfig eth0 | grep 'inet' |grep -v '127.0.0.1'| grep -v 'inet6'|cut -d: -f2|awk '{print $2}' так работает ниже - нет
    # return (os.system("/sbin/ifconfig  | grep 'inet '| grep -v '127.0.0.1' | cut -d: -f2 | awk '{ print $1}'"))
    res = os.popen(
        "/sbin/ifconfig eth0 | grep 'inet' |grep -v '127.0.0.1'| grep -v 'inet6'|cut -d: -f2|awk '{print $2}'")
    return (res.read())


def get_mask():
    res = os.popen(
        "/sbin/ifconfig eth0 | grep 'inet' |grep -v '127.0.0.1'| grep -v 'inet6'|cut -d: -f2|awk '{print $4}'")
    return (res.read())


def get_gateway():
    res = os.popen("netstat -rn | grep 0.0.0.0 | awk '{if (NR==1) print$2}'")
    return (res.read())


def get_hub(filePath):
    # filePath = path + 'ipconf.dat'
    data = {'hub': '0.0.0.0'}  # на случай, если файл не откроется
    try:
        with open(filePath, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except:
        print(u'не удалось считать файл насяйникэ мана!')
    return data['hub']  # возвращает hub

def get_bit_number_from_mask(mask):
    """ convert 255.255.255.0 to number of bits (24)"""
    # print('mask=',mask)
    result =0
    octets = mask.split(".")
    for oct in octets:
        if oct!='':
            for j in range (8):
                if (int(oct)&(2**j)):
                    result+=1
    return str(result)