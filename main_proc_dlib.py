""" gets detections from jetson cnn-based detectors.
    Build tracks based on dlib tracker which updated by detector using iou algorythm.
    Kalman filtering implemented???
"""
import enum
import pathlib
import telnetlib

from threading import Timer, Thread, Lock
from multiprocessing.dummy import Process, Queue
# from multiprocessing import Process, Queue
import time
import sys
import re
import subprocess
import typing
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
# from dlib import correlation_tracker
from shapely.geometry import Point, Polygon, box
from detect_zones import Ramka
from transform import four_point_transform, order_points2, windowToFieldCoordinates
from common_tracker import setInterval
from pprint import pprint
from copy import deepcopy
import requests
requests.packages.urllib3.disable_warnings()

import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst, GLib
Gst.init()


if 'linux' in sys.platform:
    import jetson.inference
    import jetson.utils    
    # import Jetson.GPIO as GPIO

# cascade_path = 'vehicles_cascadeLBP_w25_h25_p2572_n58652_neg_roof.xml'
# cascade_path = 'vehicle_cascadeLBP_w20_h20_p2139.xml'

q_pict = Queue(maxsize=5)       # queue for web picts
# queue for ip and other settings to sent from web client to python
q_settings = Queue(maxsize=5)
q_ramki = Queue(maxsize=5)      # polygones paths
q_status60 = Queue(maxsize=5)     # current status60 of process for web.
q_status15 = Queue(maxsize=5)     # current status15 of process for web.

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
# tresh for cnn detection bbox and car detecting zone intersection in percents
iou_tresh_perc = 10

max_bbox_sqare = 1000   # when detection bbox too small, do not process it.

width = 1280            # 640 width settings for camera capturing
height = 720            # 480 height for the same
proc_width = 640        # x size of window for processing with CNN
proc_height = 480       # y size
# camera_src = '/dev/video1'  # for USB camera
# camera_src = '0'  # for sci Gstreamer
# camera = jetson.utils.gstCamera(width, height, camera_src) # also possible capturing way
overlay = "box,labels,conf"
print("[INFO] loading model...")
# # 

cur_resolution = (width, height)
scale_factor = cur_resolution[0]/400
resolution_str = str(cur_resolution[0]) + 'x' + str(cur_resolution[1])

# calculates traffic parameters in 15 minutes period per each detection zone
# uses sliding window for calc
status15 =  {
    "avg_speed": [],
    "vehicle_types_intensity": [{"13": 0, "2": 0, "1": 0}],
    "intensity": [],
    "avg_time_in_zone": []
}
# calculates traffic parameters in 60 minutes period per each detection zone
status60 = {
    "avg_speed": [],
    "vehicle_types_intensity": [{"13": 0, "2": 0, "1": 0}],
    "intensity": [],
    "avg_time_in_zone": []
}

visual = True  # visual mode
winMode = False  # debug mode for windows - means that we are in windows now

if 'win' in sys.platform:
    proj_path = 'C:/Users/ataranov/Projects/dt3_jetson/'  # путь до папки проекта
    winMode = True
else:
    proj_path = '/home/a/dt3_jetson/'  # путь до папки проекта
    net = jetson.inference.detectNet(network, sys.argv, threshold)

# video_src = "/home/a/Videos/U524806_3.avi"
if 'win' in sys.platform:
    video_src = "G:/U524802_1_695_0_new.avi"
else:
    video_src = "/home/a/Videos/U524802_1_695_0_new.avi"  # 2650 x 2048
    video_src = "/home/a/Videos/U524806_3.avi"  # 2650 x 2048

video_src = '/home/a/filename.mp4'
# video_src = '/home/a/Videos/lenin35_640.avi' # h 640
# video_src = "/home/a/dt3_jetson/jam_video_dinamo.avi" gets some distorted video IDKW
# video_src = "http://95.215.176.83:10090/video30.mjpg?resolution=&fps="
# video_src = "http://62.117.66.226:5118/axis-cgi/mjpg/video.cgi?camera=1&dummy=0.45198500%201389718502" # sokolniki shlagbaum
# video_src = "https://rtsp.me/embed/dKfKFNTz/" # doesnt work
# video_src = "G:/fotovideo/video_src/usb2.avi"

# True - camera, False - video file /80ms per frame on camera, 149 on video
USE_CAMERA = True
USE_GAMMA = False  # Gamma correction - True - for night video

# bboxes = []  # bbox's of each frame # candidate for removing
max_track_lifetime = 2  # if it older than num secs it removes
if USE_CAMERA:
    detect_phase_period = 10  # detection phase period in frames
else:
    detect_phase_period = 5  # detection phase period in frames

# treshold for tracker append criteria 0.4 less- more sensitive, more mistakes
iou_tresh = 0.2

class VideoStreamSources(enum.Enum):
    LOCAL_CAMERA = 'local'
    RTSP_STREAM = 'rtsp'

