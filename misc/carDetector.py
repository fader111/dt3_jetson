#!/usr/bin/env python
# -*- coding: utf-8 -*-
'''
программа обнаруживает машины в рамках и меняет цвет рамки
версия где рамки - полигоны
заливаем черным все кроме рамки
обрезаем картинки по размеру рамки
недоработки : надо разделить выделение фореграунда и обучение фона.
первое нужно для каждого кадра, обучение фона - сильно реже.
сейчас есть компромис - первое и второе одновременно, раз в 100мс

доработка начата 23.10.2017, цель:
    - добавить тип рамки : присутствие,остановка
    - добавить детектирование направления движения в рамке
6.10 - направление в рамке берется из polygones.dat
каждую рамку делим на 4 части. при пересечении 2-х одновременно
на одной строне и потом 2-х одновременно на противоположной - проезд
в нужно мнаправлении считаем засчитан.

этот файл - бывший main.py переделанный для работы во flask с python3
'''
import cv2
import numpy as np
import os, sys, time, json, math
import requests
from multiprocessing import cpu_count
import threading
from threading import Timer
import threading

showMode = 1  # режим с показом картинок в gui (не работает с автозагрузкой в linux)
# больше не используется linWinMode = 0      # linux =0 Windows =1, в Main есть автоопределение.
# тестовые рамки для проверки, заменяются реальными по ходу программы
testRamki = [
    [
        [61, 325],
        [106, 277],
        [296, 464],
        [88, 539]
    ],
    [
        [344, 293],
        [370, 236],
        [698, 483],
        [427, 555]
    ],
    [
        [462, 101],
        [603, 150],
        [656, 257],
        [532, 247]
    ]
]
testMode = 0  # режим работы с тестовыми рамками - в нем не надо выдавать ничего на концентратор
dets = []  # массив экземпляров класса detector == рамки
ramki = []  # рамки которые считываются из файла polygones.dat
ramki4 = []  # массив рамок, где каждой из polygones соотв.4 рамки внутри.
ramkiModes = []  # режим работы рамок: 0 - присутствие, 1 остановка.
ramkiDirections = []  # направления в рамках для каждой [0,0,1,0] - 1 обозн. активно
ramkiEntrance = []  # массив для фиксации события въезда в рамку
ramkiMonitor = []  # массив для монироринга статуса больших рамок (введен после добавления направлений для отобр статуса большой рамки текстом)
colorStatus = []  # цвета рамок
height = 300  # px размер окна в котором происходит проверка
width = 400  # px должно равняться разрешению в camera (camera_pi)

origWidth, origHeight = 800, 600  # размер окна браузера для пересчета
# detection_settings["frame_tresh"] = 20 # frame overlap, %
# detection_settings["frame_hyst"] = 10 # frame hysteresis, %
learningRate = 0.0001  # 0.00001 0.001 - это 13 секунд 0.0001 - 113 секунд !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
# detection_settings["move_tresh"] = 60 # порог, после корого считаем что в рамке есть движуха. в перспективе видимо это надо грузить это из конфига либо из настроечной web страницы
# detection_move_hyst = 58  # гистерезис срабатывания по движухе
detection_settings = {"frame_tresh": 20, "frame_hyst": 10, "move_tresh": 60,
                      "move_hyst": 58}  # настройки детектора перенесены в словарь
adaptLearningRateInit = 0.005  # 0.005 это параметр на старте для времени обучения фона
adaptLearningRate = 0  # при старте ему присваивается Init время и во время работы убавляется.
# fixLearningRate = 0.005 # параметр для рамок присутствия? пока не буду его. вместо него возьму adaptLearningRateInit
""" это старая ботва. пути перенесены в app.py 
polygonesFilePath = 'polygones.dat'
tsNumberMinuteFilePath = 'minTSNumber.dat'
tsNumberHourFilePath = 'hourTSNumber.dat'
"""
statusFilePath = 'status.dat'

tsCalcTimeInterval = 5  # раз в это число секунд считать тс может быть 1,2,3,4,5,6,10,15,20,30,60
maxNumberTS = 10000  # если накопленное количество тс станет слишком большим, сбрасывать его.


