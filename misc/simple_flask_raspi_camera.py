''' test for csi camera on Jetson Nano
    that pipeline works on JetPack 4.4

    gst-launch-1.0 nvarguscamerasrc sensor_id=0 ! \
   'video/x-raw(memory:NVMM),width=3280, height=2464, framerate=21/1, format=NV12' ! \
   nvvidconv flip-method=0 ! 'video/x-raw,width=960, height=720' ! \
   nvvidconv ! nvegltransform ! nveglglessink -e
'''

import cv2
import time
import threading
from flask import Response, Flask

# Image frame sent to the Flask object
global video_frame
video_frame = None

# Use locks for thread-safe viewing of frames in multiple browsers
global thread_lock 
thread_lock = threading.Lock()

# GStreamer Pipeline to access the Raspberry Pi camera
GSTREAMER_PIPELINE = 'nvarguscamerasrc ! video/x-raw(memory:NVMM), width=3280, height=2464, \
    format=(string)NV12, framerate=30/1 ! nvvidconv flip-method=0 ! video/x-raw, width=960, \
        height=616, format=(string)BGRx ! videoconvert ! video/x-raw, format=(string)BGR ! \
            appsink'# wait-on-eos=false max-buffers=1 drop=True'

# for JetPack 4.4
GSTREAMER_PIPELINE2 = "nvarguscamerasrc sensor_id=0 ! \
   'video/x-raw(memory:NVMM),width=3280, height=2464, framerate=21/1, format=NV12' ! \
   nvvidconv flip-method=0 ! 'video/x-raw,width=960, height=720' ! \
   nvvidconv ! nvegltransform ! nveglglessink -e'# wait-on-eos=false max-buffers=1 drop=True"

GSTREAMER_PIPELINE = f"nvarguscamerasrc ! video/x-raw(memory:NVMM), width=(int)3280, \
		height=(int)2464,format=(string)NV12, framerate=(fraction)30/1 ! nvvidconv ! \
        video/x-raw, width=(int)1280, height=(int)720, format=(string)BGRx ! \
        videoconvert ! video/x-raw, format=(string)BGR ! appsink "#wait-on-eos=false max-buffers=1 drop=True"




# Create the Flask object for the application
app = Flask(__name__)

def captureFrames():
    global video_frame, thread_lock

    # Video capturing from OpenCV
    video_capture = cv2.VideoCapture(GSTREAMER_PIPELINE, cv2.CAP_GSTREAMER)
    
    while True:# and video_capture.isOpened():
        return_key, frame = video_capture.read()
        if not return_key:
            print ('No video captured')
            continue

        # Create a copy of the frame and store it in the global variable,
        # with thread safe access
        with thread_lock:
            video_frame = frame.copy()
        
        cv2.imshow('frame', video_frame)

        key = cv2.waitKey(30) & 0xff
        if key == 27:
            break

    video_capture.release()
        
def encodeFrame():
    global thread_lock
    while True:
        # Acquire thread_lock to access the global video_frame object
        with thread_lock:
            global video_frame
            if video_frame is None:
                continue
            return_key, encoded_image = cv2.imencode(".jpg", video_frame)
            if not return_key:
                continue

        # Output image as a byte array
        yield(b'--frame\r\n' b'Content-Type: image/jpeg\r\n\r\n' + 
            bytearray(encoded_image) + b'\r\n')

@app.route("/")
def streamFrames():
    return Response(encodeFrame(), mimetype = "multipart/x-mixed-replace; boundary=frame")

# check to see if this is the main thread of execution
if __name__ == '__main__':

    # Create a thread and attach the method that captures the image frames, to it
    process_thread = threading.Thread(target=captureFrames)
    process_thread.daemon = True

    # Start the thread
    process_thread.start()

    # start the Flask Web Application
    # While it can be run on any feasible IP, IP = 0.0.0.0 renders the web app on
    # the host machine's localhost and is discoverable by other machines on the same network 
    app.run("0.0.0.0", port="8080")
