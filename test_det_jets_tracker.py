""" gets detections from some detector. Build treks based on iou algorythm.
    gets frames, make iou's to each in the frames in detection set. 
    Assign frame to the end of the track. Kalman filtering implemented.
"""
import jetson.inference
import jetson.utils
from threading import Timer, Thread, Lock
from multiprocessing.dummy import Process, Queue
import time
import sys
import os
import math
import cv2
import numpy as np
from common import clock, draw_str, draw_rects
from RepeatedTimer_ import RepeatedTimer
from haar_cascade_detector import detect
from iou import bb_intersection_over_union
# from track_iou_kalman_cv2 import Track
from track_iou import Track
# import Jetson.GPIO as GPIO

#cascade_path = 'vehicles_cascadeLBP_w25_h25_p2572_n58652_neg_roof.xml'
# cascade_path = 'vehicle_cascadeLBP_w20_h20_p2139.xml'

q_pict = Queue(maxsize=5)  # queue for web picts
q_status = Queue(maxsize=5)  # queue for web status

# jetson inference networks list
network_lst = ["ssd-mobilenet-v2",  # 0 the best one???
               "ssd-inception-v2",  # 1
               "pednet",           # 2
               "alexnet",          # 3
               "facenet",          # 4
               "googlenet"         # 5 also good
               ]

network = network_lst[0]

threshold = 0.2  # for jetson inference object detection
width = 800#1920  # 640 
height = 600#1080 # 480 
camera_src = '/dev/video1' # for USB
camera_src = '0' # for sci
overlay = "box,labels,conf"
print("[INFO] loading model...")
net = jetson.inference.detectNet(network, sys.argv, threshold)
camera = jetson.utils.gstCamera(width, height, camera_src)

cur_resolution = (width, height)
scale_factor = cur_resolution[0]/400
resolution_str = str(cur_resolution[0]) + 'x' + str(cur_resolution[1])

# interval = 3
visual = True  # visual mode

tracks = []
iou_tresh = 0.4  # treshold for tracker append criteria
video_src = "/home/a/dt3_jetson/U524806_3.avi"
# video_src = "/home/a/dt3_jetson/jam_video_dinamo.avi"
# video_src = "http://95.215.176.83:10090/video30.mjpg?resolution=&fps="
# video_src = "http://62.117.66.226:5118/axis-cgi/mjpg/video.cgi?camera=1&dummy=0.45198500%201389718502" # sokolniki shlagbaum
# video_src = "https://rtsp.me/embed/dKfKFNTz/" # doesnt work
# video_src = "G:/fotovideo/video_src/usb2.avi"
bboxes = []  # bbox's of each frame
max_track_lifetime = 4  # if it older than num secs it removes
USE_CAMERA = 1  # True - camera, False - video file
USE_GAMMA = False # True - for night video

# only for sci camera
# framerate=(fraction)60/1 - optimum rate
camera_str = f"nvarguscamerasrc ! video/x-raw(memory:NVMM), width=(int){str(width)}, \
		height=(int){str(height)},format=(string)NV12, framerate=(fraction)60/1 ! nvvidconv flip-method=2 ! \
        video/x-raw, width=(int)1280, height=(int)720, format=(string)BGRx ! \
        videoconvert ! video/x-raw, format=(string)BGR ! appsink"

camera_str2 = f"nvarguscamerasrc ! video/x-raw(memory:NVMM), width=(int){str(width)}, \
		height=(int){str(height)},format=(string)NV12, framerate=(fraction)60/1 ! nvvidconv flip-method=2 ! \
        video/x-raw, format=(string)BGRx ! \
        videoconvert ! video/x-raw, format=(string)BGR ! appsink"


def gamma(image, gamma=0.4):
    '''makes gamma coorection'''
    img_float = np.float32(image)
    max_pixel = np.max(img_float)
    img_normalized = img_float/max_pixel
    gamma_corr = np.log(img_normalized) * gamma
    gamma_corrected = np.exp(gamma_corr)*255.0
    gamma_corrected = np.uint8(gamma_corrected)
    return gamma_corrected


def ts():
    return time.time()


