
# -*- coding: utf-8 -*-
import cProfile
import sys, os, time, cv2, socket
from flask import Flask, session, render_template, Response, request, json, jsonify, make_response
# from flask_session import Session
# from multiprocessing import Process, Queue, cpu_count #это фризит процесс.
from multiprocessing.dummy import Process, Queue
from threading import Timer
#from camera_pi import Camera
from RepeatedTimer_ import RepeatedTimer
from image_proc import *
from conf_editor import *
from get_net_settings import *

import RPi.GPIO as GPIO

GPIO.setmode(GPIO.BOARD)
GPIO.setup(7, GPIO.IN, pull_up_down=GPIO.PUD_UP)

from werkzeug.contrib.fixers import ProxyFix
from functools import wraps, update_wrapper
from datetime import datetime
import requests
# import logging

path = '/home/a/dp2/'  # путь до папки проекта

ipStatus = {"ip": '192.168.0.100',
            "mask": '255.255.255.0',
            "gateway": '192.168.0.1',
            "hub": '192.168.0.39'
            }
det_status = [0] # массив для сохранения статуса детектора (пока 1 значение) [GREEN_TAG] из вычислительного потока

app = Flask(__name__)


@app.route('/', methods=['GET', 'POST'])
def index():
    ipStatus = {"ip": get_ip() + '/' + get_bit_number_from_mask(get_mask()),
                "gateway": get_gateway(),
                "hub": get_hub(path)
                }
    return render_template('index.html', ipStatus=ipStatus)


@app.route('/video_feed')
def video_feed():
    """Video streaming route. Put this in the src attribute of an img tag."""
    return Response(gen(), mimetype='multipart/x-mixed-replace; boundary=frame')


@app.route('/sendSettingsToServer', methods=['GET', 'POST'])
def sendSettingsToServer():
    """ это вызывается при нажатии на кнопку на форме и сохраняет параметры ip на сервере """
    print('request.form',
          request.form)  # ImmutableMultiDict([('gateway', '192.168.0.254'), ('hub', '192.168.0.39'), ('ip', '192.168.0.16')])
    filePath_ipconf = path + 'ipconf.dat'
    if request.method == 'POST':
        ip = request.form['ip']
        # mask = request.form['mask'] если в посылке нет такого поля прога тут зависает нахрен.
        # print('method post',mask)
        gateway = request.form['gateway']
        hub = request.form['hub']
    ipStatus["hub"] = hub
    # print('from python: ip', ip,'  mask',mask, '  gateway',gateway,'  hub',hub)
    ip_ext = ip  # +'/24' # костыль пока маску не сделал
    change_ip_on_jetson(ip_ext, gateway)  # меняет ip и default gw
    applyIPsettingsJetson(gateway)  # применить все настройки перегрузить сетевые службы
    with open(filePath_ipconf, 'w') as f:  # Открываем на чтение и запись, записать адрес хаба
        f.write(json.dumps({'hub': hub}))  # Пишем данные в файл.( только адрес хаба)
        print('IP settings saved!')
    return json.dumps({'ip': ip, 'gateway': gateway, 'hub': hub})


def sendHubStatusToWeb():
    hubAddress = ipStatus['hub']
    addrString = 'http://' + hubAddress + '/detect'
    # отладка поиск утечек
    # tr_initial.print_diff()
    try:
        requests.get(addrString, timeout=(0.1, 0.1))
        ans = requests.post(addrString, json={"cars_detect": det_status})
        # print('hub ',addrString,)
        return ans.text
    except:
        # print('expt from  sendHubStatusToWeb', )
        return 'Disconnected...'


@app.route('/showStatusHub', methods=['POST'])
def showStatusHub():
    """shows hub status on web page"""
    return json.dumps(sendHubStatusToWeb())


def applyIPsettingsLinux(gate):
    """apply all the network settings, restart dcpcd service after changes on web page"""
    _comm = os.popen("sudo ip addr flush dev eth0 && sudo systemctl restart dhcpcd.service")
    _comm.read()
    time.sleep(10)  # время необходимое сетевым службам чтобы рестартовать
    routComm = os.popen("sudo route del default")  # нужно для обновления адреса шлюза по умолчанию
    routComm.read()
    # print('gate from change func = ', gate)
    gwComm = os.popen("sudo route add default gw " + gate)  # нужно для обновления адреса шлюза по умолчанию
    gwComm.read()