# not used,  just sample
camera_str2 = f"nvarguscamerasrc ! video/x-raw(memory:NVMM), width=(int){str(width)}, \
		height=(int){str(height)},format=(string)NV12, framerate=(fraction)60/1 ! nvvidconv flip-method=2 ! \
        video/x-raw, format=(string)BGRx ! \
        videoconvert ! video/x-raw, format=(string)BGR ! appsink"

camera_str_h256 = f"nvarguscamerasrc ! 'video/x-raw(memory:NVMM), width={str(width)}, \
                    height={str(height)},format=NV12, framerate=60/1' ! nvvidconv flip-method=2 ! \
                    omxh265enc ! qtmux ! appsink wait-on-eos=false max-buffers=1 drop=True"

ufanet_token = '007e291368194ef1a59519d128ea5861'
#http://136.169.226.9/001-999-037/tracks-v1/mono.m3u8?token=5ebf46533fe74d26938db36e87038bf8
camera_str_ufanet = f"souphttpsrc location=http://136.169.226.9/001-999-037/tracks-v1/mono.m3u8?token={ufanet_token} ! " \
                f"hlsdemux ! omxh264dec ! videoconvert " \
                f"appsink wait-on-eos=false max-buffers=1 drop=True "


def construct_input_pipline(stream_source_type):
    global camera_str
    if stream_source_type is VideoStreamSources.LOCAL_CAMERA:
        # only for sci camera
        # framerate=(fraction)60/1 - optimum rate
        camera_str = f"nvarguscamerasrc ! video/x-raw(memory:NVMM), width=(int){str(width)}, \
                height=(int){str(height)},format=(string)NV12, framerate=(fraction)60/1 ! nvvidconv ! \
                video/x-raw, width=(int)1280, height=(int)720, format=(string)BGRx ! \
                videoconvert ! video/x-raw, format=(string)BGR ! appsink wait-on-eos=false max-buffers=1 drop=True"
    elif stream_source_type is VideoStreamSources.RTSP_STREAM:
        rtsp_config_filename = pathlib.Path(proj_path) / pathlib.Path('rtsp.config')
        if rtsp_config_filename.exists():
            with rtsp_config_filename.open('r') as rtsp_config_file:
                rtsp_location = rtsp_config_file.read().strip()
        else:
            rtsp_location = 'rtsp://172.16.20.97/user=admin_password=tlJwpbo6_channel=1_stream=0.sdp?real_stream'
        camera_str = f"rtspsrc location={rtsp_location} ! queue ! rtph264depay ! h264parse ! queue ! omxh264dec ! " \
                     f"videoconvert ! appsink wait-on-eos=false max-buffers=1 drop=True"
    else:
        raise NotImplementedError(f"Stream source type {stream_source_type} unknown!")



poligones_filepath = proj_path + 'polygones.dat'
settings_filepath = proj_path + 'settings.dat'


