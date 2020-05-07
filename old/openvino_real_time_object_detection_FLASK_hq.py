#!/usr/bin/env python3
""" With web interface based on flask with good quality picture
"""
from imutils.video import VideoStream
from threading import Timer, Thread, Lock
from multiprocessing.dummy import Process, Queue
import numpy as np
import imutils
import time
import cv2
import RPi.GPIO as GPIO
import sys
import os

GPIO.setwarnings(False) # suppresses GPIO warnings
GPIO.setmode(GPIO.BOARD)
GREEN = 40
GPIO.setup(GREEN, GPIO.OUT)
RED = 38
GPIO.setup(RED, GPIO.OUT)

vis = False # xMode with Display
confidence_tresh = 0.2

# initialize the list of class labels MobileNet SSD was trained to
# detect, then generate a set of bounding box colors for each class
CLASSES = ["background", "aeroplane", "bicycle", "bird", "boat",
           "bottle", "bus", "car", "cat", "chair", "cow", "diningtable",
           "dog", "horse", "motorbike", "person", "pottedplant", "sheep",
           "sofa", "train", "tvmonitor"]
COLORS = np.random.uniform(0, 255, size=(len(CLASSES), 3))

prototxt = '/home/pi/openvino/openvino-pi-object-detection/MobileNetSSD_deploy.prototxt'
caffemodel = '/home/pi/openvino/openvino-pi-object-detection/MobileNetSSD_deploy.caffemodel'

q_pict = Queue(maxsize=5)  # queue for web picts
q_status = Queue(maxsize=5) # queue for web status

# load our serialized model from disk
print("[INFO] loading model...")
net = cv2.dnn.readNetFromCaffe(prototxt, caffemodel)
net.setPreferableTarget(cv2.dnn.DNN_TARGET_MYRIAD)
print("[INFO] starting video stream...")

resolution400 = (400,300) # default
resolution800 = (800, 600)
resolution640 = (640, 480)

cur_resolution = resolution800
scale_factor = cur_resolution[0]/400
resolution_str = str(cur_resolution[0]) +'x' +str(cur_resolution[1])
vs = VideoStream(usePiCamera=True, resolution=cur_resolution).start()
time.sleep(2.0)
print ('camera frame shape - ', vs.read().shape)

GREEN_TAG = 0
RED_TAG = 1
interval = 3


def green_light(arg, interval=3):
    global timer
    # print('зашли ', arg)
    if not timer.is_alive() or arg:
        # print('таймер ', timer)
        if arg:
            GPIO.output(GREEN, 1)
            GPIO.output(RED, 0)
        else:
            GPIO.output(GREEN, 0)
            GPIO.output(RED, 1)
        timer = Timer(interval, lambda *a: a)
        timer.start()


def box_square(box):
    (startX, startY, endX, endY) = box.astype("int")
    square = (endX - startX) * (endY - startY)
    return square


# timer for green light delay
timer = Timer(interval, lambda *a: a) 
timer.start()
# off green
green_light(0)


def wdt_func(): # restart system if wdt is not alive
    print ('save before reboot')
    ts = time.asctime( time.localtime(time.time()) )
    with open("/home/pi/detector.log", "a") as file:  # append reboot time to the file
        print(ts, sep='\n ', file=file) 
    os.system('sudo reboot')


def put_queue(queue, data):
    # print('put', q_pict.qsize())
    if not queue.qsize() > 3:  # помещать в очередь для web только если в ней не больше 3-х кадров ( статусов )
        # нем смысла совать больше если web не работает и никто не смотрит, или если статус никто не выбирает,
        # ато выжрет всю память однако
        queue.put(data)


def web_is_on():
    """ проверяем работает-ли web путем оценки длины очереди web картинок.
        картинкииз очереди выгребает Flask/
        если никто из этой очереди не get, значит web не работает"""
    return not q_pict.qsize() > 2


