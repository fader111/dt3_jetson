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

    def __init__(self, rgb, bbox, tr_number, ClassID, confidence, warp_dimentions_px,
                 calib_area_dimentions_m, M, max_point_number=40):
        self.boxes = []         # track boxes
        self.points = []        # track points
        self.warp_points = []   # track points converted to meters on the road
        self.aver_speed = 0     # average speed of vechicle
        self.tr_number = tr_number
        self.class_id = ClassID
        self.confidence = confidence
        self.max_point_number = max_point_number
        self.complete = False   # True means - car went out, don't append it more
        self.status_obt = False # Status of Track obtained by the detection zone class

        # warp section
        self.warped_width_px, self.warped_height_px = warp_dimentions_px
        self.calib_area_width_m, self.calib_area_length_m = calib_area_dimentions_m
        self.M = M # warped polygone transformation Matrix

        self.boxes.append(bbox)
        pt = self.bbox_center_bottom(bbox)
        self.points.append(pt)
        self.warp_points.append(self.calc_warped_coord(pt))
        self.t = dlib.correlation_tracker()
        rect = dlib.rectangle(bbox[0], bbox[1], bbox[2], bbox[3])
        self.t.start_track(rgb, rect)
        self.color = self.get_random_color()

        # timing section
        self.ts = time.time()
        self.renew_ts = time.time()
        # timestamp of previous point, for speed measuring
        # updates in renew() and update() methods
        self.prev_ts = 0

    def renew(self, rgb, bbox, ClassID, confidence):
        ''' appends bboxes to track in detection phase:
            delete tracker, make a new one'''
        self.class_id = ClassID
        self.confidence = confidence
        self.boxes.append(bbox)
        pt = self.bbox_center_bottom(bbox)
        self.points.append(pt)
        self.warp_points.append(self.calc_warped_coord(pt))
        self.t = dlib.correlation_tracker()
        rect = dlib.rectangle(bbox[0], bbox[1], bbox[2], bbox[3])
        self.t.start_track(rgb, rect)
        self.prev_ts = self.ts
        self.ts = time.time()
        self.renew_ts = time.time()
        self.calc_average_speed()

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
            pt = self.bbox_center_bottom(bbox)
            self.points.append(pt)
            self.warp_points.append(self.calc_warped_coord(pt))
            # if number of points in track more then max limit, delete it from the begining
            while len(self.points) > self.max_point_number:
                self.boxes.pop(0)  # boxes also
                self.points.pop(0)
                self.warp_points.pop(0)
            self.prev_ts = self.ts
            self.ts = time.time()
            self.calc_average_speed()
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

    def calc_warped_coord(self, pt):
        ''' set warped coords in meters for each track point'''
        # берем точку, с помощью матрицы трансформации вычисляем
        # ее координаты на топвью в пикселах, зная размеры зоны топвью в метрах
        # и в пикселах, вычисляем координаты точки на топвью в метрах.

        pt_np = np.array([(pt, pt, pt)], dtype=np.float32)
        # координаты точки в Top View в пикселах
        pt_warped = cv2.perspectiveTransform(pt_np, self.M)[0][0]
        # координаты точки в метрах от дальнего угла калибровочного полигона
        pt_m = pt_warped[0] / self.warped_width_px * self.calib_area_width_m, \
            pt_warped[1] / self.warped_height_px * self.calib_area_length_m
        return pt_m

    def calc_average_speed(self):
        ''' calculates the average speed over the track '''
        # средняя скорость: M` = (M*N+n) / (N+1) , где M -среднее значение на предыдущем шаге
        # N- количество значений, n - новое значение
        #
        # найдем скорость на последнем отрезке, но! тут одним последним таймстампом не обойдешься.
        # нужен еще предыдущий. добавляем его. обновлять его тоже надо.
        # скорость ищем только по координате y
        if len(self.warp_points) > 1:
            speed = int(3.6*(self.warp_points[-1][1] -
                     self.warp_points[-2][1])/(self.ts-self.prev_ts))
            if self.aver_speed == 0:  # первое измерение
                self.aver_speed = speed
            else:
                self.aver_speed = (
                    self.aver_speed*len(self.warp_points)+speed) / (len(self.warp_points)+1)

    def draw_tracks(self, frm):
        '''draw tracks points and lines'''
        if 1:  # len(self.points) > 2:  # если в треке достаточно точек для рисования
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
            # show the y coord Top View in meter under the box
            # text = f'{(self.warp_points[-1][0]):.1f} ' f'{(self.warp_points[-1][1]):.1f}m'
            #text = f'{(self.warp_points[-1][1]):.1f}m'
            speed_km_h = self.aver_speed
            text = f'{speed_km_h:.1f}km/h'
            cv2.putText(frm, text, (self.points[-1][0], self.points[-1][1]+15),
                        cv2.FONT_HERSHEY_DUPLEX, 0.5, (255, 255, 255), 1)
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