# linImagePath = '/dev/shm/mjpeg/cam.jpg' # - это от старой версии кандидат на удаление
# linImagePath = 'C:/WebServers/home/savepic/www/pic.jpg' а это не вертать!
# класс вызывает функцию function с аргументами function, *args, **kwargs с интервалом interval
class RepeatedTimer(object):
    def __init__(self, interval, function, *args, **kwargs):
        self._timer = None
        self.interval = interval
        self.function = function
        self.args = args
        self.kwargs = kwargs
        self.is_running = False
        # self.start()

    def _run(self):
        ##self.is_running = False
        self._start()
        self.function(*self.args, **self.kwargs)

    def _start(self):
        self._timer = Timer(self.interval, self._run)
        self._timer.start()

    def start(self):
        if not self.is_running:
            self._timer = Timer(self.interval, self._run)
            self._timer.start()
            self.is_running = True

    def stop(self):
        if self._timer:
            self._timer.cancel()
            self.is_running = False

    def isAlive(self):
        return self.is_running


# класс создает рамки, фон def getFgmask обновляет фон и вычисляет разницу с тек. кадром
# обновлен 6.11 - для понимания направления движеия каждая рамка поделена на 4. и все выше делается для каждой из 4-х.
# поделена линиями, соединяющими середины противоположных сторон.
class detector():
    obj_cnrt = 0

    def __init__(self, pict, frame, i):
        self.frame = frame
        self.pict = pict
        self.borders = rectOverPolygon(frame)
        ##print ('self.borders =', self.borders)  ####################################################################
        self.mask = np.zeros((self.pict.shape[0], self.pict.shape[1]),
                             dtype=np.uint8)  # черная маска по размерам входной картинки
        adaptLearningRate = adaptLearningRateInit
        # self.bg = cv2.BackgroundSubtractorMOG2(500, 5, 0)  # аргументы (history, treshold, shadow) history не активно если юзаем learninRate
        self.bg = cv2.createBackgroundSubtractorMOG2(500, 5,
                                                     0)  # аргументы (history, treshold, shadow) history не активно если юзаем learninRate
        #### Преобразование рамки в кооринаты обрезанного под нее окна
        # print (i, 'frame =', frame)
        self.roi_corners = np.array([frame], dtype=np.int32)  # вершины рамки
        cv2.fillConvexPoly(self.mask, self.roi_corners, (255, 255, 255))  # из черной маски делаем черную с белой рамкой
        self.framedPict = cv2.bitwise_and(self.pict, self.mask)
        self.smallPict = self.framedPict[int(self.borders[1]):int(self.borders[3]),
                         int(self.borders[0]):int(self.borders[2])]
        self.prev_smallPict = self.smallPict[:, :]  # нужна для детектора движения
        self.fgmask = self.bg.apply(self.smallPict, learningRate=adaptLearningRate)
        self.absMass = np.zeros((self.smallPict.shape[0], self.smallPict.shape[1]), np.uint8)  # матрица с нулями
        self.frameTrigger = 0  # (0, 0, 0) Это состояние сработки от изменения по алгоритму сравнения с фоном без учета направления
        self.frameMoveTrigger = [0, 0, 0,
                                 0]  # это состояние сработки от детектирования движения в определенном направлении
        self.frameMoveTriggerCommon = 0  # это состояние сработки от детектирования движения общее для рамки, оно =1, если есть сработка хотя-бы по одному направлению
        self.frameMoveValCalculated = [0, 0, 0,
                                       0]  # направление движения, зафиксированное детектором в рамке - аналоговая вел-на. берется из алгоритма, вычисляющего движение.
        self.cos_alfa_calculator()
        # print ('self.cos_alfax , self.cos_alfay = ',self.cos_alfax,self.cos_alfay)
        self.tss = 0  # тайм стамп, участвующий в обновлении фона
        self.tsRamkiUpd = 0  # тайм стамп, нужный для задержки в обновлении состояния рамки
        self.noRamkiDirectionsFlag = 0  # признак того, что в рамке не заданы направления, тогда она срабатывает по всем направлениям
        self.__class__.obj_cnrt += 1  # подсчет количества экземпляров класса detector (количества рамок)

    def __del__(self):
        self.__class__.obj_cnrt -= 1

    def getFgmask(self, pict, frame, adaptLearningRate):
        self.pict = pict
        self.frameArea = polygonAreaCalc(frame)
        self.framedPict = cv2.bitwise_and(self.pict, self.mask)
        self.smallPict = self.framedPict[int(self.borders[1]):int(self.borders[3]),
                         int(self.borders[0]):int(self.borders[2])]
        if (self.tss > time.time()):  # на случай еслт time.time перейдет через 0 - не знаю может так быть, или нет
            self.tss = 0
            print('tss over!!!!!!!!!!!!')
        if ((time.time() - self.tss) > 0.1):  # для увеличения скорости прореживаем обновление фона
            self.fgmask = self.bg.apply(self.smallPict, learningRate=adaptLearningRate)
            self.fgmask = cv2.erode(self.fgmask, None)
            self.fgmask = cv2.dilate(self.fgmask, None)
            self.tss = time.time()
        # print ('tss', self.tss, time.time())
        # print ('dif',time.time()-self.tss)
        cv2.convertScaleAbs(self.fgmask, self.absMass)
        self.nonZeros = cv2.countNonZero(self.absMass)
        # print('self.frameArea',self.frameArea, self.nonZeros)
        # print (self.nonZeros%frameArea* detection_settings["frame_tresh"])
        if (self.nonZeros / float(self.frameArea) * 100 > detection_settings["frame_tresh"]):
            self.frameTrigger = 1  # (255, 255, 0)
        elif (self.nonZeros / float(self.frameArea) * 100 < detection_settings["frame_tresh"] - detection_settings[
            "frame_hyst"]):  # гистерезис в 10% чтобы рамка не дергалась
            self.frameTrigger = 0  # (0, 0, 0)
        elif (self.nonZeros / float(self.frameArea) * 100 <= 0):  # на случай если порог установлен меньше гистерезиса
            self.frameTrigger = 0  # (0, 0, 0)

    def cos_alfa_calculator(
            self):  # метод вычисляет угол(косинус угла) наклона медианы - возвращает кортеж - 2 значения - по х и по у
        # return self.frame
        x0 = self.frame[0][0]
        y0 = self.frame[0][1]
        x1 = self.frame[1][0]
        y1 = self.frame[1][1]
        x2 = self.frame[2][0]
        y2 = self.frame[2][1]
        x3 = self.frame[3][0]
        y3 = self.frame[3][1]

        x01 = int((x0 + x1) / 2)  # x0+(x1-x0)/2
        y01 = int((y0 + y1) / 2)
        x12 = int((x1 + x2) / 2)
        y12 = int((y1 + y2) / 2)
        x23 = int((x2 + x3) / 2)
        y23 = int((y2 + y3) / 2)
        x30 = int((x3 + x0) / 2)
        y30 = int((y3 + y0) / 2)
        # if showMode:   # не рисуется, т.к. надо вызывать всегда во время работы, а не только в init
        # cv2.line(self.pict, (x30, y30), (x12, y12), 255, 2, 1)  # это x-медиана рамки белая
        # cv2.line(self.pict, (x01, y01), (x23, y23), 127, 2, 1)  # это y-медиана рамки серая
        # длина медианы
        medianax = math.sqrt((y12 - y30) * (y12 - y30) + (x12 - x30) * (x12 - x30))
        medianay = math.sqrt((x01 - x23) * (x01 - x23) + (y23 - y01) * (y23 - y01))
        if medianax == 0: medianax = 1
        if medianay == 0: medianay = 1
        # print('medianax= ',medianax)
        # print('medianay= ',medianay)
        '''
        if (y23 - y01)!=0 :
            alfay = math.atan((x01 - x23)/(y23 - y01))
        else:
            alfay = 90/180*math.pi
        if (x30-x12)!=0 :
            alfax = math.atan((y30 - y12) / (x30 - x12))
        else:
            alfax = 0
        '''
        # print('x01 , x23 ', x01 , x23)
        # print('y01 , y23 ', y01 , y23)
        # print('x12 , x30 ', x12 , x30)
        # print('y12 , y30 ', y12 , y30)
        if medianax != 0:
            self.cos_alfax = (x12 - x30) / medianax
            self.sin_alfax = (y12 - y30) / medianax
        else:
            self.cos_alfax = 0
            self.sin_alfax = 1
        if medianay != 0:
            self.cos_alfay = (y23 - y01) / medianay
            self.sin_alfay = (x01 - x23) / medianay
        else:
            self.cos_alfay = 1
            self.sin_alfay = 0
        # print('self.cos_alfax ', self.cos_alfax)
        # print('self.sin_alfax ', self.sin_alfax)
        # print('self.cos_alfay ', self.cos_alfay)
        # print('self.sin_alfay ', self.sin_alfay)
        # return (math.cos(alfax),math.cos(alfay))
        return (0, 0)

    def directionCalc(
            self):  # метод возвращает движ по каждому из направлений в ROI в виде 0 если нет движа и 1 если есть
        flow = cv2.calcOpticalFlowFarneback(self.smallPict, self.prev_smallPict, None, 0.5, 1, 15, 1, 2, 1.2,
                                            0)  # cv2.OPTFLOW_FARNEBACK_GAUSSIAN) # вернет массив точек в каждой будет смещение, а в 3-й координате будет по x и y соответственно
        flowx = flow[:, :,
                0]  # flow=None, pyr_scale=0.5, levels=3, winsize=15, iterations=3, poly_n=5, poly_sigma=1.1, flags=0
        flowy = flow[:, :, 1]
        self.prev_smallPict = self.smallPict  # уточнить зачем это тут!!!!!!!!
        # далее технология следующая: умножаем полученное движение по осям на cos угла
        # между направлением и x-медианой для направлений по X координате и направллением и y-медианой для направлений по y-медиане.
        # x-медиана рамки - отрезок соединяющий середины правой и левой сторон рамки. Y - медиана соединяет середины верхней и нижней сторон.
        # self.frameMoveValCalculated = [flowx.mean(),0,0,0] # времненная затычка
        self.frameMoveValCalculated[0] = int((flowy.mean() * self.cos_alfay - flowx.mean() * self.sin_alfay) * 100)
        self.frameMoveValCalculated[1] = - int((flowx.mean() * self.cos_alfax + flowy.mean() * self.sin_alfax) * 100)
        self.frameMoveValCalculated[2] = - self.frameMoveValCalculated[0]
        self.frameMoveValCalculated[3] = - self.frameMoveValCalculated[1]

        if showMode:
            self.indicator = np.zeros((100, 100),
                                      dtype=np.uint8)  # это временная картинка чтобы отображать на ней циферки, бо они мешают считать движуху на основной
            cv2.putText(self.indicator, str(abs(round(flowx.mean(), 1))), (5, 10), cv2.FONT_HERSHEY_PLAIN, 0.8, 255, 2)
            cv2.putText(self.indicator, str(abs(round(flowy.mean(), 1))), (5, 20), cv2.FONT_HERSHEY_PLAIN, 0.8, 255, 2)
            cv2.putText(self.indicator, str(self.frameMoveValCalculated[0]), (50, 10), cv2.FONT_HERSHEY_PLAIN, 0.8, 255,
                        2)
            cv2.putText(self.indicator, str(self.frameMoveValCalculated[1]), (50, 20), cv2.FONT_HERSHEY_PLAIN, 0.8, 255,
                        2)
            cv2.waitKey(1)


