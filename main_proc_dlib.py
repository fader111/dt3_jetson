""" gets detections from jetson cnn-based detectors.
    Build tracks based on dlib tracker which updated by detector using iou algorythm.
    Kalman filtering implemented???
"""
# import jetson.inference
# import jetson.utils
from threading import Timer, Thread, Lock
from multiprocessing.dummy import Process, Queue
# from multiprocessing import Process, Queue
import time
import sys
import os
import math
import cv2
import numpy as np
import json
from RepeatedTimer_ import RepeatedTimer
from common_tracker import *
from get_net_settings import *
from iou import bb_intersection_over_union
# from track_iou_kalman_cv2 import Track
from track_dlib import Track
from dlib import correlation_tracker
from shapely.geometry import Point, Polygon, box
from detect_zones import Ramka
# import Jetson.GPIO as GPIO

# cascade_path = 'vehicles_cascadeLBP_w25_h25_p2572_n58652_neg_roof.xml'
# cascade_path = 'vehicle_cascadeLBP_w20_h20_p2139.xml'

q_pict = Queue(maxsize=5)       # queue for web picts
q_settings = Queue(maxsize=5)   # queue for ip and other settings to sent from web client to python
q_ramki = Queue(maxsize=5)      # polygones paths
q_status = Queue(maxsize=5)     # current status of process for web.

# jetson inference networks list
network_lst = ["ssd-mobilenet-v2",  # 0 the best one???
               "ssd-inception-v2",  # 1
               "pednet",            # 2
               "alexnet",           # 3
               "facenet",           # 4
               "googlenet"          # 5 also good
               ]

network = network_lst[1]

threshold = 0.2         # 0.2 for jetson inference object detection
iou_tresh_perc = 10     # tresh for cnn detection bbox and car detecting zone intersection in percents
width = 1920            # 640 width settings for camera capturing
height = 1080           # 480 height for the same
proc_width = 640        # x size of window for processing with CNN 
proc_height = 480       # y size
# camera_src = '/dev/video1'  # for USB camera
# camera_src = '0'  # for sci Gstreamer 
# camera = jetson.utils.gstCamera(width, height, camera_src) # also possible capturing way
overlay = "box,labels,conf"
print("[INFO] loading model...")
# # net = jetson.inference.detectNet(network, sys.argv, threshold)

cur_resolution = (width, height)
scale_factor = cur_resolution[0]/400
resolution_str = str(cur_resolution[0]) + 'x' + str(cur_resolution[1])


visual = True  # visual mode
winMode = False # debug mode for windows - means that we are in windows now

if 'win' in sys.platform: 
    proj_path = 'C:/Users/ataranov/Projects/dt3_jetson/'  # путь до папки проекта
    winMode = True
else:
    proj_path = '/home/a/dt3_jetson/'  # путь до папки проекта

# video_src = "/home/a/Videos/U524806_3.avi"
if 'win' in sys.platform:
    video_src = "G:/U524802_1_695_0_new.avi"
else:
    video_src = "/home/a/Videos/U524802_1_695_0_new.avi" # 2650 x 2048
# video_src = '/home/a/Videos/lenin35_640.avi' # h 640
# video_src = "/home/a/dt3_jetson/jam_video_dinamo.avi" gets some distorted video IDKW
# video_src = "http://95.215.176.83:10090/video30.mjpg?resolution=&fps="
# video_src = "http://62.117.66.226:5118/axis-cgi/mjpg/video.cgi?camera=1&dummy=0.45198500%201389718502" # sokolniki shlagbaum
# video_src = "https://rtsp.me/embed/dKfKFNTz/" # doesnt work
# video_src = "G:/fotovideo/video_src/usb2.avi"

# True - camera, False - video file /80ms per frame on camera, 149 on video
USE_CAMERA = False
USE_GAMMA = False  # True - for night video

# bboxes = []  # bbox's of each frame # candidate for removing
max_track_lifetime = 2  # if it older than num secs it removes
if USE_CAMERA:
    detect_phase_period = 10  # detection phase period in frames
else:
    detect_phase_period = 5  # detection phase period in frames

iou_tresh = 0.2  # treshold for tracker append criteria 0.4 less- more sensitive, more mistakes

