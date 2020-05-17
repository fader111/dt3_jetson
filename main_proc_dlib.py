""" gets detections from jetson cnn-based detectors.
    Build tracks based on dlib tracker which updated by detector using iou algorythm.

    Kalman filtering implemented???
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
import json
from RepeatedTimer_ import RepeatedTimer
from common_tracker import *
from iou import bb_intersection_over_union
# from track_iou_kalman_cv2 import Track
from track_dlib import Track
from dlib import correlation_tracker
from shapely.geometry import Polygon, box
# import Jetson.GPIO as GPIO

# cascade_path = 'vehicles_cascadeLBP_w25_h25_p2572_n58652_neg_roof.xml'
# cascade_path = 'vehicle_cascadeLBP_w20_h20_p2139.xml'

q_pict = Queue(maxsize=5)  # queue for web picts
q_status = Queue(maxsize=5)  # queue for web status
q_ramki = Queue(maxsize=5)  # очередь где лежат рамки

# jetson inference networks list
network_lst = ["ssd-mobilenet-v2",  # 0 the best one???
               "ssd-inception-v2",  # 1
               "pednet",           # 2
               "alexnet",          # 3
               "facenet",          # 4
               "googlenet"         # 5 also good
               ]

network = network_lst[1]

threshold = 0.2  # for jetson inference object detection
iou_tresh_perc = 30  # tresh for cnn detection bbox and car detecting zone intersection in percents
width = 1920  # 640
height = 1080  # 480
# camera_src = '/dev/video1'  # for USB
# camera_src = '0'  # for sci Gstreamer 
# camera = jetson.utils.gstCamera(width, height, camera_src)
overlay = "box,labels,conf"
print("[INFO] loading model...")
net = jetson.inference.detectNet(network, sys.argv, threshold)

cur_resolution = (width, height)
scale_factor = cur_resolution[0]/400
resolution_str = str(cur_resolution[0]) + 'x' + str(cur_resolution[1])

visual = True  # visual mode

video_src = "/home/a/Videos/U524806_3.avi"
# video_src = "/home/a/dt3_jetson/jam_video_dinamo.avi" gets some distorted video IDKW
# video_src = "http://95.215.176.83:10090/video30.mjpg?resolution=&fps="
# video_src = "http://62.117.66.226:5118/axis-cgi/mjpg/video.cgi?camera=1&dummy=0.45198500%201389718502" # sokolniki shlagbaum
# video_src = "https://rtsp.me/embed/dKfKFNTz/" # doesnt work
# video_src = "G:/fotovideo/video_src/usb2.avi"

# True - camera, False - video file /80ms per frame on camera, 149 on video
USE_CAMERA = 1 #False
USE_GAMMA = False  # True - for night video

bboxes = []  # bbox's of each frame
max_track_lifetime = 3  # if it older than num secs it removes
if USE_CAMERA:
    detect_phase_period = 10  # detection phase period in frames
else:
    detect_phase_period = 3  # detection phase period in frames

iou_tresh = 0.2  # treshold for tracker append criteria 0.4

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
    new_tr_number = 0  # for tracks numeration
    frm_number = 0
    polygones = {} # json c рамками и направлениями
    ramki_scaled = [] # ramki scaled
    ramki_colors = [] # ramki colors
    ramki_directions = [] # ramki directions
    bboxes = []
    tracks = []  # list for Track class instances
    arrows = [] # arrows of polygones path
    stop_ = False  # aux for detection break

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
        img = cv2.resize(img, (640, 480))
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

        frame = img_c
        # needs for cuda to add new one channel
        img_c = cv2.cvtColor(img_c, cv2.COLOR_BGR2RGBA)  # ogiginal variant

        # Detection phase - each 2nd (5th?) frame will detect using Jetson inference
        if frm_number % detect_phase_period == 0:  # 5 - default
            # tss = time.time() # 56 w/o/ stdout on video
            frame_cuda = jetson.utils.cudaFromNumpy(img_c)
            # tss = time.time() # 54 w/o/ stdout on video

            # frame, width, height = camera.CaptureRGBA(zeroCopy = True)

            detections = net.Detect(frame_cuda, width, height, overlay)
            # for detection in detections:
            #    if detection.ClassID == 3: # car in coco
            #    print ('car detection confidence -', detection.Confidence)

            jetson.utils.cudaDeviceSynchronize()
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
                
                cv2.putText(frame, class_string, (x1+1, y1-4), cv2.FONT_HERSHEY_SIMPLEX, 0.6, green, 1)
                cv2.rectangle(frame, (x1, y1), (x2, y2), green, 1)
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
                            # track.boxes = []
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
                    
                    cv2.putText(frame, class_string, (x1+1, y1-4), cv2.FONT_HERSHEY_SIMPLEX, 0.6, purple, 1)
                    cv2.rectangle(frame, (x1, y1), (x2, y2), purple, 1)

        wframe = frame  # .copy()
        # if web_is_on(): # если web работает копируем исходный фрейм для него
        # print('web', q_pict.qsize())

        # remove frozen tracks and tracks with length less then 3 points.
        for track in tracks[:]:
            # if max track life time is over, or track isn't appended for more than 1 sec, del it
            if (time.time() - track.ts > max_track_lifetime) | ((time.time() - track.ts > 3) & (len(track.boxes) < 3)):
                if key_time != 0:  # when video capturing stops tracks don't delete
                    tracks.remove(track)

        # draw tracks
        for track in tracks:
            track.draw_tracks(frame)
        # draw frame resolution
        if net.GetNetworkFPS() != math.inf:
            fps = str(round(net.GetNetworkFPS()))
        else:
            fps = 'inf...'
        # resolution_str_ = str(width) + 'x' + str(height)
        # tot_elapsed_time = str(round((time.time()-tss), 2))
        # res_string = resolution_str_+'  fps-' + fps + \
            # ' elps ' + tot_elapsed_time + ' net-' + network
        # cv2.putText(wframe, res_string, (15, 30),
                    # cv2.FONT_HERSHEY_SIMPLEX, 0.5, 255, 1)
        # draw current time
        # os.popen("date").read()[:-1] # eats fckng 120 ms in inference!!!! 120 Karl!!!!
        # cv2.putText(wframe, time_str, (15, 15),
        # cv2.FONT_HERSHEY_DUPLEX, 0.5, 255, 1)
        # put_queue(q_pict, wframe)  # put the picture for web in the picture Queue
        # put_queue(q_status, GREEN_TAG)
        
        # calculate time per frame in msec

        # draw detecting zones q_ramki - Queue, if the are new detecting areas, they are in 
        # this queue
        if not q_ramki.empty():
            # here it comes as a string, so convert
            polygones = json.loads(q_ramki.get()) # not zoomed right 
            # calculate polygones coordinates in scale
            ramki_scaled = []
            ramki_directions = []
            ramki_colors = []
            arrows = []
            y_size, x_size = wframe.shape[:2]
            if ("polygones") in polygones:
                x_factor, y_factor = polygones["frame"]
                for polygon in polygones["polygones"]:
                    polygon_sc = [[x*x_size//x_factor, y*y_size//y_factor] for x, y in polygon]
                    ramki_scaled.append(polygon_sc)
                    ramki_colors.append(0)
                    # fill up the arrows list
                    arrows.append(arrows_path(polygon_sc, y_size))
                # print(f'ramki scaled {ramki_scaled}')
                ramki_directions = polygones["ramkiDirections"]
                # print(f'ramki directions {ramki_directions} type-{type(ramki_directions)}')
        

        # if any track point is inside the detecting zone - change it's state to On.
        for i , ramka in enumerate(ramki_scaled):
            for track in tracks: 

                # ext = [(0, 0), (0, 2), (2, 2), (2, 0), (0, 0)]
                # int = [(1, 0), (0.5, 0.5), (1, 1), (1.5, 0.5), (1, 0)][::-1]
                # polygon = Polygon(ext, [int])
                # polygon = Polygon(ext)

                # d = a.difference(polygon)

                shapely_ramka = Polygon(ramka)
                shapely_box = box(track.boxes[-1][0], track.boxes[-1][1], track.boxes[-1][2], track.boxes[-1][3])
                interscec_ = shapely_ramka.intersection(shapely_box).area/shapely_ramka.area*100
                if (interscec_ > iou_tresh_perc):
                    ramki_colors[i] = 1
                else:
                    ramki_colors[i] = 0

        
        # then draw polygones
        for i, ramka in enumerate(ramki_scaled):
            color_ = green if ramki_colors[i] == 1 else blue
            cv2.polylines(wframe, np.array([ramka], np.int32), 1, color_, 3)
        

        # draw arrows for polygones
        for i, poly in enumerate(arrows): 
            # arrows - [[[[x,y],[x,y],[x,y]], [...], [...], [...]], [[...], [...], [...], [...]]]
            for j, arrow in enumerate(poly):
                if ramki_directions[i][j] == 1:
                    # cv2.polylines(frame, np.array(item), 1, red, 0)
                    # print('arrow',[arrow])
                    cv2.polylines(frame, np.array([arrow]), 1, blue, 2)



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
            cv2.putText(wframe, frame_str, (15, 15),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            # cv2.namedWindow("Frame", cv2.WINDOW_NORMAL)
            # cv2.imshow("Frame", wframe)

            put_queue(q_pict, wframe)  # put the picture for web in the picture Queue
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
            print(f'                                                        {int(tpf_midle)} msec/frm   tracks- {len(tracks)}')
            
        # if memmon:
        #     print("[ Top 10 ]")
        #     for stat in top_stats[:10]:
        #         print(stat)


    cap.release()
    cv2.destroyAllWindows()


# if __name__ == "__main__":
    # proc()
