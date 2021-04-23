''' test for csi camera on Jetson Nano
    that pipeline works on JetPack 4.4

    gst-launch-1.0 nvarguscamerasrc sensor_id=0 ! \
   'video/x-raw(memory:NVMM),width=3280, height=2464, framerate=21/1, format=NV12' ! \
   nvvidconv flip-method=0 ! 'video/x-raw,width=960, height=720' ! \
   nvvidconv ! nvegltransform ! nveglglessink -e
'''

import cv2, sys
import time
import threading
# from multiprocessing.dummy import Process, Queue
# from multiprocessing import Process, Queue
from flask import Response, Flask

import jetson.inference
import jetson.utils  

t = time.time

# Image frame sent to the Flask object
global video_frame
video_frame = None

# Use locks for thread-safe viewing of frames in multiple browsers
global thread_lock 
thread_lock = None#threading.Lock()

# Create the Flask object for the application
app = Flask(__name__)

def captureFrames():
    global video_frame, thread_lock

    cap = jetson.utils.videoSource('', argv=sys.argv)
    frm_num =0
    while True:# and video_capture.isOpened():
        ts = t()
        img_cuda_raw = cap.Capture()
        # resize the image
        # allocate the output, with half the size of the input
        '''img_cuda = jetson.utils.cudaAllocMapped(
                                                        width=1920, 
                                                        height=1080, 
                                                        format=img_cuda_raw.format)
        '''
        # print ('imgInput.width ', imgInput.width, 'imgInput.height ', imgInput.height) # 1080 x 720
        # rescale the image (the dimensions are taken from the image capsules)
        # jetson.utils.cudaResize(img_cuda_raw, img_cuda)

        # allocate buffers for this size image
        # buffers.Alloc(img_input.shape, img_input.format)
        # buffers.Alloc(img_cuda.shape, img_cuda.format)

        # img = cv2.cvtColor(jetson.utils.cudaToNumpy(img_cuda), cv2.COLOR_BGR2RGB)
        # img = jetson.utils.cudaToNumpy(img_cuda)
        img = jetson.utils.cudaToNumpy(img_cuda_raw)
        # img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

        jetson.utils.cudaDeviceSynchronize() # good effect

        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        video_frame = img#.copy()
        
        cv2.imshow('frame', video_frame)

        key = cv2.waitKey(1)
        if key == 27:
            break
        
        ##jetson.utils.cudaDeviceSynchronize() # bad effect

        if frm_num%100 ==0:
            print(f'elapset {(t()-ts):.3f} frm size {video_frame.shape}')
        frm_num +=1
    video_capture.release()
        
def encodeFrame():
    global thread_lock
    while True:
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
    #process_thread.daemon = True

    # Start the thread
    process_thread.start()
    # capturedFrames()

    #main_proc = Process(target=captureFrames)
    # main_proc.start()

    # start the Flask Web Application
    # While it can be run on any feasible IP, IP = 0.0.0.0 renders the web app on
    # the host machine's localhost and is discoverable by other machines on the same network 
    app.run(host='0.0.0.0', port=8080, debug=False,
            threaded=True, use_reloader=False)
