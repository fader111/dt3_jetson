''' Track object has id, track points list, dlib tracker inside
'''
import time
import numpy as np
import cv2
# from pykalman import KalmanFilter
from common_tracker import bbox_touch_the_border
# import math
import dlib


class Track:
    ''' track class includes dlib corr tracker '''

    def __init__(self, rgb, bbox, tr_number, ClassID, confidence, max_point_number = 40):
        self.boxes = []  # track boxes
        self.points = []  # track points
        self.tr_number = tr_number
        self.class_id = ClassID
        self.confidence = confidence
        self.max_point_number = max_point_number
        self.complete = False  # True means - car went out, don't append it more
        self.boxes.append(bbox)
        self.points.append(self.bbox_center_bottom(bbox))
        self.t = dlib.correlation_tracker()
        rect = dlib.rectangle(bbox[0], bbox[1], bbox[2], bbox[3])
        self.t.start_track(rgb, rect)
        self.color = self.get_random_color()
        self.ts = time.time()
        self.renew_ts = time.time()

    def renew(self, rgb, bbox, ClassID, confidence):
        ''' appends bboxes to track in detection phase:
            delete tracker, make a new one'''
        self.class_id = ClassID
        self.confidence = confidence
        self.boxes.append(bbox)
        self.points.append(self.bbox_center_bottom(bbox))
        self.t = dlib.correlation_tracker()
        rect = dlib.rectangle(bbox[0], bbox[1], bbox[2], bbox[3])
        self.t.start_track(rgb, rect)
        self.ts = time.time()
        self.renew_ts = time.time()

    def update(self, rgb):
        ''' updates self.t tracker in tracking phase'''
        self.t.update(rgb)
        pos = self.t.get_position()
        x1 = int(pos.left())
        y1 = int(pos.top())
        x2 = int(pos.right())
        y2 = int(pos.bottom())
        bbox = (x1, y1, x2, y2)
        # if bbox touches the border of the frame, do not append it
        if not bbox_touch_the_border(bbox, rgb.shape[0], rgb.shape[1]):
            self.boxes.append(bbox)
            self.points.append(self.bbox_center_bottom(bbox))
            # points in track more then 100, delete it from the begining
            while len(self.points) > self.max_point_number:
                self.boxes.pop(0)
                self.points.pop(0)
            self.ts = time.time()
        else:
            self.complete = True
        

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

    def bbox_center_bottom(self, bbox):
        '''calculates position in the middle of bottom '''
        x1, y1, x2, y2 = bbox
        xmax = max(x1, x2)
        xmin = min(x1, x2)
        ymax = max(y1, y2)
        ymin = min(y1, y2)
        xc = (xmax+xmin)/2
        yb = ymax
        return int(xc), int(yb)

    def get_random_color(self):
        '''returns random color '''
        col = np.random.choice(range(256), size=3)
        return int(col[0]), int(col[1]), int(col[2])

    def draw_tracks(self, frm):
        '''draw tracks points and lines'''
        if 1:#len(self.points) > 2:  # если в треке достаточно точек для рисования
            cv2.putText(frm, str(self.tr_number), (self.points[0][0]+5, self.points[0][1]+5),
                        cv2.FONT_HERSHEY_DUPLEX, 0.5, self.color, 1)
            if True:  # not self.filtr:
                for i, point in enumerate(self.points):
                    cv2.circle(frm, point, 0, self.color, thickness=2)
                    # print('len(self.points)',len(self.points))
                    # если существует след точка то линию между текущей и следующей точкой
                    if (i < len(self.points)-1):
                        cv2.line(
                            frm, self.points[i], self.points[i+1], self.color, thickness=1)
            # kalman track
            '''
            if self.filtr:
                for i, point in enumerate(self.filtered_points):
                    # make a new color for the kalman track, move to the __init__ if ot's ok
                    # self.kalm_color = self.color[0]+10, self.color[1]+10, self.color[2]+10
                    self.kalm_color = (255, 255, 255)
                    cv2.circle(frm, point, 0, self.kalm_color, thickness=2)
                    # print('len(self.points)',len(self.points))
                    # если существует след точка то линию между текущей и следующей точкой
                    if (i < len(self.filtered_points)-1):
                        cv2.line(
                            frm, self.filtered_points[i], self.filtered_points[i+1], self.kalm_color, thickness=1)
            '''
