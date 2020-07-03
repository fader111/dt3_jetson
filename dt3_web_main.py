''' Taskkill /IM python.exe /F'''
''' Transport Detector Type2 with web interface '''
import cProfile
import sys, os, time, cv2, socket
from flask import Flask, session, render_template, Response, request, json, jsonify, make_response
from flask_httpauth import HTTPBasicAuth
# from flask_session import Session
# from multiprocessing import Process, Queue, cpu_count #это фризит процесс.
# from multiprocessing import Process, Queue
from multiprocessing.dummy import Process, Queue
from threading import Timer
#from camera_pi import Camera
# from RepeatedTimer_ import RepeatedTimer
from main_proc_dlib import *
from conf_editor import *
from get_net_settings import *
from pprint import pprint

# import RPi.GPIO as GPIO
# GPIO.setmode(GPIO.BOARD)
# GPIO.setup(7, GPIO.IN, pull_up_down=GPIO.PUD_UP)

from werkzeug.contrib.fixers import ProxyFix
from functools import wraps, update_wrapper
from datetime import datetime
import requests
# import logging

if 'win' in sys.platform:
    path = 'C:/Users/ataranov/Projects/dt3_jetson/'  # путь до папки проекта в windows
else:
    path = '/home/a/dt3_jetson/'  # путь до папки проекта в linux

ipStatus = {"ip": '192.168.0.100/24',
            "gateway": '192.168.0.1',
            "hub": '192.168.0.39'
            }
det_status = [0] # массив для сохранения статуса детектора (пока 1 значение) [GREEN_TAG] из вычислительного потока
polygones = {} # рамки со всеми потрохами

app = Flask(__name__)
auth = HTTPBasicAuth() # for authentication


@app.route('/', methods=['GET', 'POST'])
def index():
    full_path = path + "settings.dat"

    settings = read_setts_from_syst(full_path)
    ipStatus = {"ip": get_ip() + '/' + get_bit_number_from_mask(get_mask()),
                "gateway": get_gateway(),
                "hub": get_hub(full_path)
                }

    return render_template('index.html', ipStatus=ipStatus, settings=settings)


@app.route('/video_feed')
def video_feed():
    """Video streaming route. Put this in the src attribute of an img tag."""
    return Response(gen(), mimetype='multipart/x-mixed-replace; boundary=frame')


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


@app.route('/sendSettingsToServer', methods=['GET', 'POST'])
def sendSettingsToServer():
    """ calls any time, when settings change in web client, 
        save settings to file """
    #print('request.form',
    #      request.form)  # ImmutableMultiDict([('gateway', '192.168.0.254'), ('hub', '192.168.0.39'), ('ip', '192.168.0.16')])
    settings_file_path = path + 'settings.dat'
    if request.method == 'POST':
        ip = request.form["ip"]
        # mask = request.form['mask'] если в посылке нет такого поля прога тут зависает нахрен.
        # print('method post',mask)
        gateway = request.form["gateway"]
        hub = request.form["hub"]
        calibPoly = request.form['calibration']
        calib_zone_length = request.form['calib_zone_length']
        calib_zone_width = request.form['calib_zone_width']
    ipStatus["hub"] = hub
    # print('from python: ip', ip,'  mask',mask, '  gateway',gateway,'  hub',hub)
    ip_ext = ip  # +'/24' # костыль пока маску не сделал
    change_ip_on_jetson(ip_ext, gateway)  # меняет ip и default gw
    applyIPsettingsJetson(gateway)  # применить все настройки перегрузить сетевые службы
    with open(settings_file_path, 'w') as f:  # Открываем на чтение и запись
        # записываем только то, что не сохранится в линуксе - адрес хаба и калибровачный полигон
        # остальное - ip маска и шлюз применится в линуксе и сохранится. записывать нет надо.
        # f.write(json.dumps({'hub': hub, 'calibration' : calibPoly}))  # Пишем данные в файл.
        f.write(json.dumps({"hub": hub, # Пишем данные в файл.
                            "calibration" : calibPoly,
                            "calib_zone_length" : calib_zone_length,
                            "calib_zone_width" : calib_zone_width
                        }))
        print('IP settings saved!')
    # put polygones and settings to the queue for update them on main_proc_dlib
    # need to put both, because poly depends on calibration, which are in the settings

    updateSettings(json.dumps({ 'hub'               : hub,
                                'calibration'       : calibPoly,
                                'calib_zone_length' : calib_zone_length,
                                'calib_zone_width'  : calib_zone_width
                                }))
    time.sleep(1) # needs to be sure that settings are inplemented before polygones
    # because settings queue is a bit slower then polygones queue ( ?? need one queue for both polygones and settings??)
    # otherwise old calibration zone dimentions are in polygones.
    
    #updatePoly(json.dumps(polygones)) #похоже этого недостаточно. 
    # тут оказываются старые полигоны, буду читать новые полигоны из файла, потом их обновлять.
    res = json.loads(getPolyFromServer())
    updatePoly(res)
    
    
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


