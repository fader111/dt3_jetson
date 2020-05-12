""" GPIO pin5 -> GPIO pin7,  WDT for mainProcess reboot if mainProc crashes"""
# !/usr/bin/env python
# -*- coding: utf-8 -*-
import cProfile
import sys, os, time, cv2, socket
from flask import Flask, session, render_template, Response, request, json, jsonify, make_response
# from flask_session import Session
# from multiprocessing import Process, Queue, cpu_count #это фризит процесс.
from multiprocessing.dummy import Process, Queue
from threading import Timer
from carDetector import *
from werkzeug.contrib.fixers import ProxyFix
from functools import wraps, update_wrapper
from datetime import datetime
import requests
import logging

q_pict = Queue(maxsize=10)  # в очередь будем помещать картинки от камеры.
q_status = Queue(maxsize=10)  # очередь, в которую будем помещать статус рамок
q_tsNumber = Queue(maxsize=10)  # очередь, в которую будем помещать количество проехавших тс
q_ramki = Queue(maxsize=10)  # очередь где лежат рамки

frame = None # пустая картинка для генератора web картинки
app = Flask(__name__)

log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)  # выключает информационные сообщения flask оставляет только аварийные
url = 1  # тут вместо url номер камеры
winMode = 0
showMode = 0
ipStatus = {"ip": '192.168.0.100',  # удалить эту пургу отсюда нельзя, все валится
            "mask": '255.255.255.0',
            "gateway": '192.168.0.1',
            "hub": '192.168.0.39'
            }
linPath = '/home/pi/dt2/'  # путь к файлу проекта в linux
winPath = ''  # путь к файлу проекта в windows
path = ''  # итоговый, после определения в какой ос работаем, путь к файлам проекта

polygonesFilePath = 'polygones.dat'
tsNumberMinuteFilePath = 'minTSNumber.dat'
tsNumberHourFilePath = 'hourTSNumber.dat'
# параметры востановления настроек IP при зажимании пина 5
defaultIPConfFile = '/home/pi/dt2/ipconf.dat'
defaultIP = '192.168.0.31'
defaultMask = '255.255.255.0'
defaultGateway = '192.168.0.1'
defaultHub = '192.168.0.39'

tsNumbers = []  # массив с количеством задетектированных тс
tsNumbersPrev = []  # массив с количеством тс предыдущего шага, чтобы его вычитать из текущего и находить разницу
tsNumbersInterval = []  # массив с количеством тс за интервал (10с)[a,b,c,d]
tsNumbersMinute = []  # массив с количеством тс с проездами за 1 интервал за минуту [[_,_,_][][][]]
tsNumbersMinuteSumm = []  # массив с количеством тс за минуту [[][][][]]
tsNumbersHour = []  # массив с количеством тс с проездами за 1 интервал за час [[_,_,_][][][]]
tsNumbersHourSumm = []  # массив с количеством тс за час [[][][][]]

ramki = []
cicle = 0  # длительность цикла программы
lock = None  # блокировка потока
pict = None  # картинка главного процесса
colorStatus = []  # состояние рамои сработала-не сработала
adaptLearningRate = 0

capture = None


def nocache(view):
    @wraps(view)
    def no_cache(*args, **kwargs):
        response = make_response(view(*args, **kwargs))
        response.headers['Last-Modified'] = datetime.now()
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, post-check=0, pre-check=0, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '-1'
        return response

    return update_wrapper(no_cache, view)

def wdt_func(): #
    """Restart system if watch dog timer come out"""
    print ('save before reboot')
    ts = time.asctime( time.localtime(time.time()) )
    with open("/home/pi/dt2/detector.log", "a") as file:  # append reboot time to the log file
        print(ts, sep='\n ', file=file)
    os.system('sudo reboot')
    # os.system('sudo kill -9 `pidof sudo python3.6`') # restart python interpreter


def genWeb(): # отключено
    """Video streaming generator function."""
    global frame
    while True:
        out_frame = cv2.imencode('.jpg', frame)[1].tostring()
        # time.sleep(0.005)
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + out_frame + b'\r\n')
        if q_pict.qsize() > 0:
            frame = q_pict.get()


def gen(camera):
    """Video streaming generator function."""
    while True:
        frame = camera.get_frame()
        frame = cv2.imencode('.jpg', frame)[1].tostring()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')


@app.route('/video_feed')
@nocache
def video_feed():
    """Video streaming route. Put this in the src attribute of an img tag."""
    # return Response(genWeb(), # утекает память
    return Response(gen(Camera()),  # этот жрет больше ресурсов
                    mimetype='multipart/x-mixed-replace; boundary=frame')


# вызывается при старте и при изменении настроек IP в форме - устанавливает в linux новые

def putIPsettingsLinux(ip, mask, gateway):
    if not 'win' in sys.platform:
        print('sys.platform ', sys.platform, "\nip", ip, '\nmask', mask, '\ngateway', gateway)
        ipComm = os.popen("sudo ifconfig eth0 " + ip + " netmask " + mask)
        print('ipComm ', ipComm)
        routComm = os.popen("sudo route del default")
        gwComm = os.popen("sudo route add default gw " + gateway)
        ipComm.read()
        routComm.read()
        gwComm.read()
        print('before return ')
        return 0


@app.route("/get_my_ip", methods=["GET"])
def get_my_ip():
    return jsonify({'ip': request.remote_addr}), 200