def draw_str(dst, x, y, s):
    cv2.putText(dst, s, (x + 1, y + 1), cv2.FONT_HERSHEY_PLAIN, 1.0, (0, 0, 0), thickness=2, lineType=1)
    # cv2.putText(dst, s, (x, y), cv2.FONT_HERSHEY_PLAIN, 2.0, (255, 255, 255), lineType=cv2.CV_AA)
    cv2.putText(dst, s, (x, y), cv2.FONT_HERSHEY_PLAIN, 1.0, (255, 255, 255), lineType=1)


def writeFile(filePath, status):
    with open(filePath, 'w') as f:
        string = f.write(str(status))
        # print status,str(status)
    return 1


def polygonAreaCalc(polygon):
    polygonArea = 0  # площадь полигона
    polyLen = len(polygon)
    # print ('n=',n)
    for i in range(polyLen):
        x = polygon[i][0]
        if i == 0:
            y = polygon[polyLen - 1][1]
            y1 = polygon[i + 1][1]
        elif i == polyLen - 1:
            y = polygon[i - 1][1]
            y1 = polygon[0][1]
        else:
            y = polygon[i - 1][1]
            y1 = polygon[i + 1][1]
        polygonArea += x * (y - y1)
        # print (x * (y - y1))
    return abs(polygonArea) / 2


