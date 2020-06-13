import os, json
import sys

def get_ip():
    if not 'win' in sys.platform:
        # print('Come in get_ip!!! ')
        # ifconfig eth0 | grep 'inet' |grep -v '127.0.0.1'| grep -v 'inet6'|cut -d: -f2|awk '{print $2}' так работает ниже - нет
        # return (os.system("/sbin/ifconfig  | grep 'inet '| grep -v '127.0.0.1' | cut -d: -f2 | awk '{ print $1}'"))
        res = os.popen(
            "/sbin/ifconfig eth0 | grep 'inet' |grep -v '127.0.0.1'| grep -v 'inet6'|cut -d: -f2|awk '{print $2}'")
        return (res.read())
    return 'localhost'


def get_mask():
    if not 'win' in sys.platform:
        res = os.popen(
            "/sbin/ifconfig eth0 | grep 'inet' |grep -v '127.0.0.1'| grep -v 'inet6'|cut -d: -f2|awk '{print $4}'")
        return (res.read())
    return '255.255.255.0'

def get_gateway():
    if not 'win' in sys.platform:
        res = os.popen("netstat -rn | grep 0.0.0.0 | awk '{if (NR==1) print$2}'")
        return (res.read())
    return '192.168.0.254'

def get_hub(filePath):
    # filePath = path + 'ipconf.dat'
    data = {'hub': '0.0.0.0'}  # на случай, если файл не откроется
    try:
        with open(filePath, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except:
        print(u'не удалось считать файл насяйникэ мана!')
    return data['hub']  # возвращает hub


def get_settings_from_file(file_path):
    ''' gets settings from file'''
    # на случай, если файл не откроется
    data = {'hub': '0.0.0.0', "calibration":"[[200,100],[600,100],[600,500],[200,500]]"}  
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except:
        print(u'не удалось считать файл настроек settings.dat')
    return data  # возвращает json


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