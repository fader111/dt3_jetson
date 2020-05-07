""" gets detections from some detector. Build treks based on iou algorythm.
    gets frames, make iou's to each in the frames in detection set. 
    Assign frame to the end of the track

    Additional functionality:
        kalman filter make thrack smooth
"""
import jetson.inference
import jetson.utils
from threading import Timer, Thread, Lock
from multiprocessing.dummy import Process, Queue
import time
import sys, os, math
import cv2
import numpy as np
from common import clock, draw_str, draw_rects
from RepeatedTimer_ import RepeatedTimer
from haar_cascade_detector import detect, gamma
from iou import bb_intersection_over_union
from track_iou import Track
# import Jetson.GPIO as GPIO

#cascade_path = 'vehicles_cascadeLBP_w25_h25_p2572_n58652_neg_roof.xml'
# cascade_path = 'vehicle_cascadeLBP_w20_h20_p2139.xml'


q_pict = Queue(maxsize=5)  # queue for web picts
q_status = Queue(maxsize=5) # queue for web status

# jetson inference networks list
network_lst = [ "ssd-mobilenet-v2", # 0 the best one???
                "ssd-inception-v2", # 1
                "pednet",           # 2 
                "alexnet",          # 3 
                "facenet",          # 4
                "googlenet"         # 5 also good
                ]

network = network_lst[0]

threshold = 0.5
width = 640
height = 480
camera_src = '/dev/video0'
overlay = "box,labels,conf"
print("[INFO] loading model...")
net = jetson.inference.detectNet(network, sys.argv, threshold)
camera = jetson.utils.gstCamera(width, height, camera_src)

cur_resolution = (width, height)
scale_factor = cur_resolution[0]/400
resolution_str = str(cur_resolution[0]) + 'x' + str(cur_resolution[1])

interval = 3
visual = True

tracks = []
iou_tresh = 0.4
video_src = "U524806_3.avi"
# video_src = "http://95.215.176.83:10090/video30.mjpg?resolution=&fps=" 
# video_src = "http://62.117.66.226:5118/axis-cgi/mjpg/video.cgi?camera=1&dummy=0.45198500%201389718502" # sokolniki shlagbaum
# video_src = "https://rtsp.me/embed/dKfKFNTz/" # doesnt work
# video_src = "G:/fotovideo/video_src/usb2.avi"
bboxes = [] # bbox's of each frame
max_track_lifetime = 3 # sec
USE_GAMMA = False

kalman_coef = 0.0003
mp = np.array((2,1), np.float32) # kalman measurement
tp = np.zeros((2,1), np.float32) # kalman tracked / prediction

def ts():
    return time.time()
    