@app.route('/sendPolyToServer',
           methods=['GET', 'POST'])  # это вызывается при нажатии на кнопку редактировать и отсылает полигоны на сервер
def sendPolyToServer():
    filePath = path + 'polygones.dat'
    if request.method == 'POST':
        print("request.get_data (poly)== ", request.get_data())
        polygones = request.form["req"]
        print('polygones=', polygones)
        if "polygones" in polygones:  # так надо проверять, т.к. иногда чушь посылает.
            print('polygones type IS RIGHT!')
            try:
                with open(filePath, 'w') as f:  # !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
                    f.write(polygones)  # Пишем данные полигонов в файл.
                print('settings saved! path=', path)
            except:
                print(u"Не удалось сохранить файл polygones.dat")

            return json.dumps('Polygones sent to server...')
        print('polygones type IS WRONG!')
        return json.dumps('Wrong data sent to server...')


@app.route('/getPolyFromServer', methods=['GET', 'POST'])
def getPolyFromServer():
    # print('polygonesFilePath = ',polygonesFilePath)
    polygones = None
    filePath = path + 'polygones.dat'
    print('filePath = ', path + 'polygones.dat')
    try:
        with open(filePath, 'r') as f:  # !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
            polygones = f.read()  # Пишем данные полигонов в файл.
    except:
        print(u"Не удалось прочитать файл polygones.dat")
    # print('считанные рамки = ',polygones)
    # return json.dumps(ramki)
    return json.dumps(polygones)


@app.route('/sendSettingsToServer',
           methods=['GET', 'POST'])  # это вызывается при нажатии на кнопку на форме и сохраняет параметры ip на сервере
def sendSettingsToServer():
    global ipStatus  # в теле меняется поле hub
    global detection_settings
    filePath_ipconf = path + 'ipconf.dat'
    filePath_config = path + 'config'
    if request.method == 'POST':
        # print("request.get_data from sendSettingsToServer: ", request.get_data())
        # session['username'] = 'I'
        # print('session=', sess)
        ip = request.form['ip']
        mask = request.form['mask']
        gateway = request.form['gateway']
        hub = request.form['hub']
        try:  # try тут нужен на случай, если в таблице в web где это будет задаваться, вместо int будет str или еще что
            ft = detection_settings["frame_tresh"] = int(request.form[
                                                             'detection_frame_tresh'])  # {"frame_tresh":20,"frame_hyst":10,"move_tresh":60,"move_hyst":58}
            fh = detection_settings["frame_hyst"] = int(request.form['detection_frame_hyst'])
            mt = detection_settings["move_tresh"] = int(request.form['detection_move_tresh'])
            # print('!!!!!!!mt = ', mt)
            mh = detection_settings["move_hyst"] = int(request.form['detection_move_hyst'])
        except:
            # pass
            print('exp from sendSettingsToServer')
    ipStatus["hub"] = hub
    # print('from python: ip', ip,'  mask',mask, '  gateway',gateway,'  hub',hub)
    with open(filePath_ipconf, 'w') as f:  # Открываем на чтение и запись.
        f.write(json.dumps({'ip': ip, 'mask': mask, 'gateway': gateway, 'hub': hub}))  # Пишем данные в файл.
        print('IP settings saved!')
    # print('sendSettingsToServer saved in path=', filePath_ipconf)
    if not winMode:  # если в линуксе сохраняем настройки IP и настройки детектора.
        putIPsettingsLinux(ip, mask, gateway)  # установка сетевых настроек Linux

    with open(filePath_config, 'w') as f:  # настройки детектора
        f.write(json.dumps(
            {'frame_tresh': detection_settings["frame_tresh"], 'frame_hyst': detection_settings["frame_hyst"], \
             'move_tresh': detection_settings["move_tresh"],
             'move_hyst': detection_settings["move_hyst"]}))  # Пишем данные в файл.
        print('detector settings saved in path=', filePath_config, 'data=', detection_settings)
    return json.dumps({'ip': ip, 'mask': mask, 'gateway': gateway, 'hub': hub, 'detection_frame_tresh': str(ft), \
                       'detection_frame_hyst': str(fh), \
                       'detection_move_tresh': str(mt), \
                       'detection_move_hyst': str(mh), \
                       })


@app.route('/showStatus', methods=['POST'])
def showStatus():
    if q_status.qsize()>0:
        colorStatus = q_status.get()
    if q_tsNumber.qsize() >0:
        tsNumbersMinuteSumm, tsNumbersHourSumm = q_tsNumber.get()  # [1,2,3,765]
    return json.dumps([colorStatus, tsNumbersMinuteSumm, tsNumbersHourSumm])


@app.route('/showTsTable', methods=['POST', 'GET'])
def showTsTable():
    if request.method == 'POST':
        pass
        # print("showTsTable")
    return render_template('tsNumberTable.html', len=len(ramki), tsNumbersMinuteSumm=tsNumbersMinuteSumm,
                           tsNumbersHourSumm=tsNumbersHourSumm)


@app.route('/showStatusHub', methods=['POST'])
def showStatusHub():
    # print('sendColorStatusToHub() ', sendColorStatusToHub())
    return json.dumps(sendHubStatusToWeb())