# only for sci camera
# framerate=(fraction)60/1 - optimum rate
camera_str = f"nvarguscamerasrc ! video/x-raw(memory:NVMM), width=(int){str(width)}, \
		height=(int){str(height)},format=(string)NV12, framerate=(fraction)60/1 ! nvvidconv flip-method=2 ! \
        video/x-raw, width=(int)1280, height=(int)720, format=(string)BGRx ! \
        videoconvert ! video/x-raw, format=(string)BGR ! appsink"

# not used,  just sample
camera_str2 = f"nvarguscamerasrc ! video/x-raw(memory:NVMM), width=(int){str(width)}, \
		height=(int){str(height)},format=(string)NV12, framerate=(fraction)60/1 ! nvvidconv flip-method=2 ! \
        video/x-raw, format=(string)BGRx ! \
        videoconvert ! video/x-raw, format=(string)BGR ! appsink"

poligones_filepath = proj_path + 'polygones.dat'
settings_filepath  = proj_path + 'settings.dat'


def read_setts_from_syst(filePath):
    ''' read settings ip and others from system and config file
        filePath = full path to settings.dat
    '''
    # print ('filePath' + filePath)
    settings_ = {"ip": get_ip() + '/' + get_bit_number_from_mask(get_mask()),
                "gateway": get_gateway(),
                "hub": get_hub(filePath),
                "calibration":get_settings(filePath)["calibration"]
            }
    return settings_


def read_polygones_from_file(filePath):
    ''' read polygones from file
        filePath = full path to polygones.dat '''
    try:
        with open(filePath, 'r') as f:
            poligs = f.read()  
        print(f'polygones read from file: {poligs}')
        return json.loads(poligs)
    except:
        print(u"Couldn't read polygones from polygones.dat")
        return {}


def send_det_status_to_hub(addrString, det_status):  
    # передача состояний рамок на концентратор методом POST
    # addrString = 'http://' + hubAddress + '/detect'
    # must be a list to get an argument as a reference
    # print('                              hub ', addrString, det_status)

    try:
        requests.get(addrString[0], timeout=(0.1, 0.1))
        ans = requests.post(addrString, json={"cars_detect": det_status}) 
        # return ans.text
    except:
        pass
        # print('expt from  sendColorStatusToHub', )
        # return 'Disconnected...'


def put_queue(queue, data):
    # print('put', q_pict.qsize())
    if not queue.qsize() > 3:  # помещать в очередь для web только если в ней не больше 3-х кадров ( статусов )
        # нем смысла совать больше если web не работает и никто не смотрит, или если статус никто не выбирает,
        # ато выжрет всю память однако
        queue.put(data)


