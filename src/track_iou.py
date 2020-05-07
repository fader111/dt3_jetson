""" Tracks objects using ioU analyse. Kalman track filtering also possible.
    If detector loose the object, kalman try to predict it position, copy the previous 
    detection bbox to the predicted position. 
"""
import time
import numpy as np
import cv2
from pykalman import KalmanFilter
from iou import bb_intersection_over_union
import math


class Track():
    """ create track instances, append given bbox to the end.
        time stamp fix the last append event time
    """
    #  matrix for kalman filtering
    transition_matrix = [[1, 1, 0, 0],
                         [0, 1, 0, 0],
                         [0, 0, 1, 1],
                         [0, 0, 0, 1]]

    # observation_covariance = [[6400, 0], [0, 6400]]

    observation_matrix = [[1, 0, 0, 0],
                          [0, 0, 1, 0]]

    def __init__(self, bbox, tresh, tr_number, filtr=True, max_len=50):
        self.filtr = filtr  # kalman filtering flag
        self.boxes = []  # boxes of each track
        self.points = []  # center box poins of each track
        self.center = 0, 0  # var for saving current bbox center
        self.tp = 0, 0   # var for saving current kalman filter prediction
        # kalman filter functionality
        self.filtered_points = []  # filtered track points array
        self.max_len = max_len
        self.tresh = tresh
        self.updated = False  # means that track was appended in the last frame
        self.tr_number = tr_number
        self.center = self.bbox_center(bbox)
        self.center_bottom = self.bbox_center_bottom(bbox)
        if self.filtr:
            # self.kalman_initialize(self.center)
            self.kalman_initialize(self.center_bottom)
        self.append(bbox)
        self.color = self.get_random_color()
        # self.kalman_initialize()

    def kalman_initialize(self, start_point=(0, 0), start_speed=(0, 0), coef=5000.0):
        """kalman filtering initialization"""
        self.tp = np.zeros((2, 1))  # track predicted value
        self.kalman = KalmanFilter(transition_matrices=self.transition_matrix,
                                   observation_matrices=self.observation_matrix)
        self.kalman = self.kalman.em(np.asarray([(0, 0), (0, 0)]), n_iter=5)
        # self.kalman = self.kalman.em(np.asarray([self.center, (0,0)]), n_iter=5)
        self.kalman.initial_state_mean = [
            start_point[0], start_speed[0], start_point[1], start_speed[1]]
        self.filtered_state_means = self.kalman.initial_state_mean
        self.filtered_state_covariances = self.kalman.initial_state_covariance
        # observation_covariance need to be changed here, because default aren't ok,
        # and em method changes it.
        self.kalman.observation_covariance = coef*self.kalman.observation_covariance
        '''
        print('self.kalman.initial_state_mean', self.kalman.initial_state_mean)
        print('self.filtered_state_covariances',
              self.filtered_state_covariances)
        print('self.kalman.observation_covariance',
              self.kalman.observation_covariance)
        '''

    def kalman_filtering(self, center):
        ''' kalman filtering for input pair center. return filtered pair'''
        mp = np.array([center[0], center[1]])
        self.filtered_state_means, self.filtered_state_covariances = \
            self.kalman.filter_update(
                self.filtered_state_means, self.filtered_state_covariances, observation=mp)
        self.tp = (int(self.filtered_state_means[0]), int(
            self.filtered_state_means[2]))
        obs_cov = self.kalman.observation_covariance

    def append(self, bbox):
        ''' fiil up bboxes and point lists '''
        self.boxes.append(bbox)
        if len(self.boxes) > self.max_len:
            self.pop()
        self.center = self.bbox_center(bbox)
        self.center_bottom = self.bbox_center_bottom(bbox)
        # self.points.append(self.center) # track from the
        self.points.append(self.center_bottom)
        # kalman filtering of track points
        if self.filtr:
            # self.kalman_filtering(self.center) # draw track from the bbox center
            # draw track from the bbox center_bottom line
            self.kalman_filtering(self.center_bottom)
            # appendiing filtered points array
            #tp_tuppl = (int(self.tp[0]),int(self.tp[1]))
            self.filtered_points.append(self.tp)
        self.ts = time.time()

    def build_box_from_pred_point(self):
        ''' when detector lose the object it's needed to add unexisting bbox to track.
            it can build moving the last track bbox to predicted 
            by Kalman filter point '''
        last_bbox = self.boxes[-1]
        last_box_middle_bottom_point = (
            int((last_bbox[0]+last_bbox[2])/2), int(last_bbox[3]))
        target_middle_bottom_point = self.tp
        # print ('self.filtered_points', self.filtered_points)
        moving_vector = ((target_middle_bottom_point[0]-last_box_middle_bottom_point[0]),
                         (target_middle_bottom_point[1]-last_box_middle_bottom_point[1]))
        target_box = (last_bbox[0]+moving_vector[0], last_bbox[1]+moving_vector[1],
                      last_bbox[2]+moving_vector[0], last_bbox[3]+moving_vector[1])
        return target_box

    def pop(self):
        ''' if track is too long, reduce it, by pop the oldest values'''
        self.boxes.pop()
        self.points.pop()
        if self.filtr:
            self.filtered_points.pop()

    def is_old(self):
        '''check how old/actual track is '''
        pass  # if self.ts - time.time() > self.__class__.life_time:
        # del(self)

    def get_random_color(self):
        '''returns random color '''
        col = np.random.choice(range(256), size=3)
        return int(col[0]), int(col[1]), int(col[2])

    def distance_calc(self, p1, p2):
        ''' calculates distance between p1(x,y) and p2 '''
        xlen = p2[0]-p1[0]
        ylen = p2[1]-p1[1]
        return int(math.sqrt(xlen*xlen+ylen*ylen))

    def track_assignment(self, bbox):  # by IoU algorythm
        '''decides if getting bbox fit to the track
        ising IoU algotyhm, appends if yes'''
        # print('bbox in track_assignment ', bbox)
        iou_val = bb_intersection_over_union(bbox, self.boxes[-1])
        # print('iou_val ', iou_val)
        if (iou_val == 1):
            # print('same')
            return False
        if (iou_val >= self.tresh):
            # self.append(bbox)
            # print('appended! ', iou_val)
            return True
        return False

    def track_assignment_by_distance(self, bbox, dist_tresh=50):
        '''decides if getting bbox fit to the track, 
        using distanse algorythm, appends if yes'''
        last_bbox_center = self.bbox_center(self.boxes[-1])
        distance = self.distance_calc(last_bbox_center, bbox)
        print(f'distance- {distance}')
        if distance <= dist_tresh:
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

    def draw_tracks(self, frm):
        '''draw tracks points and lines'''
        if len(self.points) > 2:  # если в треке достаточно точек для рисования
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
