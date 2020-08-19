# работает
# gst-launch-1.0 nvarguscamerasrc ! 'video/x-raw(memory:NVMM),width=3820, height=2464, framerate=21/1, format=NV12' ! nvvidconv flip-method=0 ! 'video/x-raw,width=960, height=616' ! nvvidconv ! nvegltransform ! nveglglessink -e
width = 3820
height = 2464
width = 1920
height = 1080
src2 = f"nvarguscamerasrc ! video/x-raw(memory:NVMM), width=(int){str(width)}, \
		height=(int){str(height)},format=(string)NV12, framerate=(fraction)60/1 ! nvvidconv flip-method=0 ! \
        video/x-raw, width=(int)1280, height=720, format=(string)BGRx ! \
        videoconvert ! video/x-raw, format=(string)BGR ! appsink"

src3 = f"nvarguscamerasrc ! video/x-raw(memory:NVMM), width=3820, \
		height=2464,format=(string)NV12, framerate=(fraction)60/1 ! nvvidconv flip-method=2 ! \
        video/x-raw, width=1920, height=1080, format=(string)BGRx ! \
        videoconvert ! video/x-raw, format=(string)BGR ! appsink"

src = f"nvarguscamerasrc ! video/x-raw(memory:NVMM),width=3820, height=2464, framerate=21/1, format=NV12 \
    ! nvvidconv flip-method=0 ! video/x-raw, width=960, height=616 ! nvvidconv ! nvegltransform ! nveglglessink -e"

import cv2
cap = cv2.VideoCapture(src, cv2.CAP_GSTREAMER)
while(cap.isOpened()):
    ret, frame = cap.read()

#  gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

#  cv2.imshow('frame',gray)
    cv2.imshow('frame', frame)
    if cv2.waitKey(1) == 27:
        break
cap.release()
cv2.destroyAllWindows()