@app.route('/sendPolyToServer', methods=['GET', 'POST'])
def sendPolyToServer():
    ''' calls any time, when polygones change in web client, 
        save polygones to file
    '''
    filePath = path + 'polygones.dat'
    if request.method == 'POST':
        print("request.get_data (poly)== ", request.get_data())
        poly = request.form["req"]
        print('polygones=', poly)
        if "polygones" in poly:  # так надо проверять, т.к. иногда чушь посылает.
            print('polygones type IS RIGHT!')
            try:
                with open(filePath, 'w') as f:
                    f.write(poly)  # Пишем данные полигонов в файл.
                print('polygones saved! path=', path)
                # updates polygones according to the changes
                updatePoly(poly)
            except:
                print(u"Не удалось сохранить файл polygones.dat")
                return json.dumps("Polygones wasn't sent to server...")

            return json.dumps('Polygones sent to server...')
        print('polygones type IS WRONG!')
        return json.dumps('Wrong data sent to server...')


@app.route('/getPolyFromServer', methods=['GET', 'POST'])
def getPolyFromServer():
    ''' calls when aplication starts, 
        reads polygones from file
    '''
    # print('polygonesFilePath = ',polygonesFilePath)
    poly = None
    filePath = path + 'polygones.dat'
    print('filePath = ', path + 'polygones.dat')
    try:
        with open(filePath, 'r') as f:  # !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
            poly = f.read()  # вытаскиваем рамки из файла
    except:
        print(u"Не удалось прочитать файл polygones.dat")
    # print('считанные рамки = ', poly)
    polygones = json.dumps(poly)
    updatePoly(poly)
    return json.dumps(poly)


@app.route('/getSettingsFromServer', methods=['GET', 'POST'])
def getSettingsFromServer():
    ''' calls when aplication starts,
        reads settings from file
    '''
    settings = None
    filePath = path + 'settings.dat'
    print('filePath = ', path + 'settings.dat')
    try:
        with open(filePath, 'r') as f:  # !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
            settings = f.read()  # вытаскиваем настройки из файла
    except:
        print(u"Не удалось прочитать файл settings.dat")
    # print('считанные настройки = ', settings)
    updateSettings(settings)
    return json.dumps(settings)


@auth.get_password
def get_password(username):
    if username == 'smarttraffic':
        return '9TYsDh2f3_'
    return None


@auth.error_handler
def unauthorized():
    return make_response(jsonify({'error': 'Unauthorized access'}), 401)


@app.route('/status60', methods=['GET'])
@auth.login_required
def getStatus60():
    ''' response for client request about traffic parameters for 60 minutes'''
    return jsonify({'tasks': '23'})


@app.route('/status15', methods=['GET'])
@auth.login_required
def getStatus15():
    ''' response for client request about traffic parameters for 15 minutes'''
    ans = { 
  				"avg_speed": [ 55, 60, 40, 100 ],
  				"vehicle_types_intensity": [{"bus": 10, "truck": 20, "car": 50},
                                            {"bus": 1, "truck": 2, "car": 70},
                                            {"bus": 0, "truck": 1, "car": 90},
                                            {"bus": 0, "truck": 0, "car": 950}],
  				"intensity": [200, 300, 350, 400],
  				"avg_time_in_zone": [3, 1, 1, 1]
			}
    return jsonify(ans)


@app.route('/sendCalibrationToServer', methods=['POST'])
def sendCalibrationToServer():
    ''' IS IT ABSOLETE??? TO DELETE??? '''
    ''' When finish calibration on server, put the calibration 
        polygon points to the python'''
    pass