@app.route('/', methods=['GET', 'POST'])
# @app.route('/')
def index():
    global ipStatus
    global detection_settings
    global winMode
    # print('winMode=========== ',winMode ) # здесь настоящий winMode не виден, надо разобраться почему!!!
    hub = ipStatus['hub']
    if request.method == 'POST':
        hub = request.form['hub']  # сюда кажется не заходит
    if 'win' in sys.platform:  # в windows варианте все для теста
        # ip = socket.gethostbyname_ex(socket.gethostname())[2][1] # [2][2] - если торчит второй ethernet адаптер выдает второй по счету ip адрес среди прочих
        # ip = jsonify({'ip': request.remote_addr}), 200
        ip = request.remote_addr
        ipStatus = {
            # "ip": socket.gethostbyname_ex(socket.gethostname())[2][1], # [2][2] - если торчит выдает второй по счету ip адрес среди прочих
            "ip": ip,
            "mask": "255.255.255.0",  # это просто заглушки для теста
            "gateway": "192.168.0.1",
            "hub": hub
        }
    else:
        # ip = request.remote_addr
        ipStatus = {"ip": get_ip(),
                    "mask": get_mask(),
                    "gateway": get_gateway(),
                    "hub": get_hub()
                    }
    print("detection_settings from index:", detection_settings)
    # return render_template('index.html',title = '1',ipStatus = ipStatus,detection_settings=detection_settings)
    return render_template('index.html', ipStatus=ipStatus, detection_settings=detection_settings)


@app.route('/post_ts_number', methods=['GET', 'POST'])  # отвечает на post запрос о количестве машин
def post_ts_number():
    if request.method == 'POST':
        req = request.get_data()
        if "hour" in str(req):
            # print("hour asks",tsNumbersHourSumm)
            return json.dumps(tsNumbersHourSumm)
        if "minute" in str(req):
            # print("minuten asks",tsNumbersMinuteSumm)
            return json.dumps(tsNumbersMinuteSumm)
            # print("request.get_data()== ", request.get_data())
    return json.dumps("Wrong request")


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
    res = os.popen("netstat -rw | grep default | awk '{if (NR==1) print$2}'")
    return (res.read())