def rectOverPolygon(polygon):
    x1, y1 = x2, y2 = polygon[0]
    for i in range(len(polygon)):
        if polygon[i][0] < x1: x1 = polygon[i][0]
        if polygon[i][1] < y1: y1 = polygon[i][1]
        if polygon[i][0] > x2: x2 = polygon[i][0]
        if polygon[i][1] > y2: y2 = polygon[i][1]
    return x1, y1, x2, y2


def readPolyFile(polygonesFilePath):  # считывание файла с полигонами
    # time.sleep(0.1)
    # global origWidth, origHeight,ramki,ramkiModes,ramkiDirections,linPolygonesFilePath
    global origWidth, origHeight, testMode
    polygonesFilePath = "polygones.dat"
    try:
        with open(polygonesFilePath, 'r') as f:
            jsRamki = json.load(f)
            ramki = jsRamki.get("polygones", testRamki)
            origWidth, origHeight = jsRamki.get("frame", (800, 600))  # получаем размер картинки из web интрефейса
            ramkiModes = jsRamki.get("ramkiModes",
                                     [0 for i in range(len(ramki))])  # по дефолту все рамки - в режиме присутствие
            ramkiDirections = jsRamki.get("ramkiDirections", [[0, 0, 0, 0] for i in range(len(
                ramki))])  # дефолт - нет направлений. дефолт переделать, т.к. может быть не 4 - надо сделать генератор
            testMode = 0

    except Exception as Error:  # если рамки не считались, и подставились тестовые, работает криво - рамки каждый раз масштабируются, как это поправить, пока не знаю.
        print(u'считать рамки не удалось, пришлось подставить тестовые..', Error)
        ramki = testRamki  # это уже вроде выше присвоилось... удалять не надо, иначе вызывает ошибки типа ramki не определены при попадании в exception
        ramkiModes = [0 for i in range(len(ramki))]
        ramkiDirections = [[0, 0, 0, 0] for i in range(len(ramki))]
        testMode = 1

    # масштабируем рамки
    # dets = []  # будущие экземпляры класса detector
    # в цикле создаем рамки и передем им данные рамок из веб интерфейса
    for i in range(len(ramki)):
        xRate = origWidth / float(width)  # соотношение сторон по x картинки с web и картинки в питоне
        yRate = origHeight / float(height)  # то-же по y
        ###print (ramki[i] , 'i=',i, 'origWidth',origWidth, 'origHeight',origHeight)
        for j in range(len(ramki[i])):
            ramki[i][j][0] = round(ramki[i][j][0] / xRate)  # масштабирование всех рамок
            ramki[i][j][1] = round(ramki[i][j][1] / yRate)
    return ramki, ramkiModes, ramkiDirections