def proc():
    global vis, GREEN_TAG, RED_TAG, interval
    # timer to restart detector when main thread crashes
    # when USB traffic with Intel NCStick problem occurs
    wdt_tmr = Timer(30, wdt_func) # отключено на время отладки
    wdt_tmr.start()# отключено на время отладки

    for i, param in enumerate(sys.argv):
        """ осталось от старого времени. не актуально, кандидат на удаление"""
        # print ('\npar', i," !- ", param)
        if param == "vis":
            print ("Visual mode")
            # set xMode
            vis = True

    while True:
        wdt_tmr.cancel()# отключено на время отладки
        wdt_tmr = Timer(10, wdt_func)# отключено на время отладки
        wdt_tmr.start()# отключено на время отладки
        frame = vs.read()
        if web_is_on(): # если web работает копируем исходный фрейм для него
            # print('web', q_pict.qsize())
            wframe = frame.copy()
        else:
            pass #wframe = frame
        # print ('frame.shape',frame.shape)
        frame = imutils.resize(frame, width=400)

        # draw frame resolution
        cv2.putText(wframe, resolution_str, (15, 30), cv2.FONT_HERSHEY_DUPLEX, 0.5, 255, 1)
        # draw current time
        time_str = os.popen("date").read()[:-1]
        cv2.putText(wframe, time_str, (15, 15), cv2.FONT_HERSHEY_DUPLEX, 0.5, 255, 1)

        # grab the frame dimensions and convert it to a blob
        (h, w) = frame.shape[:2]
        # Caffe
        blob = cv2.dnn.blobFromImage(frame, 0.007843, (300, 300), 127.5)
        net.setInput(blob)
        detections = net.forward()

        # loop over the detections
        for i in np.arange(0, detections.shape[2]):
            # extract the confidence (i.e., probability) associated with
            # the prediction
            confidence = detections[0, 0, i, 2]
            # filter out weak detections by ensuring the `confidence` is
            # greater than the minimum confidence
            if confidence > confidence_tresh: # args["confidence"]:
                # extract the index of the class label from the
                # `detections`, then compute the (x, y)-coordinates of
                # the bounding box for the object
                idx = int(detections[0, 0, i, 1])
                box = detections[0, 0, i, 3:7] * np.array([w, h, w, h])
                if idx == 15 and box_square(box) > 5000 and box_square(box) < 50000: # показываем рамки тока для пешеходов
                    # ограничения >5k нужно чтобы оч маленькие объекты не цеплял, а меньше 20к нужны чтобы не было ложных сработок
                    # т.к. иногда ему кажется что перед ним person во весь экран
                    # print(box_square(box), '\n\n')
                    GREEN_TAG = 1

                    if web_is_on():  # если web работает рисуем картинку для него
                        box *= scale_factor  #
                        (startX, startY, endX, endY) = box.astype("int")

                        # draw the prediction on the frame
                        # label = "{}: {:.2f}% - {}".format(CLASSES[idx],confidence * 100, box_square(box))
                        label = "{}: {:.2f}% ".format(CLASSES[idx],confidence * 100)
                        cv2.rectangle(wframe, (startX, startY), (endX, endY), 100, 2)
                        y = startY - 15 if startY - 15 > 15 else startY + 15
                        cv2.putText(wframe, label, (startX, y),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, 100, 2)



                if idx == 15 and box_square(box) > 5000 and box_square(box) < 50000: # дублирует предыдущий if ( для экспериментов)
                    # switch if person and box is big enough
                    # < 50000 supress wrong behavior when somth close the lens -
                    # appears some large box with wrong repson detection
                    # GREEN_TAG = 1
                    pass
        # off GREEN

        put_queue(q_pict, wframe)  # put the picture for web in the picture Queue

        ###green_light(0)
        # on GREEN if TAG = 1
        green_light(GREEN_TAG)
        put_queue(q_status, GREEN_TAG)
        GREEN_TAG = 0

        if vis:
            # show the output frame (not actual anymore candidate for del)
            cv2.imshow("Frame", frame)

            key = cv2.waitKey(1) & 0xFF
            # if the `q` key was pressed, break from the loop
            if key == ord("q"):
                break

    green_light(0)
    cv2.destroyAllWindows()
    vs.stop()