def proc():
    # global interval
    # timer to restart detector when main thread crashes
    # wdt_tmr = Timer(30, wdt_func) # отключено на время отладки
    # wdt_tmr.start() # отключено на время отладки

    # if memmon: # mamory allocation monitoring
    # import tracemalloc
    # tracemalloc.start()

    if USE_CAMERA:
        cap = cv2.VideoCapture(camera_str, cv2.CAP_GSTREAMER) # for SCI camera
    else:
        cap = cv2.VideoCapture(video_src)

    prev_bboxes = []  # bboxes to draw from previous frame

    while True:
        # if memmon:
        # snapshot = tracemalloc.take_snapshot()
        # top_stats = snapshot.statistics('lineno')

        # wdt_tmr.cancel()# отключено на время отладки
        # wdt_tmr = Timer(10, wdt_func)# отключено на время отладки
        # wdt_tmr.start()# отключено на время отладки
        tss= ts() # 90 ms , 60 w/o/ stdout

        ret, img = cap.read()
        # tss= ts() #78 ms
        
        if not ret:
            if USE_CAMERA:
                # cap = cv2.VideoCapture(camera_src) # for USB camera
                cap = cv2.VideoCapture(camera_str, cv2.CAP_GSTREAMER) # for SCI camera
            else:
                cap = cv2.VideoCapture(video_src)
            ret, img = cap.read()
            
        img = cv2.resize(img, (640, 480))
        height, width = img.shape[:2]

        if USE_GAMMA:
            img = gamma(img, gamma=0.8)

        # needs for cuda to add new one channel
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGBA)

        # give roi
        up_bord = int(0.2*height)
        img_c = img[up_bord:height, 0:width]
        height, width = img_c.shape[:2]
        frame = jetson.utils.cudaFromNumpy(img_c)

        # frame, width, height = camera.CaptureRGBA(zeroCopy = True)
        detections = net.Detect(frame, width, height, overlay)
        # for detection in detections:
        #    if detection.ClassID == 3: # car in coco
        #    print ('car detection confidence -', detection.Confidence)

        jetson.utils.cudaDeviceSynchronize()
        # create a numpy ndarray that references the CUDA memory
        # it won't be copied, but uses the same memory underneath

        frame = jetson.utils.cudaToNumpy(frame, width, height, 4)

        #print ("img shape {}".format (aimg1.shape))
        frame = cv2.cvtColor(frame.astype(np.uint8), cv2.COLOR_RGBA2BGR)
        # draw rectangles over the inference drawing
        # selecting the bboxes
        bboxes = []
        for box in prev_bboxes:
            cv2.rectangle(frame, (box[0], box[1]),
                          (box[2], box[3]), (0, 255, 0), 1)

        prev_bboxes = []

        for detection in detections:
            # print('  class', detection.Area, detection.ClassID)
            # print('detection', detection)
            x1 = int(detection.Left)
            y1 = int(detection.Top)
            x2 = int(detection.Right)
            y2 = int(detection.Bottom)
            # if bbox is connected to the frame borders, don't take it,
            # track deistorted in this case
            bord_lim = 10
            if (x1 > bord_lim) & (height - y2 > bord_lim) & (y1 > bord_lim) & (width - x2 > bord_lim):
                bboxes.append((x1, y1, x2, y2))
            # draw rectangle
            cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 0, 0), 1)
            # if detection.ClassID == 3: # car in coco
            # print ('car detection confidence -', detection.Confidence)
            prev_bboxes.append((x1, y1, x2, y2))

        wframe = frame  # .copy()
        # if web_is_on(): # если web работает копируем исходный фрейм для него
        ####### print('web', q_pict.qsize())
        # wframe = frame.copy()
        #frame = cv2.resize(frame, width=400)
        # assign founded detectons to the existing tracks
        for i, bbox in enumerate(bboxes):
            # print('bbox', bbox)
            assign_flag = 0  # признак того, что для данного ббокса не было назначения ни одному треку
            for track in tracks:
                if (not assign_flag) & track.track_assignment(bbox):
                    assign_flag = 1  # если назначено, переходим к следующему ббоксу
            # if pass thru the all tracks and no assignment, make a new track with it
            if (assign_flag == 0):
                # if len(tracks)<=0: # if acts, only one track exist
                tracks.append(Track(bbox, iou_tresh))

        # remove very old tracks and bad tracks
        for i, track in enumerate(tracks):
            # if max track life time is over, or track isn't appended for more than 1 sec, del it
            if (ts() - track.ts > max_track_lifetime) | ((ts() - track.ts > 3) & (len(track.points) < 3)):
                print('del', i, '/', len(tracks))
                del(tracks[i])

        # draw tracks
        for track in tracks:
            track.draw_tracks(frame)
        # draw frame resolution
        if net.GetNetworkFPS() != math.inf:
            fps = str(round(net.GetNetworkFPS()))
        else:
            fps = 'inf...'
        resolution_str_ = str(width) + 'x' + str(height)
        tot_elapsed_time = str(round((ts()-tss), 2))
        res_string = resolution_str_+'  fps-' + fps + \
            ' elps ' + tot_elapsed_time + ' net-' + network
        cv2.putText(wframe, res_string, (15, 30),
                    cv2.FONT_HERSHEY_DUPLEX, 0.5, 255, 1)
        # draw current time 
        time_str = ''#os.popen("date").read()[:-1] # eats fckng 120 ms in inference!!!! 120 Karl!!!!
        # cv2.putText(wframe, time_str, (15, 15),
                    # cv2.FONT_HERSHEY_DUPLEX, 0.5, 255, 1)
        # put_queue(q_pict, wframe)  # put the picture for web in the picture Queue
        # put_queue(q_status, GREEN_TAG)

        if visual:
            # show the output frame (not actual anymore candidate for del)
            # cv2.namedWindow("Frame", cv2.WINDOW_NORMAL)
            # img = cv2.resize(img, (800, 600))
            
            frame_rate_str = f'{(time.time()-tss)*1000:.4} msec/frm'
            cv2.putText(wframe, frame_rate_str, (15, 15), cv2.FONT_HERSHEY_DUPLEX, 0.5, (255,255,255), 1)
            
            cv2.imshow("Frame", wframe)
            key = cv2.waitKey(1) & 0xFF
            # if the `ESC` key was pressed, break from the loop
            if key == 27:
                break

        # if memmon:
        #     print("[ Top 10 ]")
        #     for stat in top_stats[:10]:
        #         print(stat)
    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    proc()