def proc():
    # timer to restart detector when main thread crashes
    # wdt_tmr = Timer(30, wdt_func) # отключено на время отладки
    # wdt_tmr.start() # отключено на время отладки

    # if memmon: # mamory allocation monitoring
    # import tracemalloc
    # tracemalloc.start()

    if USE_CAMERA:
        # cap = cv2.VideoCapture(camera_src) # for GSTreamer handling camera
        cap = cv2.VideoCapture(camera_str, cv2.CAP_GSTREAMER)  # for SCI camera
    else:
        cap = cv2.VideoCapture(video_src)


    # prev_bboxes = []  # bboxes to draw from previous frame
    key_time = 1
    new_tr_number = 0   # for tracks numeration
    frm_number = 0
    ramki_scaled = []   # ramki scaled mass for Instances of Ramka
    ramki_status = []   # mass of 0 and 1 for send to hub as json, len = len(ramki_scaled), 0 if ramka off, 1 - if on
    # need to have only one reference, thats why below fild created.
    ramki_status_ = []  # copy of ramki status to sent to repeated timer for sending to hub. 

    bboxes = []
    tracks = []         # list for Track class instances
    stop_ = False       # aux for detection break
    polygon_sc = []     # scaled polygon points
    calibrPoints = []   # list of points of calibration Polygon on road
    calibrPoints_sc = []# scaled list of points of calibration Polygon
    w_web = 800         # web picture width
    h_web = 600         # web picture hight
    
    # Init polygones at start processing
    polygones = read_polygones_from_file(poligones_filepath) # json c рамками и направлениями
    ramki_status = [0 for i in range(len(polygones["polygones"]))]
    ramki_status_ =[0 for i in range(len(polygones["polygones"]))]
    # Init ip and other settings from system
    settings = read_setts_from_syst(proj_path + "settings.dat")

    # before start 
    if ("polygones") in polygones:
        w_web, h_web = polygones["frame"]
        for k, polygon in enumerate(polygones["polygones"]):
            polygon_sc = [[x*proc_width//w_web, y*proc_height//h_web] for x, y in polygon]
            ramki_scaled.append(Ramka(polygon_sc, polygones["ramkiDirections"][k], proc_height))

    if ("calibration") in settings:
        calibrPoints = json.loads(settings["calibration"])
        calibrPoints_sc = [[x*proc_width//w_web, y*proc_height//h_web] for x, y in calibrPoints]
    
    # status of process must send to hub - device wich convert detector packets to the 
    # physical signals. Do it with repeated timer. Update each 400ms
    
    addrString = ['http://' + settings["hub"] + '/detect']

    rtUpdStatusForHub = RepeatedTimer(0.4, send_det_status_to_hub, addrString, ramki_status_)
    rtUpdStatusForHub.start()

    while True:
        # if memmon:
        # snapshot = tracemalloc.take_snapshot()
        # top_stats = snapshot.statistics('lineno')
        # wdt_tmr.cancel()# отключено на время отладки
        # wdt_tmr = Timer(10, wdt_func)# отключено на время отладки
        # wdt_tmr.start()# отключено на время отладки
        frm_number += 1
        tss = time.time()  # 90 ms , 60 w/o/ stdout
        ret, img = cap.read()
        # tss= time.time() #78 ms

        if len(ramki_status) == len(ramki_status_):
            for i in range(len(ramki_status)):
                ramki_status_[i] = ramki_status[i]

        if not ret:
            if USE_CAMERA:
                # cap = cv2.VideoCapture(camera_src) # for USB camera
                cap = cv2.VideoCapture(
                    camera_str, cv2.CAP_GSTREAMER)  # for SCI camera
            else:
                cap = cv2.VideoCapture(video_src)
            ret, img = cap.read()

        orig_img = img
        while not ret:
            ret, img = cap.read()
            print ('wait..')
        img = cv2.resize(img, (proc_width, proc_height))
        # img = cv2.resize(img, (800, 604))
        height, width = img.shape[:2]
        # print(f'orig_img.shape = {orig_img.shape}')

        if USE_GAMMA:
            img = gamma(img, gamma=0.8)

        # give roi. Roi cuted upper part of frame
        up_bord = int(0.2*height)
        img_c = img#[up_bord:height, 0:width]

        # img_c = img_c[0:height, 0:int(width/5)]

        height, width = img_c.shape[:2]
        # cv2.line(img, (0, up_bord), (width, up_bord), 255, 1)

        frame_show = frame = img_c # frame_show only for display on interface with texts, rectangles and labels
        frame_show = np.copy(frame_show) # separate frame_show to another object

        # needs for cuda to add new one channel
        img_c = cv2.cvtColor(img_c, cv2.COLOR_BGR2RGBA)  # ogiginal variant

        # Detection phase - each 2nd (5th?) frame will detect using Jetson inference
        if frm_number % detect_phase_period == 0:  # 5 - default
            # tss = time.time() # 56 w/o/ stdout on video
            '''!!!'''
            if not winMode:
                frame_cuda = jetson.utils.cudaFromNumpy(img_c)
                # tss = time.time() # 54 w/o/ stdout on video
                # frame, width, height = camera.CaptureRGBA(zeroCopy = True)
                '''!!!'''
                detections = net.Detect(frame_cuda, width, height, overlay)
                # for detection in detections:
                #    if detection.ClassID == 3: # car in coco
                #    print ('car detection confidence -', detection.Confidence)
                '''!!!'''
                jetson.utils.cudaDeviceSynchronize()
            else:
                detections = []
            # create a numpy ndarray that references the CUDA memory
            # it won't be copied, but uses the same memory underneath
            # tss = time.time() # 8-14 w/o/ stdout on video
#            frame = jetson.utils.cudaToNumpy(frame_cuda, width, height, 4)
            # tss = time.time() # 8-14 w/o/ stdout on video
#            frame = cv2.cvtColor(frame.astype(np.uint8), cv2.COLOR_RGBA2RGB)

            for detection in detections:
                # print('  class', detection.Area, detection.ClassID)
                # print('detection', detection)
                x1 = int(detection.Left)
                y1 = int(detection.Top)
                x2 = int(detection.Right)
                y2 = int(detection.Bottom)
                bbox = (x1, y1, x2, y2)

                if detection.ClassID in CLASSES:
                    # conf = round(detection.Confidence,2)
                    class_string = f'{CLASSES[detection.ClassID]} - {detection.Confidence:.2f}'
                else:
                    class_string = ('wtf?')
                    continue # go 
                
                cv2.putText(frame_show, class_string, (x1+1, y1-4), cv2.FONT_HERSHEY_SIMPLEX, 0.6, green, 1)
                cv2.rectangle(frame_show, (x1, y1), (x2, y2), green, 1)
                # if detection.ClassID == 3: # car in coco
                # print ('car detection confidence -', detection.Confidence)
                stop_ = False
                # assign bbox to the track
                for track in tracks:
                    # if bbox intesect good with last bbox in the track
                    # renew the track - delete tracker, append bbox to track,
                    # start new tracker from this bbox
                    iou_val = bb_intersection_over_union(bbox, track.boxes[-1])
                    if iou_val > iou_tresh:
                        # if bbox touches the frame borders, don't take it,
                        # track builds wrong in this case
                        stop_ = True  # prevent creating new track object
                        if not bbox_touch_the_border(bbox, height, width):
                            bboxes.append(bbox)
                            track.renew(frame, bbox, detection.ClassID, detection.Confidence)
                        else:
                            # mark this track as completed, don't update it anymore
                            track.complete = True
                            # track.boxes = [] # no, exception in iou_val above
                        break  # do not need do more with this bbox, go out
                if stop_:
                    break
                # or, if bbox didn't assingned to any track, create a new track
                tracks.append(Track(frame, bbox, new_tr_number, detection.ClassID, detection.Confidence))
                new_tr_number += 1
                if new_tr_number > 99:
                    new_tr_number = 0

        # trackig phase - update tracks
        else:
            for track in tracks:
                # update the tracker and grab the updated position
                if not track.complete:
                    track.update(frame)
                    x1, y1, x2, y2 = track.boxes[-1]
                    
                    if track.class_id in CLASSES:
                        # conf = round(detection.Confidence,2)
                        class_string = f'{CLASSES[track.class_id]} - {track.confidence:.2f}'
                    else:
                        class_string = ('wtf?')
                    
                    cv2.putText(frame_show, class_string, (x1+1, y1-4), cv2.FONT_HERSHEY_SIMPLEX, 0.6, purple, 1)
                    cv2.rectangle(frame_show, (x1, y1), (x2, y2), purple, 1)

        wframe = frame  # .copy()
        # if web_is_on(): # если web работает копируем исходный фрейм для него
        # print('web', q_pict.qsize())

        # remove frozen tracks and tracks with length less then 3 points.
        for track in tracks[:]:
            now = time.time()
            # if max track life time is over, or track isn't appended for more than 1 sec, del it
            if (now - track.ts > max_track_lifetime) | \
                ((now - track.ts > 3) & (len(track.boxes) < 3)) | \
                (now - track.renew_ts > 40):
                if key_time != 0:  # when video capturing stops tracks don't delete
                    tracks.remove(track)

        # draw tracks
        for track in tracks:
            track.draw_tracks(frame_show)
        # draw frame resolution
        '''!!!'''
        if not winMode:
            if net.GetNetworkFPS() != math.inf:
                fps = str(round(net.GetNetworkFPS()))
            else:
                fps = ' inf...'
        else:
            fps = ' ***'
        # draw detecting zones q_ramki - Queue, if the are new detecting areas, they are in 
        # this queue
        if not q_ramki.empty():
            # here it comes as a string, so convert
            polygones = json.loads(q_ramki.get()) # not zoomed right 
            # calculate polygones coordinates in scale
            ramki_scaled = []
            y_size, x_size = wframe.shape[:2]
            if ("polygones") in polygones:
                w_web, h_web = polygones["frame"]
                for k, polygon in enumerate(polygones["polygones"]):
                    polygon_sc = [[x*x_size//w_web, y*y_size//h_web] for x, y in polygon]
                    ramki_scaled.append(Ramka(polygon_sc, polygones["ramkiDirections"][k], y_size))
            # print(f'ramki scaled {ramki_scaled}')
            # print(f'ramki directions {ramki_directions} type-{type(ramki_directions)}')
            ramki_status = [0 for i in range(len(ramki_scaled))]
            # when lenght ramki_status changed do below, can't remove ramki_status_ object, 
            # because need to save it's reference fo repeated timer
            while len(ramki_status_)>len(ramki_status):
                ramki_status_.pop()
            while len(ramki_status_)<len(ramki_status):
                ramki_status_.append(0)
        
        # get settings from flask process
        if not q_settings.empty():
            y_size, x_size = wframe.shape[:2]
            settings = json.loads(q_settings.get())
            addrString[0] = 'http://' + settings["hub"] + '/detect'
            calibrPoints = json.loads(settings["calibration"])
            calibrPoints_sc = [[x*x_size//w_web, y*y_size//h_web] for x, y in calibrPoints]
            print('calibrPoints scaled', calibrPoints_sc)

        ### Changing zone colors ###
        # If any track point is inside the detecting zone - change it's state to On.
        # use shapely lib to calculate intersections of polygones (good lib)
        for i, ramka in enumerate(ramki_scaled):
            ramka.color = 0 # for each ramka before iterate for frames, reset it 
            ramki_status[i]=0
            # if some track below cross, it,  it woll be on for whole frame. 
            for track in tracks:
                if not track.complete:
                    shapely_box = box(track.boxes[-1][0], track.boxes[-1][1], track.boxes[-1][2], track.boxes[-1][3])
                    # interscec_ = ramka.shapely_path.intersection(shapely_box).area/ramka.area*100
                    interscec_ = ramka.shapely_path.intersection(shapely_box).area/ramka.area*100
                    if (interscec_ > iou_tresh_perc):
                        # here need to check if track points are in detecting zone, and only then swith it on
                        # iterate for points in track, check if point inside the zone
                        for j in range(len(track.points)):
                            point = track.points[len(track.points)-1-j]
                            if Point(point).within(ramka.shapely_path):
                                ramka.color = 1
                                ramki_status[i] = 1

        # then draw polygones with arrows
        for i, ramka in enumerate(ramki_scaled):
            color_ = green if ramka.color == 1 else blue
            cv2.putText(frame_show, str(i+1), (ramka.center[0]-5, ramka.center[1]+5), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, color_, 2)
            # draw polygones 
            cv2.polylines(frame_show, np.array([ramka.path], np.int32), 1, color_, 3)
            # draw arrows
            # for j, arrow in enumerate(poly):
            for j in range(4):
                if ramka.directions[j] ==1:
                    cv2.polylines(frame_show, np.array([ramka.arrows_path[j]]), 1, color_, 2)
        
        ### do the transform calibration polygone 


        # draw calibration polygone 
        cv2.polylines(frame_show, np.array([calibrPoints_sc]), 1, green, 1)



        # Time Per Frame to show on the web
        tpf = int((time.time()-tss)*1000) 
        
        if frm_number < 5:
            tpf_midle = tpf
        elif frm_number > 200:
            tpf_midle = (tpf_midle + ((tpf)-tpf_midle)/200)
        else:
            tpf_midle = (tpf_midle + ((tpf)-tpf_midle)/frm_number)

        if visual:
            # img = cv2.resize(img, (800, 600))
            frame_str = f'{int(tpf_midle)} ms/f tr-{len(tracks)} ' + \
                        f'{width}x{height} fps{fps} {network}'
            cv2.putText(frame_show, frame_str, (15, 15),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            cv2.namedWindow("Frame", cv2.WINDOW_NORMAL)
            # cv2.imshow("Frame", wframe)
            cv2.imshow("Frame", frame_show)

            put_queue(q_pict, frame_show)  # put the picture for web in the picture Queue
            key = cv2.waitKey(key_time) & 0xFF
            # if the `ESC` key was pressed, break from the loop
            if key == 27:
                break
            if key == ord("p"):
                key_time = 0
            if key == ord("o"):
                key_time = 1
            if key == ord("d"):
                tracks = []  # kill all tracks pressing d
        if frm_number % 10 == 0:
            # print(f'                                                        {int(tpf_midle)} msec/frm   tracks- {len(tracks)}')
            pass
        

        # if memmon:
        #     print("[ Top 10 ]")
        #     for stat in top_stats[:10]:
        #         print(stat)


    cap.release()
    cv2.destroyAllWindows()


# if __name__ == "__main__":
    # proc()