def proc():
    global interval
    # timer to restart detector when main thread crashes
    # wdt_tmr = Timer(30, wdt_func) # отключено на время отладки
    # wdt_tmr.start() # отключено на время отладки

    # if memmon: # mamory allocation monitoring 
        # import tracemalloc
        # tracemalloc.start()
    cap = cv2.VideoCapture(video_src)

    # kalman = cv2.KalmanFilter(4, 2)
    # kalman.measurementMatrix = np.array([[1,0,0,0],[0,1,0,0]],np.float32)
    # kalman.transitionMatrix = np.array([[1,0,1,0],[0,1,0,1],[0,0,1,0],[0,0,0,1]],np.float32)
    # kalman.processNoiseCov = np.array([[1,0,0,0],[0,1,0,0],[0,0,1,0],[0,0,0,1]],np.float32) * kalman_coef
    
    while True:
        # if memmon:
            # snapshot = tracemalloc.take_snapshot()
            # top_stats = snapshot.statistics('lineno')
       
        # wdt_tmr.cancel()# отключено на время отладки
        # wdt_tmr = Timer(10, wdt_func)# отключено на время отладки
        # wdt_tmr.start()# отключено на время отладки
        tss = ts()
        ret, img = cap.read()
        if not ret:
            cap = cv2.VideoCapture(video_src) # reopen capture when video file is over
            ret, img = cap.read()

        img = cv2.resize(img, (640, 480))
        height, width = img.shape[:2]

        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGBA) # needs for cuda to add new one channel
        
        # give roi
        up_bord = int(0.2*height)
        img_c = img[up_bord:height, 0:width] 
        height, width = img_c.shape[:2]
        frame = jetson.utils.cudaFromNumpy(img_c)

        # frame, width, height = camera.CaptureRGBA(zeroCopy = True)

        detections = net.Detect(frame, width, height, overlay)
        #for detection in detections:
        #    if detection.ClassID == 3: # car in coco 
        #       print ('car detection confidence -', detection.Confidence)

        jetson.utils.cudaDeviceSynchronize()
        # create a numpy ndarray that references the CUDA memory
        # it won't be copied, but uses the same memory underneath
        frame = jetson.utils.cudaToNumpy(frame, width, height, 4)
        #print ("img shape {}".format (aimg1.shape))
        frame = cv2.cvtColor(frame.astype(np.uint8), cv2.COLOR_RGBA2BGR)
        
        # draw rectangles over the inference drawing
        # selecting the bboxes
        bboxes = []
        for detection in detections:
            # print('  class', detection.Area, detection.ClassID)
            # print('detection', detection)
            x1 = int(detection.Left)
            y1 = int(detection.Top)
            x2 = int(detection.Right)
            y2 = int(detection.Bottom)
            # if bbox touches the frame borders, don't take it, 
            # track deistorted in this case 
            bord_lim = 10
            if (x1 > bord_lim) & (height - y2 > bord_lim) & (y1 > bord_lim) & (width - x2 > bord_lim): 
                bboxes.append((x1, y1, x2, y2))
            # draw rectangle    
            cv2.rectangle(frame, (x1, y1), (x2, y2), (255,0,0),1)
            # if detection.ClassID == 3: # car in coco 
                # print ('car detection confidence -', detection.Confidence)


        wframe = frame #.copy()
        # if web_is_on(): # если web работает копируем исходный фрейм для него
            ####### print('web', q_pict.qsize())
            # wframe = frame.copy()
        #frame = cv2.resize(frame, width=400)
        # assign founded detectons to the existing tracks
        for i, bbox in enumerate(bboxes):
            # print('bbox', bbox)
            assign_flag = 0 # признак того, что для данного ббокса не было назначения ни одному треку
            for track in tracks:
                if (not assign_flag) & track.track_assignment(bbox):
                    # bbox connected to the track. ok, add the kalman filtered point to it also
                    assign_flag = 1 # если назначено, переходим к следующему ббоксу
            # if pass thru the all tracks and no assignment, make a new track with it
            if assign_flag == 0: 
                tr = Track(bbox, iou_tresh) 
                tracks.append(tr)

        
        # remove very old tracks and bad tracks
        for i, track in enumerate(tracks):
            # if max track life time is over, or track isn't appended for more than 1 sec, del it
            if (ts() - track.ts > max_track_lifetime) | ((ts() - track.ts > 3) & (len(track.points) < 5)):
                print ('del',i, '/',len(tracks))
                del(tracks[i])
            


        # draw tracks
        for track in tracks:
            track.draw_tracks(frame)

        # 

        # draw frame resolution
        if net.GetNetworkFPS() != math.inf:
            fps = str(round(net.GetNetworkFPS()))
        else: 
            fps = 'inf...'
        resolution_str = str(width) + 'x' + str(height)
        tot_elapsed_time = str(round((ts()-tss), 2))
        res_string = resolution_str+'  fps-'+ fps + ' elps ' + tot_elapsed_time + ' net-' + network
        cv2.putText(wframe, res_string, (15, 30), cv2.FONT_HERSHEY_DUPLEX, 0.5, 255, 1)
        # draw current time
        time_str = os.popen("date").read()[:-1]
        cv2.putText(wframe, time_str, (15, 15), cv2.FONT_HERSHEY_DUPLEX, 0.5, 255, 1)

        # put_queue(q_pict, wframe)  # put the picture for web in the picture Queue

        # put_queue(q_status, GREEN_TAG)
        
        if visual:
            # show the output frame (not actual anymore candidate for del)
            cv2.imshow("Frame", frame)
            key = cv2.waitKey(1) & 0xFF
            # if the `ESC` key was pressed, break from the loop
            if key == 27:
                break
     

        # if memmon:
        #     print("[ Top 10 ]")
        #     for stat in top_stats[:10]:
        #         print(stat)


    # green_light(0)


if __name__ == "__main__":
    proc()
