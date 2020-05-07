#!/usr/bin/env python3
from imutils.video import VideoStream
from threading import Timer, Thread, Lock
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

# load our serialized model from disk
print("[INFO] loading model...")
net = cv2.dnn.readNetFromCaffe(prototxt, caffemodel)
net.setPreferableTarget(cv2.dnn.DNN_TARGET_MYRIAD)
print("[INFO] starting video stream...")
vs = VideoStream(usePiCamera=True).start()
time.sleep(2.0)
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
#	global wdt_tmr, lock
#	print ('wdt_func started')
#	while True:
#		lock.acquire()
#		if not wdt_tmr.is_alive(): # reboot device in main process brakes
			# because of usb communication problem
			# save reboot time in file
    print ('save before reboot')
    ts = time.asctime( time.localtime(time.time()) )
    with open("/home/pi/detector.log", "a") as file:  # append reboot time to the file
        print(ts, sep='\n ', file=file) 
    os.system('sudo reboot')
#		lock.release()	
#		time.sleep(5)	

# timer to restart detector when main thread crashes
# when USB traffic with Intel NCStick problem occurs
wdt_tmr = Timer(30, wdt_func) 
wdt_tmr.start()
# lock=Lock()

for i, param in enumerate(sys.argv):
    # print ('\npar', i," !- ", param)
    if param == "vis":
        print ("Visual mode")
        # set xMode
        vis = True


#wdt_thread = Thread(target=wdt_func, daemon=True)
#wdt_thread = Thread(target=wdt_func)
#wdt_thread.start()
#loop_num =0

# loop over the frames from the video stream
while True:
    # start watchdog 
    #lock.acquire()
    wdt_tmr.cancel()
    wdt_tmr = Timer(10, wdt_func)
    wdt_tmr.start()
    #lock.release()
    #loop_num += 1
    #print ('loop ',loop_num )
    # grab the frame from the threaded video stream and resize it
    # to have a maximum width of 400 pixels
    frame = vs.read()
    frame = imutils.resize(frame, width=400)

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
            if vis:
                # print(box_square(box), '\n\n')
                (startX, startY, endX, endY) = box.astype("int")

                # draw the prediction on the frame
                label = "{}: {:.2f}% - {}".format(CLASSES[idx],
                                         confidence * 100, box_square(box))
                cv2.rectangle(frame, (startX, startY), (endX, endY), COLORS[idx], 2)
                y = startY - 15 if startY - 15 > 15 else startY + 15
                cv2.putText(frame, label, (startX, y),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, COLORS[idx], 2)
            # light on the GREEN
            if idx == 15 and box_square(box) > 5000 and box_square(box) < 50000:
                # switch if person and box is big enough
                # < 50000 supress wrong behavior when somth close the lens -
                # appears some large box with wrong repson detection
                GREEN_TAG = 1
    # off GREEN

    ###green_light(0)
    # on GREEN if TAG = 1
    green_light(GREEN_TAG)
    GREEN_TAG = 0

    if vis:
        # show the output frame
        cv2.imshow("Frame", frame)
    
        key = cv2.waitKey(1) & 0xFF
        # if the `q` key was pressed, break from the loop
        if key == ord("q"):
            break

green_light(0)
cv2.destroyAllWindows()
vs.stop()
