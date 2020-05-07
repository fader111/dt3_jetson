# import the necessary packages
from imutils.video import VideoStream
import argparse
import imutils
import time
import cv2

width = 1280
height = 720

# USE_CAMERA = 1

camera_str = f"nvarguscamerasrc ! video/x-raw(memory:NVMM), width=(int){str(width)}, \
		height=(int){str(height)},format=(string)NV12, framerate=(fraction)60/1 ! nvvidconv flip-method=2 ! \
        video/x-raw, width=(int)1280, height=(int)720, format=(string)BGRx ! \
        videoconvert ! video/x-raw, format=(string)BGR ! appsink"

# construct the argument parser and parse the arguments
ap = argparse.ArgumentParser()
ap.add_argument("-v", "--video", type=str, #default='/home/a/dt3_jetson/U524806_3.avi',
	help="path to input video file")
ap.add_argument("-t", "--tracker", type=str, default="medianflow",
	help="OpenCV object tracker type")
args = vars(ap.parse_args())

# initialize a dictionary that maps strings to their corresponding
# OpenCV object tracker implementations
OPENCV_OBJECT_TRACKERS = {
	"csrt": cv2.TrackerCSRT_create, #slow 154ms
	"kcf": cv2.TrackerKCF_create, # slow and bad 145ms
	"boosting": cv2.TrackerBoosting_create, # slow and bad 155ms
	"mil": cv2.TrackerMIL_create, # very slow 250ms
	"tld": cv2.TrackerTLD_create,  # very slow 250ms
	"medianflow": cv2.TrackerMedianFlow_create, # fast 100ms zoomed!!! The best one!!
	"mosse": cv2.TrackerMOSSE_create # fast 100ms, do not zoom at all
}
# initialize OpenCV's special multi-object tracker
trackers = cv2.MultiTracker_create()

# if a video path was not supplied, grab the reference to the web cam
if not args.get("video", False):
    print("[INFO] starting video stream...")
    # vs = VideoStream(src=camera_str).start()
    vs = cv2.VideoCapture(camera_str, cv2.CAP_GSTREAMER) 
    # time.sleep(1.0)
# otherwise, grab a reference to the video file
else:
	vs = cv2.VideoCapture(args["video"])

# loop over frames from the video stream
while True:
    # grab the current frame, then handle if we are using a
    # VideoStream or VideoCapture object
    ts = time.time()
    ret, frame = vs.read()
    #frame = frame[1] if args.get("video", False) else frame
    # check to see if we have reached the end of the stream
    if frame is None:
        break
    # resize the frame (so we can process it faster)
    frame = cv2.resize(frame, (800,600))

    # grab the updated bounding box coordinates (if any) for each
    # object that is being tracked
    (success, boxes) = trackers.update(frame)
    # loop over the bounding boxes and draw then on the frame
    for box in boxes:
        (x, y, w, h) = [int(v) for v in box]
        cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)

    frame_rate_str = f'{(time.time()-ts)*1000:.4} msec/frm'
    cv2.putText(frame, frame_rate_str, (15, 15), cv2.FONT_HERSHEY_DUPLEX, 0.5, (255,255,255), 1)

    # show the output frame
    cv2.imshow("Frame", frame)
    key = cv2.waitKey(1) & 0xFF
    # if the 's' key is selected, we are going to "select" a bounding
    # box to track
    if key == ord("s"):
        # select the bounding box of the object we want to track (make
        # sure you press ENTER or SPACE after selecting the ROI)
        box = cv2.selectROI("Frame", frame, fromCenter=False,
            showCrosshair=True)
        print(f'box {box}')
        # create a new object tracker for the bounding box and add it
        # to our multi-object tracker
        tracker = OPENCV_OBJECT_TRACKERS[args["tracker"]]()
        trackers.add(tracker, frame, box)
    elif key == ord("c"):
        trackers = cv2.MultiTracker_create()    

# if the Esc key was pressed, break from the loop
    elif key == 27:
        break
# if we are using a webcam, release the pointer
if not args.get("video", False):
	vs.stop()
# otherwise, release the file pointer
else:
	vs.release()
# close all windows
cv2.destroyAllWindows()