def updatePoly(poly):
    ''' Updates polygones, during start or when changes come from web client'''
    polygones = poly
    # print(f'polygones {polygones}')
    while not q_ramki.empty():  # перед помещением в очередь чистим ее
        q_ramki.get()
    if not q_ramki.qsize() >= q_ramki.maxsize:
        q_ramki.put(poly)  # обновили очередь рамок.


def updateSettings(settings):
    ''' Updates settings in main_proc_dlib, when changes come from web client
        put changes to queue '''
    print('settings', settings)
    while not q_settings.empty():
        q_settings.get()
    if not q_settings.qsize() >= q_settings.maxsize:
        q_settings.put(settings)


def applyIPsettingsLinux(gate):
    """apply all the network settings, restart dcpcd service after changes on web page"""
    if not winMode:
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
    if not winMode:
        _comm = os.popen("sudo ip addr flush dev eth0 && sudo service network-manager restart")
        _comm.read()
        time.sleep(10)  # время необходимое сетевым службам чтобы рестартовать
        routComm = os.popen("sudo route del default")  # нужно для обновления адреса шлюза по умолчанию
        routComm.read()
        # print('gate from change func = ', gate)
        gwComm = os.popen("sudo route add default gw " + gate)  # нужно для обновления адреса шлюза по умолчанию
        gwComm.read()


def change_ip_on_host(ip, gate, fname='/etc/dhcpcd.conf'):  # 129.168.0.16/24 
    """ ONLY FOR RASPBERRY!! changes ip: edit /etc/dhcpcd.conf file and restart network """
    file_edit(fname, 'inform', ip)
    file_edit(fname, 'static routers', gate)


def change_ip_on_jetson(ip, gate, fname='/etc/NetworkManager/system-connections/Wired connection 1'):
    """ ONLY FOR JETSON cahanges ip, mask, gate in file /etc/NetworkManager/system-connections/Wired connection 1 """
    if not winMode:
        file_edit_jetson(fname, ip, gate)


def set_Default_IP_Settings(def_ip="192.168.0.34/24", def_gateway="192.168.0.254"):
    """ записывает новые ip и default gw в файл настроек сети и применяет их """
    if not winMode:
        change_ip_on_jetson(def_ip, def_gateway)
        applyIPsettingsJetson(def_gateway)  # применить все настройки перегрузить сетевые службы


def gpio_button_handler(channel):
    """ восcтанавливает дефолтные настройки IP при замыкании пина 5 на землю"""
    # print ("сработка set_Default_IP_Settings!!!")
    ts = time.time()
    while 0:#GPIO.input(7) == False:  # при замыкании кнопки
        # print("false")
        time.sleep(1)
        if (time.time() - ts > 2):
            print("Restore Default IP Settings")
            print("ip = 192.168.0.34/24, default gw = 192.168.0.254")
            set_Default_IP_Settings()
            # time.sleep(0.1)


def main_process():
    proc()


# в главном треде срабатывает вызов при нажатии на кнопку пин 5.
# GPIO.add_event_detect(7, GPIO.FALLING, callback=gpio_button_handler, bouncetime=100)

ipStatus = {"ip": get_ip() + '/' + get_bit_number_from_mask(get_mask()),
            "gateway": get_gateway(),
            "hub": get_hub(path+"settings.dat")
            }
print ('ipStatus-', ipStatus)



# шлем статус сработки детектора на контроллер , концентратор. раз в 400 мс.
# rtUpdStatusForHub = RepeatedTimer(0.4, sendDetStatusToHub)  # обновляем статус для Hub'a раз в 400 мс
# rtUpdStatusForHub.start()
# !! устарело - это переехало в вычислительный процесс
# в параллельном процессе запускаем все вычисления

settings = read_setts_from_syst(path + "settings.dat")
polygones = read_polygones_from_file(path + "polygones.dat")

frame = np.zeros((512,512,3), np.uint8) # пустая картинка при старте
font = cv2.FONT_HERSHEY_SIMPLEX
cv2.putText(frame,'wait...',(180,250), font, 2,(255,255,255), 2, cv2.LINE_AA)

main_proc = Process(target=main_process)
main_proc.start()

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8080, debug=False, threaded=True, use_reloader=False)