# функция делает 4 рамки из одной. входной аргумент однако - весь массив рамок
# def make4RamkiFrom1(ramki):
#     # вход ramki[i]=[[x1,y1],[x2,y2],[x3,y3],[x4,y4]]
#     # выхлоп ramki4[i] = [[[x0,y0],[x1,y1],[x2,y2],[x3,y3]],[вторая внутр. рамка],(третья....] т.е. [i][внурт рамка 1-4][угол][кордината x или y]
#     ramki4=[[[[0,0] for k in range(4)] for j in range(4)] for i in range(len(ramki))] # нулями ее забить выхлоп при старте
#     for i in range(len(ramki)):
#         x0= ramki4[i][0][0][0]= ramki[i][0][0]
#         y0= ramki4[i][0][0][1]= ramki[i][0][1]
#         x1= ramki4[i][1][1][0]= ramki[i][1][0]
#         y1= ramki4[i][1][1][1]= ramki[i][1][1]
#         x2= ramki4[i][2][2][0]= ramki[i][2][0]
#         y2= ramki4[i][2][2][1]= ramki[i][2][1]
#         x3= ramki4[i][3][3][0]= ramki[i][3][0]
#         y3= ramki4[i][3][3][1]= ramki[i][3][1]
#         # находим середины строн, они-же координаты углов внутренних рамок
#         x01= ramki4[i][0][1][0]= ramki4[i][1][0][0]= (x0+x1)/2  #x0+(x1-x0)/2
#         y01= ramki4[i][0][1][1]= ramki4[i][1][0][1]= (y0+y1)/2
#         x12= ramki4[i][1][2][0]= ramki4[i][2][1][0]= (x1+x2)/2
#         y12= ramki4[i][1][2][1]= ramki4[i][2][1][1]= (y1+y2)/2
#         x23= ramki4[i][2][3][0]= ramki4[i][3][2][0]= (x2+x3)/2
#         y23= ramki4[i][2][3][1]= ramki4[i][3][2][1]= (y2+y3)/2
#         x30= ramki4[i][3][0][0]= ramki4[i][0][3][0]= (x3+x0)/2
#         y30= ramki4[i][3][0][1]= ramki4[i][0][3][1]= (y3+y0)/2
#         xm = ramki4[i][0][2][0]= ramki4[i][1][3][0]=ramki4[i][2][0][0]=ramki4[i][3][1][0]=(x01+x23)/2
#         ym = ramki4[i][0][2][1]= ramki4[i][1][3][1]=ramki4[i][2][0][1]=ramki4[i][3][1][1]=(y01+y23)/2
#         #print ("ramki[i]",ramki[i])
#     return ramki4
#
