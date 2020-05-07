""" gets detections from some detector. Build treks based on iou algorythm.
    gets frames, make iou's to each in the frames in detection set. 
    Assign frame to the end of the track
"""

import time
import sys
import cv2
import numpy as np
from common import clock, draw_str, draw_rects
from RepeatedTimer_ import RepeatedTimer
from haar_cascade_detector import detect, gamma
from iou import bb_intersection_over_union

cascade_path = 'vehicles_cascadeLBP_w25_h25_p2572_n58652_neg_roof.xml'
# cascade_path = 'vehicle_cascadeLBP_w20_h20_p2139.xml'

tracks = []
iou_tresh = 0.5
video_src = "U524806_3.avi"
# video_src = "G:/fotovideo/video_src/usb2.avi"
bboxes = [] # bbox's of each frame
max_track_lifetime = 3
USE_GAMMA = False

class Track():
    """ create track instances, append given bbox to the end.
        time stamp fix the last append event time
    """
    def __init__(self, bbox):
        self.boxes = [] # boxes of each track 
        self.points = [] # center box poins of each track
        self.append(bbox) 
        self.color = self.get_random_color() 
      

    def append(self, bbox): 
        ''' fiil up bboxes and point lists '''
        self.boxes.append(bbox)
        center = self.bbox_center(bbox)
        self.points.append(center)
        self.ts = time.time()


    def is_old(self):
        '''check how old/actual track is '''
        pass #if self.ts - time.time() > self.__class__.life_time:
            # del(self)


    def get_random_color(self):
        '''returns random color '''
        col = np.random.choice(range(256), size=3)
        return int(col[0]), int(col[1]), int(col[2])


    def track_assignment(self, bbox):
        '''decides if getting bbox fit to the track, appends if yes'''
        # print('bbox in track_assignment ', bbox)
        iou_val = bb_intersection_over_union(bbox, self.boxes[-1])
        # print('iou_val ', iou_val)
        if (iou_val == 1):
            #print('same')
            return False
        if (iou_val >= iou_tresh):
            self.append(bbox)
            # print('appended! ', iou_val)
            return True   
        return False
        

    def bbox_center(self, bbox):
        '''calculates the center point bbox'''
        x1, y1, x2, y2 = bbox
        xmax = max(x1, x2)
        xmin = min(x1, x2)    
        ymax = max(y1, y2)
        ymin = min(y1, y2)    
        xc = (xmax+xmin)/2
        yc = (ymax+ymin)/2
        return int(xc), int(yc)

    def draw_tracks(self):
        ''' draw tracks points and lines'''
        if len(self.points) > 5: # если в треке достаточно точек для рисования
            for i, point in enumerate(self.points):
                cv2.circle(vis, point, 2, self.color, thickness=2)
                # print('len(self.points)',len(self.points)) 
                if (i < len(self.points)-1): # если существует след точка то линию между текущей и следующей точкой
                    cv2.line(vis, self.points[i], self.points[i+1], self.color, thickness=1)

def ts():
    return time.time()


if __name__ == "__main__":
    cap = cv2.VideoCapture(video_src)
    ret, img = cap.read()

    cascade = cv2.CascadeClassifier(cascade_path)
    frm_number = 0
    while ret:
        #print('len tracks main = ', len(tracks))
        frm_number += 1
        #print('frm_numb ', frm_number)
        ret, img = cap.read()
        if not ret: 
            print('Once again! ', )
            cap = cv2.VideoCapture(video_src)
            ret, img = cap.read()
            # sys.exit()

        # надо еще подумать - трекать по автомобилю, или по пластине внутри автомобиля (наверное втрое) 
        # пока трек надо попробовать построить по машине. 

        img = cv2.resize(img, (640, 480))
        if USE_GAMMA:
            img = gamma(img)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        # gray = cv2.equalizeHist(gray)
        
        t = clock()
        bboxes = detect(gray, cascade)
        # print('bboxes', bboxes)
        #remove_bad_bboxes(bboxes)
        
        for i, bbox in enumerate(bboxes):
            # print('bbox', bbox)
            assign_flag = 0 # признак того, что для данного ббокса не было назначения ни одному треку
            for track in tracks:
                if (not assign_flag) & track.track_assignment(bbox):
                    assign_flag = 1 # если назначено, переходим к следующему ббоксу
            # if pass thru the all tracks and no assignment, make a new track with it
            if assign_flag == 0: 
                tracks.append(Track(bbox))
                # print('len tracks from bboxes= ', len(tracks))


        dt = clock() - t
        vis = img.copy()
        draw_rects(vis, bboxes, (0, 255, 0))
        # cv2.bboxangle(vis, (10, 10), (100, 100), (255,0,0), 2) просто для проверки
        
        # remove very old tracks and bad tracks
        for i, track in enumerate(tracks):
            # if max track life time is over, or track isn't appended for more than 1 sec, del it
            if (ts() - track.ts > max_track_lifetime) | ((ts() - track.ts > 3) & (len(track.points) < 5)):
                print ('del',i, '/',len(tracks))
                del(tracks[i])


        # draw tracks
        for track in tracks:
            track.draw_tracks()

        draw_str(vis, (20, 20), 'time: %.1f ms' % (dt*1000))
        cv2.imshow(str(cascade_path), vis)
        if cv2.waitKey(1) == 27:
            break
    cap.release()
    cv2.destroyAllWindows()
    cv2.KalmanFilter()