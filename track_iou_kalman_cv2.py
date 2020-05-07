"""Tracks objects using ioU analyse
"""
import time
import numpy as np
import cv2
from iou import bb_intersection_over_union

class Track():
    """ create track instances, append given bbox to the end.
        time stamp fix the last append event time
    """
    def __init__(self, bbox, tresh):
        self.boxes = [] # boxes of each track 
        self.points = [] # center box poins of each track
        self.center = 0,0
        # kalman filter functionality 
        self.filtered_points = [] # filtered track points array 
        self.kalman_initialize()
        
        self.append(bbox) 
        self.tresh = tresh
        self.color = self.get_random_color() 
        self.kalman_initialize() # second time? why?


    def kalman_initialize(self):
        """kalman filtering initialization"""
        self.tp = np.zeros((2,1), np.float32) # tracked / prediction
        self.kalman_coef = 0.003 #0.0003
        self.kalman = cv2.KalmanFilter(4, 2)
        self.kalman.measurementMatrix = np.array([[1,0,0,0],[0,1,0,0]],np.float32)
        self.kalman.transitionMatrix = np.array([[1,0,1,0],[0,1,0,1],[0,0,1,0],[0,0,0,1]],np.float32)
        self.kalman.processNoiseCov = np.array([[1,0,0,0],[0,1,0,0],[0,0,1,0],[0,0,0,1]],np.float32) * self.kalman_coef

      
    def append(self, bbox): 
        ''' fiil up bboxes and point lists '''
        self.boxes.append(bbox)
        self.center = self.bbox_center(bbox)
        self.points.append(self.center)
        # kalman filtering of track points
        self.kalman_filtering(self.center)
        # appendiing filtered points array
        tp_tuppl = (int(self.tp[0]),int(self.tp[1]))
        self.filtered_points.append(tp_tuppl)
        # print ('mp, tp=', self.center, self.tp)
        self.ts = time.time()


    def kalman_filtering(self, center):
        ''' kalman filtering for input pair center. return filtered pair'''
        mp = np.array([[np.float32(center[0])],[np.float32(center[1])]])
        self.kalman.correct(mp)
        self.tp = self.kalman.predict()


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
        if (iou_val >= self.tresh):
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

    def draw_tracks(self, frm):
        '''draw tracks points and lines'''
        kalman_enable = True
        if len(self.points) > 5: # если в треке достаточно точек для рисования
            if True:#not kalman_enable:
                for i, point in enumerate(self.points):
                    cv2.circle(frm, point, 2, self.color, thickness=2)
                    # print('len(self.points)',len(self.points)) 
                    if (i < len(self.points)-1): # если существует след точка то линию между текущей и следующей точкой
                        cv2.line(frm, self.points[i], self.points[i+1], self.color, thickness=1)
            if True:#else:
                for i, point in enumerate(self.filtered_points):
                    cv2.circle(frm, point, 2, (255,255,255), thickness=2)
                    # print('len(self.points)',len(self.points)) 
                    if (i < len(self.filtered_points)-1): # если существует след точка то линию между текущей и следующей точкой
                        cv2.line(frm, self.filtered_points[i], self.filtered_points[i+1], self.color, thickness=1)
                    