def applyIPsettingsJetson(gate):
    """apply all the network settings, restart netw manager service after changes on web page"""
    _comm = os.popen("sudo ip addr flush dev eth0 && sudo service network-manager restart")
    _comm.read()
    time.sleep(10)  # время необходимое сетевым службам чтобы рестартовать
    routComm = os.popen("sudo route del default")  # нужно для обновления адреса шлюза по умолчанию
    routComm.read()
    # print('gate from change func = ', gate)
    gwComm = os.popen("sudo route add default gw " + gate)  # нужно для обновления адреса шлюза по умолчанию
    gwComm.read()


def gen():
    """Video streaming generator function."""
    global frame
    while True:
        # print('q_pict.qsize()', q_pict.qsize())
        if not q_pict.empty():
            frame = q_pict.get()
        frame_ = cv2.imencode('.jpg', frame)[1].tostring()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_ + b'\r\n')
        #time.sleep(0.1)


def change_ip_on_host(ip, gate, fname='/etc/dhcpcd.conf'):  # 129.168.0.16/24 
    """ ONLY FOR RASPBERRY!! changes ip: edit /etc/dhcpcd.conf file and restart network """
    file_edit(fname, 'inform', ip)
    file_edit(fname, 'static routers', gate)


def change_ip_on_jetson(ip, gate, fname='/etc/NetworkManager/system-connections/Wired connection 1'):
    """ ONLY FOR JETSON cahanges ip, mask, gate in file /etc/NetworkManager/system-connections/Wired connection 1 """
    file_edit_jetson(fname, ip, gate)


def set_Default_IP_Settings(def_ip="192.168.0.34/24", def_gateway="192.168.0.254"):
    """ записывает новые ip и default gw в файл настроек сети и применяет их """
    change_ip_on_jetson(def_ip, def_gateway)
    applyIPsettingsJetson(def_gateway)  # применить все настройки перегрузить сетевые службы


def gpio_button_handler(channel):
    """ воостанавливает дефолтные настройки IP при замыкании пина 5 на землю"""
    # print ("сработка set_Default_IP_Settings!!!")
    ts = time.time()
    while GPIO.input(7) == False:  # при замыкании кнопки
        # print("false")
        time.sleep(1)
        if (time.time() - ts > 2):
            print("Restore Default IP Settings")
            print("ip = 192.168.0.34/24, default gw = 192.168.0.254")
            set_Default_IP_Settings()
            # time.sleep(0.1)


def sendDetStatusToHub():  # передача состояний рамок на концентратор методом POST
    # def sendColorStatusToHub(hubAddress = '192.168.0.39:80'):
    hubAddress = ipStatus['hub']
    # print('hubAddress = ',hubAddress)
    addrString = 'http://' + hubAddress + '/detect'
    if q_status.qsize()>0:
        det_status[0] = q_status.get()
    # print("addrString", addrString, "detST", det_status)
    try:
        requests.get(addrString, timeout=(0.1, 0.1))
        ans = requests.post(addrString, json={"cars_detect": det_status[0]}) # сюда вместо colorStatus через очередь надо сунуть статус сработки!!!!
        # print('hub ',addrString,)
        # return ans.text
    except:
        pass
        # print('expt from  sendColorStatusToHub', )
        # return 'Disconnected...'


def main_process():
    proc()


# в главном треде срабатывает вызов при нажатии на кнопку пин 5.
GPIO.add_event_detect(7, GPIO.FALLING, callback=gpio_button_handler, bouncetime=100)

ipStatus = {"ip": get_ip() + '/' + get_bit_number_from_mask(get_mask()),
            "gateway": get_gateway(),
            "hub": get_hub(path)
            }
print ('ipStatus-',ipStatus)

# шлем статус сработки детектора на контроллер , концентратор. раз в 400 мс.
rtUpdStatusForHub = RepeatedTimer(0.4, sendDetStatusToHub)  # обновляем статус для Hub'a раз в 400 мс
rtUpdStatusForHub.start()

# в параллельном процессе запускаем все вычисления

frame = np.zeros((512,512,3), np.uint8) # пустая картинка при старте
font = cv2.FONT_HERSHEY_SIMPLEX
cv2.putText(frame,'wait...',(180,250), font, 2,(255,255,255),2,cv2.LINE_AA)

main_proc = Process(target=main_process)
main_proc.start()

if __name__ == "__main__":
    app.run(app.run(host='0.0.0.0', port=8080, debug=False, threaded=True, use_reloader=False))