def get_hub():
    filePath = path + 'ipconf.dat'
    data = {'hub': '0.0.0.0'}  # на случай, если файл не откроется
    try:
        with open(filePath, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except:
        print(u'не удалось считать файл насяйникэ мана!')
    return data['hub']  # возвращает hub


def ipSetup():  # считывает настройки сети для интерфейса eth0 из файла и сует их в linux
    filePath = path + 'ipconf.dat'
    data = {"gateway": "192.168.0.1", "hub": "192.168.0.38", "ip": "192.168.0.31", "mask": "255.255.255.0"}
    try:
        with open(filePath, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except:
        print(u'Не удалось считать файл ipconf.dat ...')
    if not winMode:
        putIPsettingsLinux(data['ip'], data['mask'], data['gateway'])
    ipStatus["hub"] = data['hub']


def readDetectorSettings():  # считывает настройки детектора из файла и применяет их
    filePath = path + 'config'
    # print ('!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!filePath from readDetectorSettings = ',filePath)
    data = {'frame_tresh': 20, 'frame_hyst': 10,
            'move_tresh': 30, 'move_hyst': 25}
    try:
        with open(filePath, 'r', encoding='utf-8') as f:  # Пишем данные в файл.
            data = json.load(f)
        data['frame_tresh'] = int(data['frame_tresh'])  # в файле значения str- надо конвертать в int
        data['frame_hyst'] = int(data['frame_hyst'])
        data['move_tresh'] = int(data['move_tresh'])
        data['move_hyst'] = int(data['move_hyst'])
        # print('@@@@@!!!!!!!!!@@@@@@@@@data from  readDetectorSettings ==== ', data)
    except:
        print(u'Не удалось считать файл config подставлены значения по умолчанию...')
    return data


def set_Default_IP_Settings():
    """ воостанавливает дефолтные настройки IP при замыкании пина 5 на землю"""
    # print ("сработка set_Default_IP_Settings!!!")
    ts = time.time()

    while GPIO.input(7) == False:  # при замыкании кнопки
        # print("false")
        time.sleep(1)
        if (time.time() - ts > 2) & (not winMode):
            with open(defaultIPConfFile, 'w') as f:  # Открываем на чтение и запись.
                f.write(
                    json.dumps({'ip': defaultIP, 'mask': defaultMask, 'gateway': defaultGateway,
                                'hub': defaultHub}))  # Пишем данные в файл.
                print('default IP settings saved!')
            rebootComm = os.popen("sudo reboot")  # перезагружаем тушку
            rebootComm.read()
            # time.sleep(1)


def updatePolyFromServer(polygonesFilePath,
                         q_ramki):  # обновляет в периоде полигоы с сервера запускается таймером  раз в 5 сек
    global ramki, ramkiModes, ramkiDirections, dets, adaptLearningRate, pict, colorStatus, \
        colorStatusPrev, tsNumbers, tsNumbersPrev, tsNumbersInterval, tsNumbersMinute, tsNumbersMinuteSumm, tsNumbersHour, \
        tsNumbersHourSumm  # , capture
    ramkiUpd, ramkiModesUpd, ramkiDirectionsUpd = readPolyFile(polygonesFilePath)

    if (ramki != ramkiUpd or ramkiModes != ramkiModesUpd or ramkiDirections != ramkiDirectionsUpd):
        # проверяем новые рамки на наличие отрицательных значений
        print(u"Рамки обновлены на клиенте!")  # ,ramki, ramkiUpd)
        print(ramkiDirections)
        print(ramkiDirectionsUpd)
        for i in ramkiUpd:
            for j in i:
                for k in j:
                    if k <= 0:
                        print('negative Coordinates in polygones!!!!')
                        ######                        lock.release()  # отпуск блокировки
                        return  # если в рамках есть ошибка, нех ничо обновлять
        ramki = ramkiUpd[:]
        ramkiModes = ramkiModesUpd[:]
        ramkiDirections = ramkiDirectionsUpd[:]
        del dets
        dets = []  # будущие экземпляры класса detector
        while not q_ramki.empty():  # перед помещением в очередь чистим ее
            q_ramki.get()
        if not q_ramki.qsize() >= q_ramki.maxsize:
            q_ramki.put((ramki, ramkiModes, ramkiDirections))  # обновили очередь рамок.

        # Это было тут до перехода на процессы
        # for i in range(len(ramki)):  # в dets4 будут лежать объекты класса
        #     dets.append(detector(pict, ramki[i], i))
        #     if not 1 in ramkiDirections[i]:
        #         dets[i].noRamkiDirectionsFlag = 1 # если в рамке нет направлений, ставим флаг что нет направлений
        #     # for ramki1_4 in range(4):  # создание экземпляров класса детекторов по 4 в каждой рамке
        #     #     print ("ramki[ramka][ramki1_4]",ramki[ramka][ramki1_4])
        #     #     dets4[ramka].append(detector(pict, ramki4[ramka][ramki1_4], ramka))
        #     ###   print (ramki[i])
        #     dets[i].cos_alfa_calculator()


        adaptLearningRate = adaptLearningRateInit
        # ramkiMonitor = [0 for i in ramki]  # и все остальные рабочие массивы надо изменять, т.к. поменялось количество рамок
        colorStatus = [0 for i in ramki]  # массив в котором лежат цвета рамок текущего цикла
        colorStatusPrev = [0 for i in ramki]  # массив в котором лежат цвета рамок предыдущего цикла
        tsNumbers = [0 for i in ramki]  # массив в котором лежит числ проехавших тс
        tsNumbersPrev = [0 for i in ramki]  # массив в котором лежит числ проехавших тс за предыдущий промежуток времени
        tsNumbersInterval = [0 for i in ramki]  # и т.д. см инициализацию вначале программы
        tsNumbersMinute = [0 for i in ramki]
        tsNumbersMinuteSumm = [0 for i in ramki]
        tsNumbersHour = [0 for i in ramki]
        tsNumbersHourSumm = [0 for i in ramki]
        print('adaptLearningRate-------------', adaptLearningRate)
    if showMode:
        pass  # cv2.destroyAllWindows() # это не работает, окна плодятся безбожно.
    # if not winMode: # проверяем не нажат-ли пин восстановления дефол IP (только для Linux)
    if not 'win' in sys.platform:
        if ('arm' in os.popen("uname -m").read()):  # если запущено на малине
            set_Default_IP_Settings()


#####    lock.release() #отпуск блокировки

def sendHubStatusToWeb():
    hubAddress = ipStatus['hub']
    addrString = 'http://' + hubAddress + '/detect'
    # отладка поиск утечек
    # tr_initial.print_diff()
    try:
        requests.get(addrString, timeout=(0.1, 0.1))
        ans = requests.post(addrString, json={"cars_detect": colorStatus})
        # print('hub ',addrString,)
        return ans.text
    except:
        # print('expt from  sendHubStatusToWeb', )
        return 'Disconnected...'


def sendColorStatusToHub():  # передача состояний рамок на концентратор методом POST
    # def sendColorStatusToHub(hubAddress = '192.168.0.39:80'):
    hubAddress = ipStatus['hub']
    # print('hubAddress = ',hubAddress)
    addrString = 'http://' + hubAddress + '/detect'
    try:
        requests.get(addrString, timeout=(0.1, 0.1))
        ans = requests.post(addrString, json={"cars_detect": colorStatus})
        # print('hub ',addrString,)
        # return ans.text
    except:
        pass
        # print('expt from  sendColorStatusToHub', )
        # return 'Disconnected...'


def updTsNumsMinute(tsNumberMinuteFilePath):  # обновляет по тикеру tsNumbers и tsNumbersPrev
    global tsNumbers, tsNumbersPrev, tsNumbersMinute, tsNumbersMinuteSumm, tsNumbersInterval
    for i, mem in enumerate(tsNumbers):
        # print('tsNumbersMinuteSumm ', tsNumbersMinuteSumm)
        tsNumbersInterval[i] = mem - tsNumbersPrev[i]  # набиваем массив разницей за интервал (10 сек)
        tsNumbersPrev[i] = mem  # переписываем в предыдущий число из текущего
        # try:
        #    pass
        #    assert type(tsNumbersMinute[i])==list,'tsNumbersMinute ='+str(tsNumbersMinute) ### tsNumbersMinute[i] обязательно должен быть массивом
        # except IndexError:
        #    print (IndexError,tsNumbersMinute)
        if (type(tsNumbersMinute[i]) != list):
            tsNumbersMinute[i] = [0 for j in range(12)]
        tsNumbersMinute[i].append(tsNumbersInterval[i])  # добавляет в конец разницу за интервал
        tsNumbersMinute[i].pop(0)  # и выкидывает первый в очереди
        tsNumbersMinuteSumm[i] = sum(tsNumbersMinute[i])  # кладет сумму в массив где копятся проезды за минуту
        if mem > maxNumberTS:  # если количество посчитанных тс станет слишком велико, чтобы не отжирать память, сбрасывать его
            tsNumbers[i] -= maxNumberTS
            tsNumbersPrev[i] -= maxNumberTS
            # print('tsNumbers из updTsNumsMinute ',tsNumbers)
            # if (adaptLearningRate < 0.001):
            # os.system('cls')
            # print (tsNumbers)  # = [])  # массив с количеством задетектированных тс
            # print (tsNumbersPrev  # = [])  # массив с количеством тс предыдущего шага, чтобы его вычитать из текущего и находить разницу
            # print (tsNumbersInterval  # = [])  # массив с количеством тс за интервал (10с)[a,b,c,d]
            # print (tsNumbersMinute  # = [])  # массив с количеством тс с проездами за 1 интервал за минуту [[_,_,_][][][]]
            # print (tsNumbersMinuteSumm  # = [])  # массив с количеством тс за минуту [[][][][]]
            # writeFile(tsNumberMinuteFilePath, tsNumbersMinuteSumm)### запись файла в linux было раньше в версии php, больше не актуально


def updTsNumsHour(tsNumberHourFilePath):
    global tsNumbersHour, tsNumbersHourSumm
    for i, mem in enumerate(tsNumbers):
        # print('tsNumbersHour[',i,'] ', tsNumbersHour[i])
        if (type(tsNumbersHour[i]) != list):
            tsNumbersHour[i] = [0 for j in range(60)]
        tsNumbersHour[i].append(tsNumbersMinuteSumm[i])
        tsNumbersHour[i].pop(0)
        tsNumbersHourSumm[i] = sum(tsNumbersHour[i])
        # if (adaptLearningRate < 0.001):
        # os.system('cls')
        # print (tsNumbersHour)  # = []  # массив с количеством тс с проездами за 1 минуту [[_,_,_][][][]]
        # print (tsNumbersHourSumm)  # = []  # массив с количеством тс за час [[][][][]]
        # !!!!!!!!!!!!!!!!!writeFile(linTSNumberHourFilePath, tsNumbersHourSumm)### запись файла в linux
        # writeFile(tsNumberHourFilePath, tsNumbersHourSumm)  ### запись файла в linux было раньше в версии php, больше не актуально


def shutdown_server():  # это работает толко будучи вызванным из http запроса. почему - хз.
    func = request.environ.get('werkzeug.server.shutdown')
    if func is None:
        raise RuntimeError('Not running with the Werkzeug Server')
    func()


def detectors_update():  # при обновлении рамок их над опо-новой пересоздавать. раньше это в updatePolyFromServer было, а теперь он в другом контексте.
    global ramki, dets, ramkiDirections, learningRateInc, adaptLearningRate
    global colorStatus, colorStatusPrev
    dets = []  # будущие экземпляры класса detector  dets ниже везде заменть в while
    # в цикле создаем рамки и передем им данные рамок из веб интерфейса
    # обновлено 6.11 из каждой рамки надо сделать 4
    # сначала сфрмировать новые рамки - в 4 раза больше.
    ###ramki4 = make4RamkiFrom1(ramki)
    ###dets4=[[] for i in  range(len(ramki))] # подготовили массив для детекторов X4

    for i in range(len(ramki)):  # в dets будут лежать объекты класса
        dets.append(detector(pict, ramki[i], i))
    for i in range(len(ramki)):
        dets[i].noRamkiDirectionsFlag = 0  # флаг что в рамке нет направлений. см. ниже на 3 строки
        dets[i].cos_alfa_calculator()
    for i, j in enumerate(ramkiDirections):  # если в рамке нет направлений, то задается сработка со всех направлений
        if not 1 in ramkiDirections[i]:
            dets[i].noRamkiDirectionsFlag = 1  # если в рамке нет направлений, ставим флаг что нет направлений
    colorStatus = [0 for i in ramki]
    colorStatusPrev = [0 for i in ramki]
    adaptLearningRate = adaptLearningRateInit
    # print('len dets ',len(dets))


def mainProcess():  # процесс где вычисляются состояния рамок занято, чи нет. внего предается очередь картинок.
    global path, cicle, pict, ramki, colorStatus, colorStatusPrev
    global winMode, statusFilePath, linPath, polygonesFilePath, tsNumberMinuteFilePath, tsNumberHourFilePath, showMode
    global tsNumbers, tsNumbersPrev, tsNumbersMinute, tsNumbersMinuteSumm, tsNumbersInterval
    global tsNumbersHour, tsNumbersHourSumm
    cicle = 0
    tstRamkiTrig = 0
    # showMode = 1
    if 'win' in sys.platform:
        from camera import Camera

        winMode = 1
        path = winPath
        print("Windows mode, path=", path)
    else:
        linPath = '/home/developer/Camera_piter/'
        if 'arm' in os.popen("uname -m").read():  # если запущено на малине
            linPath = '/home/pi/dt2/'
            from camera_pi import Camera
            import RPi.GPIO as GPIO
            GPIO.setmode(GPIO.BOARD)
            GPIO.setup(7, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        else:
            from camera import Camera
        winMode = 0
        path = linPath
        polygonesFilePath = path + 'polygones.dat'
        tsNumberMinuteFilePath = path + 'minTSNumber.dat'  # в питоне больше не актуально кандидат на удаление
        tsNumberHourFilePath = path + 'hourTSNumber.dat'  # то же
        statusFilePath = linPath + statusFilePath
        print("Linux mode; path=", path)
    print("url=", url)
    # вызов программы устанавливающей параметры детектирования
    ipSetup()  # вызов программы для установки хаба , а для линукса еще и ip адреса,маски и гейта
    detection_settings = readDetectorSettings()

    for param in sys.argv:  # запуск проги в режиме визуализации
        if param == 'vis':
            print('work in visual mode')
            showMode = 1
    print('showMode', showMode)

    # lock = threading.RLock()  # будем блокировать треды ### по-ходу это больше не нужно
    # ramki,ramkiModes,ramkiDirections = readPolyFile(polygonesFilePath)
    rt = RepeatedTimer(tsCalcTimeInterval, updTsNumsMinute,
                       tsNumberMinuteFilePath)  # !!!!!!!!! вызывает функцию которая будет обновлять массив количества проехавших с отсчетами за интервал
    rtUpdPolyFromServer = RepeatedTimer(5, updatePolyFromServer, polygonesFilePath, q_ramki)
    rth = RepeatedTimer(60, updTsNumsHour,
                        tsNumberHourFilePath)  # вызывает функцию, которая будет обновлять минутные отсчеты и формировать данные о кол-ве тс за час
    # rtUpdStatusForHub = RepeatedTimer(0.4, sendColorStatusToHub, *[ipStatus['hub']])  # обновляем статус для web сервера раз в 400 мс !!!!!!!!!!!!!!!!!!!!!!!проблема с мс
    rtUpdStatusForHub = RepeatedTimer(0.4, sendColorStatusToHub)  # обновляем статус для Hub'a раз в 400 мс
    # rtUpdStatusForHub
    rt.start()  # запустить таймер
    rth.start()  # ...
    rtUpdPolyFromServer.start()
    rtUpdStatusForHub.start()

    # watchdog timer - иногда на некоторых объектах без всякой причины падает основной процесс
    # но продолжает работать родительский. systemctl не рубутает ситему. для этого запускаем wdt
    wdt_tmr = Timer(30, wdt_func)
    wdt_tmr.start()

    ramki, ramkiModes, ramkiDirections = readPolyFile(polygonesFilePath)
    print('ramki = ', ramki)
    print('ramkiModes = ', ramkiModes)
    print("ramkiDirections=", ramkiDirections)
    # print 'cpu_count = ', cpu_count()
    adaptLearningRate = adaptLearningRateInit
    # print ('origWidth origHeight= ', origWidth, origHeight)
    # считывание картинки из camera / camera_pi
    capture = Camera()
    # print('instances Camera ', sys.getrefcount(capture)) # 2
    pict = capture.get_frame()  # вызов класс метода без создания экземпляра. чистая блажь, можно сделать обычным способом с экземпляром и методом
    # print('pict!!!!!!!! ',pict )
    # pict = next(genInternal(capture)) # вариант запуска с генератором на малине оказывается оч медленным
    # pict = cv2.imread('dt2/1.jpg')
    ######pict = cv2.imread('cam.jpg')
    pict = cv2.cvtColor(pict, cv2.COLOR_BGR2GRAY)
    # pict = cv2.resize(pict, (width,height))
    # считывание файла с полигонами

    frame = np.zeros((512,512,3), np.uint8) # пустая картинка при старте
    
    detectors_update()  # обновляем детекторы
    learningRateInc = learningRate / 100.0
    ts2 = time.time()  # time stamp для обновления статуса рамок для web сервера
    ts3 = time.time()  # time stamp для обновления рамок при изменении их с web интерфейса
    treadSendPost = None
    tsNumbers = [0 for ii in ramki]  # количество задетектированных тс [0,0,0,0] для 4-х рамок
    colorStatus = tsNumbers[:]  # клон tsNumbers в котором лежат цвета рамок текущего цикла
    colorStatusPrev = tsNumbers[:]  # клон tsNumbers в котором лежат цвета рамок предыдущего цикла
    tsNumbersPrev = tsNumbers[
                    :]  # массив с количеством тс предыдущего шага, чтобы его вычитать из текущего и находить разницу
    tsNumbersInterval = tsNumbers[:]  # массив с количеством тс за интервал (10с)[a,b,c,d]
    tsNumbersMinute = tsNumbers[:]  # массив с количеством тс с проездами за 1 интервал за минуту [[_,_,_][][][]]
    tsNumbersMinuteSumm = tsNumbers[:]  # массив с количеством тс за минуту [10,20,30,40]
    tsNumbersHour = tsNumbers[:]  # ... за час
    tsNumbersHourSumm = tsNumbers[:]  # ... сумма за час
    numberOfInterval = int(60 / tsCalcTimeInterval)  # количество интервалов в минуте для подсчета тс
    for i in range(len(tsNumbers)):  # по количеству рамок
        tsNumbersMinute[i] = [0 for ii in range(numberOfInterval)]
    for i in range(len(tsNumbers)):  # по количеству рамок
        tsNumbersHour[i] = [0 for ii in range(60)]
    # print ("tsNumbersMinute",tsNumbersMinute)


    while 1:
        wdt_tmr.cancel() # каждый цикл обновляем таймер. Если mainProcess упадет, wdt_tmr не обновится
        # вызовется wdt_func, которая ребутнет систему.
        wdt_tmr = Timer(10, wdt_func)
        wdt_tmr.start()
        # lock.acquire()  # блокировка треда, на время выполнения обновления рамок
        # print('sys.getrefcount(capture) = ', sys.getrefcount(capture))
        if q_ramki.qsize() > 0:  # в эту очередь забиваются новые рамки, если они обновились в web.
            ramki, ramkiModes, ramkiDirections = q_ramki.get()

            # print ('ramki',ramki, ramkiModes, ramkiDirections)
            detectors_update()  # если рамки поменялись в web процессе, в этом их тоже надо менять
        # print ('while start')
        ts = time.time()  # засекли время начала цикла
        if (
                    learningRate < adaptLearningRate):  # если стартовое время обучения меньше финального, уменьшаем его постепенно
            adaptLearningRate -= learningRateInc
        # пробуем считать картинку
        # pict = capture.get_frame()
        # print('instances Camera 1', sys.getrefcount(capture)) # 2
        try:
            # print('get pict!!')
            pict = capture.get_frame()
            # pict = Camera().get_frame()
            # pict = next(genInternal(capture))

        except:
            print(u'Нет картинки!')
            continue  # если считать картинку не удалось, переходим к след итерации цикла
        # time.sleep(0.02) # искусственная шняга иначе до weba вообще дело не доходит. !!! надо поэкспериментировать!!!!! выключил в процессах
        pict = cv2.cvtColor(pict, cv2.COLOR_BGR2GRAY)
        try:
            for i in range(len(ramki)):  # проходим по всем рамкам и назначаем цвет, и считаем ТС
                # dets[i].getFgmask(pict,ramki[i], adaptLearningRate) # экземпляры класса detector == рамки
                # print ("ramkiModes=",ramkiModes[i])
                # суть алгоритма: берем направление из ramkiDirections. Если текущее ==1, то формирууем событие "въезд". Это сработка 2-х
                # рамок на въезде без сработки на выезде. если было событие въезд, далее контролируем событие выезд для этого направления:
                # сработка хотя-бы одной выездной зоны. если случилосЬ, красим, иначе нет. так, перебираем по всем направлениям.
                # for j in range (4): # перебираем по каждой из 4-х рамок внутри одной большой
                if ramkiModes[i] == 0:  # режим работы рамки "присутствие"
                    # экземпляры класса detector == рамки разбитые на 4 части:
                    try:  # зачем тут этот try? удалить?
                        dets[i].getFgmask(pict, ramki[i],
                                          adaptLearningRateInit)  # с постоянным соотношением времени обучения фона равного начальному.
                    except:
                        print('Exception!!! dets=', dets[i])
                        continue
                else:
                    dets[i].getFgmask(pict, ramki[i], adaptLearningRate)  # либо с изменяемым.
                # dets[i].cos_alfa_calculator() это здесь лишнее, т.к. есть в конструкторе
                dets[i].directionCalc()  # поместит в dets[i].frameMoveValCalculated направления движухи в рамке

                # обрабатываем движ в рамке - если есть совпадение движа с заданным напр-ем взводим его
                for k, j in enumerate(ramkiDirections[
                                          i]):  # (dets[i].frameTrigger>0) &     2 стр colorStatusPrev[i] &  ## k=0,1,2,3 - индекс каждого направления
                    m = j | dets[
                        i].noRamkiDirectionsFlag  # сработка или по признаку того что для рамки задан контроль направления, или есть признак "нет направлений"
                    if m & (dets[i].frameMoveValCalculated[k] > detection_settings["move_tresh"]) | \
                                            m & (dets[i].frameMoveTriggerCommon) & (
                                        dets[i].frameMoveValCalculated[k] > (
                                                detection_settings["move_tresh"] - detection_settings["move_hyst"])):
                        # dets[i].frameTrigger: # если задано это направление и вычисленный движ больше порога,
                        #  или рамка уже сработала и (движ все еще больше гистерезиса или сработал детектор по вычитанию фона) ставим признак сработки по этому направлению
                        # print ('dets[i].frameMoveValCalculated[k]',k,dets[i].frameMoveValCalculated[k],'из',dets[i].frameMoveValCalculated, 'задано',ramkiDirections[i] )
                        dets[i].frameMoveTrigger[k] = 1
                    else:
                        dets[i].frameMoveTrigger[k] = 0
                # если есть движ по одному из направлений, есть общий признак того что движ есть
                if 1 in dets[i].frameMoveTrigger:
                    dets[i].frameMoveTriggerCommon = 1
                    dets[i].tsRamkiUpd = time.time()  # устанавливаем таймстамп рамки
                else:
                    if time.time() - dets[
                        i].tsRamkiUpd > 0.2:  # устанавливаем мин. время сработки через таймстамп чтоб не слишком часто переключалась
                        dets[i].frameMoveTriggerCommon = 0
                if not (testMode):  # текущий статус рамок для web обновляем только в случае, если нет тест мода
                    if ramkiModes[i] == 0:  # если рамка в режиме Проезд
                        # print('ramkiModes[i]',ramkiModes[i])
                        if (dets[i].frameMoveTriggerCommon > 0):
                            colorStatus[i] = 1  # этот статус уезжает в web
                        else:
                            colorStatus[i] = 0
                    else:  # если рамка в режиме Остановка
                        if dets[i].frameMoveTriggerCommon == 1 & dets[i].frameTrigger:
                            colorStatus[i] = 1
                            # print('1')
                        if dets[i].frameTrigger & colorStatus[i]:
                            colorStatus[i] = 1
                            # print('2')
                        else:
                            colorStatus[i] = 0
                            # print('3')
                    if colorStatus[i] & (not colorStatusPrev[i]):  # при переходе цвета рамки 0->1 прибавляем
                        tsNumbers[i] += 1

                    colorStatusPrev[i] = colorStatus[
                        i]  # текущее состояние цвета рамки передаем предыдущему, и переходим к следующей итерации цикла
                # print('tsNumbers из main',tsNumbers )
                if ramkiModes[i] == 0:
                    currentState = "P"
                else:
                    currentState = "S"

                colorStatusPrev[i] = colorStatus[
                    i]  # текущее состояние цвета рамки передаем предыдущему, и переходим к следующей итерации цикла
                if showMode:
                    draw_str(pict, int(ramki[i][0][0]) + 5, int(ramki[i][0][1]) + 25,
                             currentState)  # показывает режим работы рамки проезд или остановка
                    draw_str(pict, int(ramki[i][0][0]) + 5, int(ramki[i][0][1]) + 45, str(colorStatus[i]))
                    draw_str(pict, int(ramki[i][3][0]) + 5, int(ramki[i][3][1]) - 5, str(tsNumbers[
                                                                                             i]))  # показывает количество тс проехавших в рамке за время работы программы (надо сделать чтоб за минуту) - dN/dt
                    cv2.polylines(pict, [np.array(ramki[i], np.int32)], 1, colorStatus[i] * 255,
                                  2)  # рисует рамки на картинке
                    dets[i].winName = "bkg" + str(i)
                    ##print ('#####',i,'=',dets[i].borders[3]- dets[i].borders[0],dets[i].fgmask.shape)
                    # cv2.imshow(dets4[i][j].winName,dets4[i][j].fgmask) #показывает на отдельных картинках фореграунд маску.
            tsNumberStatus = (tsNumbersMinuteSumm, tsNumbersHourSumm)
            # print('common_status ',tsNumberStatus )
            while not q_status.empty():
                q_status.get()
            if not q_status.qsize() >= q_status.maxsize:
                q_status.put(colorStatus)
            while not q_tsNumber.empty():
                q_tsNumber.get()
            if not q_tsNumber.qsize() >= q_tsNumber.maxsize:
                q_tsNumber.put(tsNumberStatus)
        except:
            print('Exception! ramki number= ', len(ramki))
            detectors_update()
            continue
        cicle = str(int(1000 * (time.time() - ts)))
        if showMode:
            # print ('adaptLearningRate',adaptLearningRate)
            draw_str(pict, 20, 25, str(int(1000 * (time.time() - ts))))  # индикация времени выполнения цикла в мс
            draw_str(pict, 75, 25, "LearnRate " + str(round(adaptLearningRate, 5)))
            cv2.imshow("input", pict)
            for i in range(len(ramki)):
                pass  # cv2.imshow(str(i),dets[i].indicator)
                # print ("tsNumbers---",tsNumbers)

        c = cv2.waitKey(1)  # выход из цикла и закрытие окон по нажатию Esc
        if c == 27:
            rt.stop()
            rth.stop()
            rtUpdPolyFromServer.stop()
            rtUpdStatusForHub.stop()
            print('Остановка по Escape!')
            break
            # lock.release()  # роспуск блокировки
    cv2.destroyAllWindows()


app.wsgi_app = ProxyFix(app.wsgi_app)  # для работы Gunicorn

if 1: # нельзя name main, потому что так не работает фласк.
    # if __name__ == '__main__':
    cicle = 0
    tstRamkiTrig = 0
    # showMode = 1
    if 'win' in sys.platform:
        winMode = 1
        path = winPath
        print("Windows mode, path=", path)
    else:  # для большого линя
        linPath = '/home/developer/Camera_piter/'

    if 'arm' in os.popen("uname -m").read():  # если запущено на малине
        from camera_pi import Camera

        linPath = '/home/pi/dt2/'
        import RPi.GPIO as GPIO

        GPIO.setmode(GPIO.BOARD)
        GPIO.setup(7, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    else:  # если запущено на Винде или большом лине
        from camera import Camera

        winMode = 0
        path = linPath
        polygonesFilePath = path + 'polygones.dat'
        tsNumberMinuteFilePath = path + 'minTSNumber.dat'
        tsNumberHourFilePath = path + 'hourTSNumber.dat'
        statusFilePath = linPath + statusFilePath
        print("Linux mode; path=", path)

    detection_settings = readDetectorSettings()
    main_proc = Process(target=mainProcess)
    main_proc.start()
    print('camera_proc started.. ')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=80, debug=False, threaded=True, use_reloader=False)