def read_setts_from_syst(filePath):
    ''' read settings ip and others from system and config file
        filePath = full path to settings.dat
    '''
    # print ('filePath' + filePath)
    settings_ = {"ip": get_ip() + '/' + get_bit_number_from_mask(get_mask()),
                 "gateway": get_gateway(),
                 "hub": get_hub(filePath),
                 "calibration": get_settings_from_file(filePath)["calibration"],
                 "calib_zone_length": get_settings_from_file(filePath)["calib_zone_length"],
                 "calib_zone_width": get_settings_from_file(filePath)["calib_zone_width"],
                 "source_stream_type": get_settings_from_file(filePath)["source_stream_type"]
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
    #if len(det_status)>4:
    #    det_status = det_status[:3]
    # print('                              hub ', addrString, det_status)
    
#    requests.post('https://172.16.20.240/detect',json={"cars_detect":[True, False, False, False]}, verify=False).text
    try:
        # pass
        # requests.get(addrString[0], timeout=(0.1, 0.1))
        ans = requests.post(addrString[0], timeout=(1.0, 1.0), json={"cars_detect": det_status}, verify=False)
        # requests.post(addrString[0], json={"cars_detect": det_status}, verify=False)
        # return ans.text
        # print(' !!!!!!!!!!!!!!!!!!!!                    ', ans.text, ans.raw.read(10) , addrString)
    except Exception as err:
        pass
        print('expt from  sendColorStatusToHub', err)
        # return 'Disconnected...'


def put_queue(queue, data):
    # print('put', q_pict.qsize())
    if not queue.qsize() > 3:  # помещать в очередь для web только если в ней не больше 3-х кадров ( статусов )
        # нем смысла совать больше если web не работает и никто не смотрит, или если статус никто не выбирает,
        # ато выжрет всю память однако
        queue.put(data)


def put_status(queue, status):
    ''' Updates detectors status in flask process, when changes occurs 
        put changes to queue '''
    # сюда суем статус детектирования, если он изменился в выч процессе. 
    # в web процессе вычитываем очередь при поступлении запроса
    # print('status', status)
    while not queue.empty():
        queue.get()
    if not queue.qsize() >= queue.maxsize:
        queue.put(status)


def init_status60_15_struct(n_ramki):
    ''' initiates status60, status15, massives according to the number of 
        detecting zones
        vehicle types: 1- car; 2 - 2axis truck; 3-3axix track; 13 - bus.
    '''
    status60["avg_speed"] = [0 for j in range(n_ramki)]
    status60["vehicle_types_intensity"] = [{"1": 0, "2": 0, "13": 0} for j in range(n_ramki)]
    status60["intensity"] = [0 for j in range(n_ramki)]
    status60["avg_time_in_zone"] = [0 for j in range(n_ramki)]

    status15["avg_speed"] = [0 for j in range(n_ramki)]
    status15["vehicle_types_intensity"] = [{"1": 0, "2": 0, "13": 0} for j in range(n_ramki)]
    status15["intensity"] = [0 for j in range(n_ramki)]
    status15["avg_time_in_zone"] = [0 for j in range(n_ramki)]
    # print()

def bbox_square(bbox):
    return abs((bbox[0]-bbox[2])*(bbox[1]-bbox[3]))


dir_of_hls_video = pathlib.Path('/tmp/hls/video')

def reboot_local_rtsp_camera():
    DEFAULT_IP = '172.16.20.97'
    USERNAME = 'root'
    PASSWORD = 'xmhdipc'

    tn = telnetlib.Telnet(DEFAULT_IP)
    tn.read_until(b"login: ")
    tn.write(USERNAME.encode('ascii') + b"\n")
    tn.read_until(b"Password: ")
    tn.write(PASSWORD.encode('ascii') + b"\n")
    tn.write(b"reboot\n")
    tn.read_all()

def local_rtsp_camera_reboot_thread():
    reboot_timeout = 24*60*60       # secs, 24 hours
    while True:
        time.sleep(reboot_timeout)
        reboot_local_rtsp_camera()

def run_rtsp_media_server():
    """
    alternative_path = '/home/a/sources/RtspRestreamServer/build/RestreamServerApp/RestreamServerApp'
    :return:
    """
    path_of_executable = pathlib.Path('/home/a/sources/rtsp-simple-server/rtsp-simple-server /home/a/sources/rtsp-simple-server/rtsp-simple-server.yml')
    subprocess.Popen(str(path_of_executable), shell=True)


def start_hls_streaming():
    frames_per_sec = 10
    video_filename_template = 'file%d.ts'
    videofiles_num = 5
    playlist_filename = 'playlist.m3u8'
    videofiles_duration = 5
    appsrc_plugin_name = 'appsrc0'

    run_rtsp_media_server()

    if dir_of_hls_video.exists():
        clear_dir(dir_of_hls_video)
    else:
        dir_of_hls_video.mkdir(parents=True)

    pipeline = construct_pipeline(frames_per_sec = frames_per_sec,
                                  dir_of_video = dir_of_hls_video,
                                  video_filename_template = video_filename_template,
                                  videofiles_num = videofiles_num,
                                  playlist_filename = playlist_filename,
                                  videofiles_duration = videofiles_duration,
                                  appsrc_plugin_name = appsrc_plugin_name
                                 )

    loop = GLib.MainLoop.new(None, False)
    loop_thread = Thread(target=loop.run)

    loop_thread.start()
    try:
        pipeline.set_state(Gst.State.PLAYING)
        appsrc = pipeline.get_by_name(appsrc_plugin_name)

        pts = 0
        duration = 10**9 / frames_per_sec
        while True:
            array = q_pict.get()
            gst_buffer = ndarray_to_gst_buffer(array)
            pts += duration                                 # Increase pts by duration
            gst_buffer.pts = pts
            gst_buffer.duration = duration
            appsrc.emit("push-buffer", gst_buffer)

        appsrc.emit("end-of-stream")
    except Exception as e:
        print("error:", e)
    finally:
        pipeline.set_state(Gst.State.NULL)
    loop.quit()
    loop_thread.join(timeout=5)


def ndarray_to_gst_buffer(array: np.ndarray) -> Gst.Buffer:
    """Converts numpy array to Gst.Buffer"""
    return Gst.Buffer.new_wrapped(array.tobytes())


def construct_pipeline(frames_per_sec, dir_of_video, video_filename_template, videofiles_num, playlist_filename,
                       videofiles_duration, appsrc_plugin_name):
    source_video_format = 'BGR'
    video_width, video_height = 640, 480

    pipeline = Gst.Pipeline.new(None)

    appsrc = Gst.ElementFactory.make('appsrc', appsrc_plugin_name)
    appsrc.set_property('is-live', True)
    appsrc.set_property('caps',
                        Gst.Caps.from_string("video/x-raw,format=%s,width=%d,height=%d,framerate=%d/1" %
                                             (source_video_format, video_width, video_height, frames_per_sec))
                        )
    appsrc.set_property('format', Gst.Format.TIME)
    appsrc.set_property("block", True)
    pipeline.add(appsrc)
    videoconvert = Gst.ElementFactory.make('videoconvert', None)
    pipeline.add(videoconvert)
    omxh264enc = Gst.ElementFactory.make('omxh264enc', None)
    omxh264enc.set_property('profile', 'high')
    pipeline.add(omxh264enc)
    tee = Gst.ElementFactory.make('tee', None)
    pad_template = tee.get_pad_template('src_%u')
    tee_hls_pad = tee.request_pad(pad_template, None, None)
    tee_rtsp_pad = tee.request_pad(pad_template, None, None)
    pipeline.add(tee)
    queue_hls = Gst.ElementFactory.make('queue', 'queue_hls')
    queue_hls_pad = queue_hls.get_static_pad("sink")
    pipeline.add(queue_hls)
    h264parse = Gst.ElementFactory.make('h264parse', None)
    pipeline.add(h264parse)
    mpegtsmux = Gst.ElementFactory.make('mpegtsmux', None)
    pipeline.add(mpegtsmux)
    hlssink = Gst.ElementFactory.make('hlssink', None)
    hlssink.set_property('location', str(dir_of_video / video_filename_template))
    hlssink.set_property('max-files', videofiles_num)
    hlssink.set_property('playlist-location', str(dir_of_video / playlist_filename))
    hlssink.set_property('target-duration', videofiles_duration)
    pipeline.add(hlssink)
    queue_rtsp = Gst.ElementFactory.make('queue', 'queue_rtsp')
    queue_rtsp_pad = queue_rtsp.get_static_pad("sink")
    pipeline.add(queue_rtsp)
    rtspclientsink = Gst.ElementFactory.make('rtspclientsink', None)
    rtspclientsink.set_property('location', 'rtsp://localhost:8001/test')
    rtspclientsink.set_property('protocols', 'tcp')
    pipeline.add(rtspclientsink)

    appsrc.link(videoconvert)
    videoconvert.link(omxh264enc)
    omxh264enc.link(tee)
    tee_hls_pad.link(queue_hls_pad)
    queue_hls.link(h264parse)
    h264parse.link(mpegtsmux)
    mpegtsmux.link(hlssink)
    tee_rtsp_pad.link(queue_rtsp_pad)
    queue_rtsp.link(rtspclientsink)

    return pipeline


def clear_dir(dir_: pathlib.Path):
    for subpath in dir_.iterdir():
        if subpath.is_dir():
            clear_dir(subpath)
        else:
            subpath.unlink()


def proc():
    # timer to restart detector when main thread crashes
    # wdt_tmr = Timer(30, wdt_func) # отключено на время отладки
    # wdt_tmr.start() # отключено на время отладки

    # if memmon: # mamory allocation monitoring
    # import tracemalloc
    # tracemalloc.start()

    # prev_bboxes = []  # bboxes to draw from previous frame
    key_time = 1
    new_tr_number = 0   # for tracks numeration
    frm_number = 0
    ramki_scaled = []   # ramki scaled mass for Instances of Ramka
    # mass of 0 and 1 for send to hub as json, len = len(ramki_scaled), 0 if ramka off, 1 - if on
    ramki_status = []
    # need to have only one reference, thats why below fild created.
    # copy of ramki status to sent to repeated timer for sending to hub.
    ramki_status_ = []

    bboxes = []
    tracks = []         # list for Track class instances
    stop_ = False       # aux for detection break
    polygon_sc = []     # scaled polygon points
    calibrPoints = []   # list of points of calibration Polygon on road
    calibrPoints_sc = []  # scaled list of points of calibration Polygon
    w_web = 800         # web picture width
    h_web = 600         # web picture hight

    ### main preparation section ###

    # read detection zone areas (polygones) from polygones
    # read settings from file
    polygones = read_polygones_from_file(
        poligones_filepath)  # json c рамками и направлениями
    ramki_status = [0 for i in range(len(polygones["polygones"]))]
    ramki_status_ = [0 for i in range(len(polygones["polygones"]))]
    # Init ip and other settings from system
    settings = read_setts_from_syst(proj_path + "settings.dat")

    stream_source_type = VideoStreamSources(settings['source_stream_type'])
    construct_input_pipline(stream_source_type)

    if USE_CAMERA:
        # cap = cv2.VideoCapture(camera_src) # for GSTreamer handling camera
        cap = cv2.VideoCapture(camera_str, cv2.CAP_GSTREAMER)  # for SCI camera
    else:
        cap = cv2.VideoCapture(video_src)

    # calibration polygon point Init
    if ("calibration") in settings:
        calibrPoints = json.loads(settings["calibration"])
        # scaled polygones
        calibrPoints_sc = [[x*proc_width//w_web, y*proc_height//h_web]
                           for x, y in calibrPoints]

    # make transform matrix, hight and width of Top view of callibration polygon -
    # means make the rectangle from the polygone
    black_img = np.zeros((h_web, w_web, 3), np.uint8)
    np_calibrPoints_sc = np.array(calibrPoints_sc, dtype="float32")
    M, warped_width_px, warped_height_px = four_point_transform(
        black_img, np_calibrPoints_sc, picMode=False)
    warp_dimentions_px = warped_width_px, warped_height_px

    # get calibration zone settings - width and length in meters from settings file
    calib_area_length_m = float(settings['calib_zone_length'])
    calib_area_width_m = float(settings['calib_zone_width'])
    calib_area_dimentions_m = calib_area_width_m, calib_area_length_m

    # create all the detection zones objects
    if ("polygones") in polygones:
        w_web, h_web = polygones["frame"]
        for k, polygon in enumerate(polygones["polygones"]):
            polygon_sc = [[x*proc_width//w_web, y*proc_height//h_web]
                          for x, y in polygon]
            # scaled means fitted to web view
            ramki_scaled.append(
                Ramka(polygon_sc,                         # scaled polygon vertex
                      warp_dimentions_px,                 # width, height Top view of calibration zone
                      calib_area_dimentions_m,            # width, height of calibration zone in meter
                      M,                                  # transition matrix
                      polygones["ramkiDirections"][k],    # directions
                      proc_height                         # CNN process window hight
                      ))
    # ramki_scaled
    # calculation distanses of up and down side of detecting areas

    # status of process must send to hub - device wich convert detector packets to the
    # physical signals. Do it with repeated timer. Update each 400ms

    addrString = ['https://' + settings["hub"] + '/detect']

    rtUpdStatusForHub = RepeatedTimer(
        0.4, send_det_status_to_hub, addrString, ramki_status_)
    rtUpdStatusForHub.start()

    init_status60_15_struct(len(ramki_scaled)) # initiates status60 and status15 massives
    # with proper number of detecting zones

    @setInterval(60) # each {arg} seconds runs  ramka.sliding_wind for update zone status 
    def function():
        ''' calculates detector status60 and status15 '''
        for i, ramka in enumerate(ramki_scaled):
            ramka.sliding_wind()
            status60['avg_speed'][i] =                  ramka.status['avg_speed_60']
            status60['intensity'][i] =                  ramka.status['avg_intens_60']
            status60['avg_time_in_zone'][i] =           ramka.status['avg_time_in_zone_60']
            status60["vehicle_types_intensity"][i] =    ramka.status['avg_intens_60_tp']

            status15['avg_speed'][i] =                  ramka.status['avg_speed_15']
            status15['intensity'][i] =                  ramka.status['avg_intens_15']
            status15['avg_time_in_zone'][i] =           ramka.status['avg_time_in_zone_15']
            status15["vehicle_types_intensity"][i] =    ramka.status['avg_intens_15_tp']

        # print('status60')
        # pprint(status60)

        # print('status15')
        # pprint(status15)

        ### Transmit status60 and status15 to the q_status queue ###
        put_status(q_status60, status60)
        put_status(q_status15, status15)

    # start new thread for average speed calculating
    stop = function() # stop is threading.Event object

    hls_streaming_thread = Thread(target=start_hls_streaming)
    hls_streaming_thread.start()

    reboot_camera_thread = Thread(target=local_rtsp_camera_reboot_thread)
    reboot_camera_thread.start()

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
            # print('wait..')
        img = cv2.resize(img, (proc_width, proc_height))
        # img = cv2.resize(img, (800, 604))
        height, width = img.shape[:2]
        # print(f'orig_img.shape = {orig_img.shape}')

        if USE_GAMMA:
            img = gamma(img, gamma=0.8)

        # give roi. Roi cuted upper part of frame
        up_bord = int(0.2*height)
        img_c = img  # [up_bord:height, 0:width]

        # img_c = img_c[0:height, 0:int(width/5)]

        height, width = img_c.shape[:2]
        # cv2.line(img, (0, up_bord), (width, up_bord), 255, 1)

        # frame_show only for display on interface with texts, rectangles and labels
        frame_show = frame = img_c
        # separate frame_show to another object
        frame_show = np.copy(frame_show)

        # needs for cuda to add new one channel
        img_c = cv2.cvtColor(img_c, cv2.COLOR_BGR2RGBA)  # ogiginal variant

        
        ### DETECTION PHASE ###
        
        #  each 2nd (5th?) frame will detect using Jetson inference
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
                
                # if bbox_square(bbox) < max_bbox_sqare:
                    # print(f'bbox_square {bbox_square(bbox)}')

                if bbox_square(bbox) < max_bbox_sqare:
                    continue
                # print(f'bbox_square {bbox_square(bbox)}')

                if detection.ClassID in CLASSES_EXTENDED:
                    # conf = round(detection.Confidence,2)
                    class_string = f'{CLASSES_EXTENDED[detection.ClassID]} - {detection.Confidence:.2f}'
                else:
                    class_string = ('wtf?')
                    continue  # go

                cv2.putText(frame_show, class_string, (x1+1, y1-4),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, green, 1)
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
                            track.renew(
                                frame, bbox, detection.ClassID, detection.Confidence)
                        else:
                            # mark this track as completed, don't update it anymore
                            track.complete = True
                            # track.boxes = [] # no, exception in iou_val above
                        break  # do not need do more with this bbox, go out
                if stop_:
                    break
                # or, if bbox didn't assingned to any track, create a new track
                tracks.append(Track(frame, bbox, new_tr_number,
                                    detection.ClassID, detection.Confidence, warp_dimentions_px, 
                                    calib_area_dimentions_m, M,))
                new_tr_number += 1
                if new_tr_number > 99:
                    new_tr_number = 0


        ### TRACKING PHASE ###

        # update tracks
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

                    cv2.putText(frame_show, class_string, (x1+1, y1-4),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, purple, 1)
                    cv2.rectangle(frame_show, (x1, y1), (x2, y2), purple, 1)

        wframe = frame  # .copy()
        # if web_is_on(): # если web работает копируем исходный фрейм для него
        # print('web', q_pict.qsize())

        
        ### Remove old and bad tracks ###
        
        # remove frozen tracks and tracks with length less then 3 points and didn't updated 
        # for more then 3 secs or if detector cant find the car for more then 10 secs.
        for track in tracks[:]:
            now = time.time()
            # if max track life time is over, or track isn't appended for more than 1 sec, del it
            if (now - track.ts > max_track_lifetime) | \
                ((now - track.ts > 3) & (len(track.boxes) < 3)) | \
                 (now - track.renew_ts > 10) | \
                 (abs(track.aver_speed) > 190):
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


        ### UPDATE DETECTION ZONES STATUS AND SETTINGS SECTION ###

        # get polygones from flask process
        # when polygones change on web, it always translate to calc process
        # using Queue
        if not q_ramki.empty():
            
            temp_polygones = deepcopy(polygones) # need to compare with new polygones, 
            # if they're the same, no need to stop statistic collection
            
            # here it comes as a string, so convert
            polygones = json.loads(q_ramki.get())  # not zoomed right
            # update calibration settings
            calib_area_length_m = float(settings['calib_zone_length'])
            calib_area_width_m = float(settings['calib_zone_width'])
            calib_area_dimentions_m = calib_area_width_m, calib_area_length_m

            # stops setInterval detecting zones sliding windows
            stop.set()

            
            # calculate polygones coordinates in scale
            ramki_scaled = []
            y_size, x_size = wframe.shape[:2]
            if ("polygones") in polygones:
                w_web, h_web = polygones["frame"]
                for k, polygon in enumerate(polygones["polygones"]):
                    polygon_sc = [[x*x_size//w_web, y*y_size//h_web]
                                  for x, y in polygon]
                    
                    ramki_scaled.append(
                        Ramka(polygon_sc,                       # scaled polygon vertex
                            warp_dimentions_px,                 # width, height Top view of calibration zone
                            calib_area_dimentions_m,            # width, height of calibration zone in meter
                            M,                                  # transition matrix
                            polygones["ramkiDirections"][k],    # directions
                            proc_height                         # CNN process window hight
                            ))
                    
            # dlym = ramki_scaled[2].down_limit_y_m
            # print(f'ramki scaled {ramki_scaled}')
            # print(f'ramki directions {ramki_directions} type-{type(ramki_directions)}')
            ramki_status = [0 for i in range(len(ramki_scaled))]
            # when lenght ramki_status changed do below, can't remove ramki_status_ object,
            # because need to save it's reference fo repeated timer
            while len(ramki_status_) > len(ramki_status):
                ramki_status_.pop()
            while len(ramki_status_) < len(ramki_status):
                ramki_status_.append(0)
            # update status60 and status15 structures according to the number of det zones
            # if polygones aren't the same
            if polygones != temp_polygones:
                init_status60_15_struct(len(ramki_scaled)) 
            # start setInterval detecting zones sliding windows
            stop = function()

        # get settings from flask process
        # when setting change on web, it always translate to calc process
        # using Queue
        if not q_settings.empty():
            y_size, x_size = wframe.shape[:2]
            # save old settings to compare them with new ones, 4548
            # if they aren't the same, update statistics (below)
            temp_settings = deepcopy(settings)
            settings = json.loads(q_settings.get())

            if stream_source_type != VideoStreamSources(settings['source_stream_type']):
                stream_source_type = VideoStreamSources(settings['source_stream_type'])
                construct_input_pipline(stream_source_type)
                cap = cv2.VideoCapture(
                    camera_str, cv2.CAP_GSTREAMER)

            addrString[0] = 'https://' + settings["hub"] + '/detect'
            calibrPoints = json.loads(settings["calibration"])
            calibrPoints_sc = [[x*x_size//w_web, y*y_size//h_web]
                               for x, y in calibrPoints]
            print('calibrPoints scaled', calibrPoints_sc)
            calib_area_length_m = float(settings['calib_zone_length'])
            calib_area_width_m = float(settings['calib_zone_width'])
            calib_area_dimentions_m = calib_area_width_m, calib_area_length_m
            # update status60 and status15 structures according to the number of det zones
            # if calib polygone settings aren't the same
            if (temp_settings['calibration'] != settings['calibration']) or (
               temp_settings['calib_zone_length'] != settings['calib_zone_length']) or (
               temp_settings['calib_zone_width'] != settings['calib_zone_width']):
                init_status60_15_struct(len(ramki_scaled)) 

        ### Changing zone colors and statistics ###
        
        # If any track point is inside the detecting zone - change it's state to On.
        # use shapely lib to calculate intersections of polygones (good lib)
        for i, ramka in enumerate(ramki_scaled):
            ramka.color = 0  # for each ramka before iterate for frames, reset it
            ramki_status[i] = 0
            # if some track below cross it, it will be in "on" state for whole frame.
            for track in tracks:
                if not track.complete:
                    shapely_box = box(
                        track.boxes[-1][0], track.boxes[-1][1], track.boxes[-1][2], track.boxes[-1][3])
                    interscec_ = ramka.shapely_path.intersection(
                        shapely_box).area/ramka.area*100
                    if (interscec_ > iou_tresh_perc):
                        # here need to check if track points are in detecting zone, and only then 
                        # switch it on
                        # iterate for points in track, check if point inside the zone
                        for j in range(len(track.points)):
                            point = track.points[len(track.points)-1-j]
                            if Point(point).within(ramka.shapely_path):
                                
                                ### Change ramka status ###
                                ramka.color = 1
                                ramki_status[i] = 1
                                
                                ### Append track speed to ramka ###
                                # put average speed of track to the zone 
                                # if flag obtaining status is False, and it's not the first track point
                                # then obtain status
                                if not track.status_obt and (len(track.points) > 3):

                                    ### Average spped ###
                                    ramka.status['avg_speed_1'].append(round(track.aver_speed))

                                    
                                    ### Intense vehicles by types ###
                                    # CLASSES = {6:"bus"(13), 3:"car"(1), 8:"truck"(2), 4:"motorcicle"}
                                                               
                                    
                                    if track.class_id == 3: # if car
                                        ramka.status['avg_intens_1_tp']['1'].append(round(track.aver_speed))
                                    elif track.class_id == 8: # if truck
                                        ramka.status['avg_intens_1_tp']['2'].append(round(track.aver_speed))
                                    elif track.class_id == 6: # if bus
                                        ramka.status['avg_intens_1_tp']['13'].append(round(track.aver_speed))

                                    # so, track status already obtained, do not do it twice
                                    track.status_obt = True

                # if track                     

            ### Calculate time in zone ###
            if (ramka.color == 1) and (ramka.trig == False):
                ramka.ts = time.time()
                ramka.trig = True
            if (ramka.trig == True) and (ramka.color == 0):
                ramka.status['cur_time_in_zone'] = round((time.time() - ramka.ts), 1)
                ramka.status['times_in_zone_1'].append(ramka.status['cur_time_in_zone'])
                ramka.trig = False
            
                        
        # Draw polygones with arrows
        for i, ramka in enumerate(ramki_scaled):
            color_ = green if ramka.color == 1 else blue

            # draw zone number & current time in zone
            # cv2.putText(frame_show, str(i+1)+' '+str(ramka.status['cur_time_in_zone']), (ramka.center[0]-5, ramka.center[1]+5),
            cv2.putText(frame_show, str(i+1)+' ', (ramka.center[0]-5, ramka.center[1]+5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, color_, 2)
            
            # draw polygones
            cv2.polylines(frame_show, np.array(
                [ramka.path], np.int32), 1, color_, 2)
            # draw arrows
            # for j, arrow in enumerate(poly):
            for j in range(4):
                if ramka.directions[j] == 1:
                    cv2.polylines(frame_show, np.array(
                        [ramka.arrows_path[j]]), 1, color_, 2)
            # draw ramki sides distances from the calibration polygone in meters
            cv2.putText(frame_show, f'{ramka.up_limit_y_m:.1f}', ramka.up_side_center,
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, white, 1)
            cv2.putText(frame_show, f'{ramka.down_limit_y_m:.1f}', ramka.down_side_center,
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, white, 1)

        # do the transform calibration polygone to get top View
        # if top view image needed to be shown in GUI, 
        # use WITH_TOP_VIEW_IMG = True
        WITH_TOP_VIEW_IMG = False

        # show the warped calibration polygone area
        np_calibrPoints_sc = np.array(calibrPoints_sc, dtype="float32")
        # np_calibrPoints_sc = np.array(calibrPoints_sc)
        # get top view
        if WITH_TOP_VIEW_IMG:
            warped_img, M = four_point_transform(
                frame_show, np_calibrPoints_sc, picMode=True)
            warped_width_px = warped_img.shape[1]
            warped_height_px = warped_img.shape[0]
        else:
            # another way without picture, only required params
            M, warped_width_px, warped_height_px = four_point_transform(
                frame_show, np_calibrPoints_sc, picMode=False)

        # convert point coord on the perspective view (originalPoint) to the point coordinates
        # on the Top view. Where perspectiveCoords - 4 point of calib Polygon in perspective,
        # width, hight - in pixels for the 2D top-view field.

        #windowToFieldCoordinates(originalPoint, perspectiveCoords, width=0, height=0)
        # windowToFieldCoordinates(originalPoint, perspectiveCoords, width=0, height=0)
        # нарисуем кружочек на картинке с перспективой
        # это точки - середины ближней и дальней поперечных планок рамки

        # для каждой рамки вычислим в метрах от края калибровочного полигона ее
        # ее верхнюю и нижнюю границу

        '''
        # NOTE! это надо сделать на этапе инициализации рамки или после ее изменения. см пояснения в wiki
        for i, ramka in enumerate(ramki_scaled):
            # взять настройку длины зоны из settings и
            # считать метры от края через пропорцию, Ym/Lm = up_side_center/warped_height
            up_limit_y_px = ramka.up_side_center[1]
            down_limit_y_px = ramka.down_side_center[1]
            # Ym = up_limit_px/warped_height_px*calib_area_length_m
            ramka.up_limit_y_m = up_limit_y_px/warped_height_px*calib_area_length_m
            ramka.down_limit_y_m = down_limit_y_px/warped_height_px*calib_area_length_m

        top_point = (226, 84)
        down_point = (268, 207)
        cv2.circle(frame_show, top_point, 2, green, 2)
        cv2.circle(frame_show, down_point, 2, green, 2)
        # print("M", M)
        # посчитаем координаты кружочка в топвью плоскости и отобразим на варпед картинке
        top_point_np3D = np.array([((top_point[0], top_point[1]), (
            top_point[0], top_point[1]), (top_point[0], top_point[1]))], dtype=np.float32)
        down_point_np3D = np.array([((down_point[0], down_point[1]), (
            down_point[0], down_point[1]), (down_point[0], down_point[1]))], dtype=np.float32)
        trans_point_top = cv2.perspectiveTransform(top_point_np3D, M)[0][0]
        trans_point_down = cv2.perspectiveTransform(down_point_np3D, M)[0][0]
        # сошлось, надо же

        # ramki_scaled[0].up_limit_y_m = trans_point_top[1]/warped_height_px*calib_area_length_m
        up_limit_y_m = trans_point_top[1]/warped_height_px*calib_area_length_m
        # ramki_scaled[0].down_limit_y_m = trans_point_down[1]/warped_height_px*calib_area_length_m
        down_limit_y_m = trans_point_down[1]/warped_height_px*calib_area_length_m
        '''
        # draw calibration polygone
        zero_point = (calibrPoints_sc[0][0]-15, calibrPoints_sc[0][1]+5)
        width_point = (calibrPoints_sc[1][0]+8, calibrPoints_sc[1][1]+5)
        length_point = (calibrPoints_sc[3][0]-35, calibrPoints_sc[3][1]+5)
        cv2.putText(frame_show, "0", zero_point,
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, green, 2)
        cv2.putText(frame_show, str(calib_area_width_m), width_point,
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, green, 2)
        cv2.putText(frame_show, str(calib_area_length_m), length_point,
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, green, 2)
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
            # cv2.namedWindow("Frame", cv2.WINDOW_NORMAL)
            # cv2.imshow("Frame", frame_show)

            if WITH_TOP_VIEW_IMG:
                # warped image show
                cv2.namedWindow("warped", cv2.WINDOW_NORMAL)
                # cv2.imshow("Frame", wframe)
                cv2.imshow("warped", warped_img)

            # put the picture for web in the picture Queue
            put_queue(q_pict, frame_show)
            # fix_this
            key = 0
            # key = cv2.waitKey(key_time) & 0xFF
            # if the `ESC` key was pressed, break from the loop
            if key == 27:
                break
            if key == ord("p"):
                key_time = 0
            if key == ord("o"):
                key_time = 1
            if key == ord("t"):
                tracks = []  # kill all tracks pressing d
        if frm_number % 10 == 0:
            print(f'                                                        {int(tpf_midle)} msec/frm   tracks- {len(tracks)}')
            pass

        # if memmon:
        #     print("[ Top 10 ]")
        #     for stat in top_stats[:10]:
        #         print(stat)

    cap.release()
    cap2.release()
    cv2.destroyAllWindows()


# if __name__ == "__main__":
    # proc()
