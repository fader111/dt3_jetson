import numpy as np
import cv2
import time

video_src = "U524806_3.avi"
cap = cv2.VideoCapture(video_src)
tic = 0

while(True):
    tic += 1
    ts = time.time()
    # Capture frame-by-frame
    ret, frame = cap.read()

    # Our operations on the frame come here
    gray = frame #cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    # Display the resulting frame
    cv2.namedWindow('frame', cv2.WINDOW_NORMAL)
    cv2.imshow('frame', gray)
    tot_elapsed_time = str(round((time.time()-ts), 2))
    if tic > 50:
        print(tot_elapsed_time)
        tic = 0
    if cv2.waitKey(1) & 0xFF == 27:
        break

# When everything done, release the capture
cap.release()
cv2.destroyAllWindows()
