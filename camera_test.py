#!/usr/bin/env python3
import cv2
import time 

def puttxt(image, text, ):	
	'''cv2.putText(image, text, org, font, fontScale, color[, thickness[, lineType[, bottomLeftOrigin]]])
	'''
	org=(50,50)
	font=cv2.FONT_HERSHEY_SIMPLEX
	cv2.putText(image, text, org, font, fontScale=1, color=(0,255,0), thickness =2)


def CaptureImage():
	imageName = 'DontCare.jpg' #Just a random string
	w= 1080#800#1920
	h = 608#600#960
	#cap = cv2.VideoCapture(0)
	# 8Mp camera 
	cap = cv2.VideoCapture("nvarguscamerasrc ! video/x-raw(memory:NVMM), width=(int)"+str(w)+", \
		height=(int)"+str(h)+",format=(string)NV12, framerate=(fraction)30/1 ! nvvidconv ! video/x-raw, \
		format=(string)BGRx ! videoconvert ! video/x-raw, format=(string)BGR ! appsink")
	# 1920x960 - 8fps    800x600 - 20 fps
	#cap.set(3,w)
	#cap.set(4,h)
	ret, frame = cap.read()
	time.sleep(2)
	#print ("frame shape ",frame.shape)
	while(True):
	    # Capture frame-by-frame
	    ts = time.time()
	    ret, frame = cap.read()

	    #gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) #For capture image in monochrome
	    rgbImage = frame #For capture the image in RGB color space
	    fps = round((1/(time.time()-ts)),1)
	    puttxt(frame, 'fps '+str(fps))	
	    # Display the resulting frame
	    pic_name = 'Webcam '+str(frame.shape[1])+'x'+str(frame.shape[0])+' -ESC for break '
	    cv2.namedWindow(pic_name, cv2.WINDOW_AUTOSIZE)	    
	    cv2.imshow(pic_name, rgbImage)
	    #Wait to press 'ESC' key for capturing
	    
	    if cv2.waitKey(1) == 27:
	        #Set the image name to the date it was captured
	        imageName = str(time.strftime("%Y_%m_%d_%H_%M_%s")) + '.jpg'
	        #Save the image
	        cv2.imwrite(imageName, rgbImage)
	        break
	# When everything done, release the capture
	cap.release()
	cv2.destroyAllWindows()
	#Returns the captured image's name
	return imageName 

if __name__ == "__main__":
	CaptureImage()

