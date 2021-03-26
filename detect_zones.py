''' Ramka - class for detect zones'''

from collections import OrderedDict
from typing import List, Union, Tuple

from colors import Colors, colors_to_bgr_map
from vehicle_types import VehicleTypes

import time
# import threading
from shapely.geometry import Point, Polygon, box
import math
import numpy as np
import cv2
# from common_tracker import setInterval

blue = (255, 0, 0)  # BGR format
green = (0, 255, 0)
red = (0, 0, 255)
purple = (255, 0, 255)

"""
    What this class can do?
        - we have some coordinates of Ramka
        - coordinates discribe points on a plane
        - polygon may not be convex (ie may be concave)
        - Ramka can be activated or not
        - Ramka has color
        - if activated Ramka can change color
        - Ramka can have size (in real values (meters etc))
    Q:
        - do we need to use shapely for geometry?
        - which transformations do we apply?
        - which methods do we use for activation of ramka
        - what about time counting?
    TODO:
        - restrict to use black color for mask     
"""
class BasicRamka:
    """
        We must syncronize np.path and shapely_path
    """
    path_type = Union[np.ndarray, List[List[int]]]

    def __init__(self, path: path_type, threshold: float, default_color:Colors=Colors.BLACK):
        self.path = path

        self.shapely_center = Point(0., 0.)
        self.np_center = np.asarray(self.shapely_center, dtype=np.int)
        self.__center_changed = True

        self.__area = 0.
        self.__area_changed = True

        self.activated = False

        self.threshold = float(threshold)

        self.__color = None
        self.default_color = default_color
        self.set_color(default_color)

    def __assert_path(self):
        # check if path closed and convert it to open
        if (self.__path[0] == self.__path[-1]).all():
            self.__path = self.__path[:-1]

        # check that we working with planar paths
        if self.__path.shape[-1] != 2 and self.__path.shape[0] < 3:
            raise Exception(f'class {self.__class__.__name__} can work only with planar paths')

        # check if path type is int
        if not np.issubdtype(self.__path.dtype, np.integer):
            raise Exception(f"{self.__class__.__name__} can't work with non-integer paths")

        # check that all points are not on the same line
        # determinant = np.hstack((np.ones((self.__path.shape[0],1), dtype=np.int), self.__path))
        # if np.linalg.det(determinant) == 0.:
        #     raise Exception(f"{self.__class__.__name__} all path points can't lay on a line")

        # TODO check if path is not self-interacting

    def __get_indexes_in_frame(self):
        if self.path.shape[0] != 4:
            raise NotImplementedError("Can get indexes only for parallelogramms")

        minx, miny, maxx, maxy = tuple(map(int, self.shapely_path.bounds))
        all_possible_coords = np.mgrid[minx:maxx + 1, miny:maxy + 1].reshape(2, -1).T

        p_points = np.repeat(all_possible_coords, 8, axis=0)
        qi_points = np.repeat(self.path, 2, axis=0)
        qi_points = np.append(qi_points[1:], [qi_points[0]], axis=0)
        qi_points = np.tile(qi_points, (all_possible_coords.shape[0], 1))
        determinants_matrices = np.reshape(p_points - qi_points, (-1, 4, 2, 2))
        determinants = np.linalg.det(determinants_matrices)

        mask = (np.sum(determinants >= 0, axis=1) == 4) | (np.sum(determinants <= 0, axis=1) == 4)
        self.pixel_indices_inside_path = all_possible_coords[mask]

    @property
    def path(self) -> np.ndarray:
        return self.__path

    @path.setter
    def path(self, path: path_type) -> None:
        self.__path = np.array(path)
        self.__assert_path()

        self.shapely_path = Polygon(path)
        self.__center_changed = True
        self.__area_changed = True
        self.__get_indexes_in_frame()

    @property
    def center(self) -> np.ndarray:
        if self.__center_changed:
            # using poly centroid as figure center that is not accurate in some concave cases
            self.shapely_center = self.shapely_path.centroid
            self.np_center = np.asarray(self.shapely_center, dtype=np.int)
            self.__center_changed = False

        return self.np_center

    @property
    def area(self) -> float:
        if self.__area_changed:
            self.__area = self.shapely_path.area
            self.__area_changed = False
        return  self.__area

    @property
    def color(self) -> Colors:
        return self.__color

    @color.setter
    def color(self, color: Colors):
        self.__color = color

    def get_bgr_color(self) -> Tuple[int, int, int]:
        return colors_to_bgr_map[self.__color]

    def activate(self):
        self.activated = True

    def deactivate(self):
        self.activated = False

    def is_activated(self):
        return self.activated

    def set_color(self, color:Colors):
        self.__color = color

    # debug function to draw paths in opencv
    def draw_path(self):
        """
            TODO
            size -> size of window may be None
        """
        pass

    # deprecated
    def center_calc(self):
        '''
            calc center of path to put zone number there
            available only for 4 sides poly
        '''
        if not self.path.shape[0] != 4:
            raise Exception("can't use this method to calculate center of polygon with more or less than 4 sides")

        x1 = self.path[0][0]
        y1 = self.path[0][1]
        x2 = self.path[1][0]
        y2 = self.path[1][1]
        x3 = self.path[2][0]
        y3 = self.path[2][1]
        x4 = self.path[3][0]
        y4 = self.path[3][1]

        x12 = (x1 + x2) / 2
        x34 = (x3 + x4) / 2
        y23 = (y2 + y3) / 2
        y41 = (y4 + y1) / 2

        return round((x12+x34)/2), round((y23+y41)/2)

class PedestrianRamka(BasicRamka):
    pass

"""
    - VehicleRamka can have directions
    - if activated VehicleRamka can have some class in it
"""
class VehicleRamka(BasicRamka):
    '''has path, color, shapely state fields'''
    # need to delete state = 0               # state of polygon On/Off
    # arrows graphical path of this polygon.[[[x,y],[x,y],[x,y]], [..], [..]]]
    arrows = []
    ramki_directions = []
    types = {"13": 0, "2": 0, "1": 0} # vehicle types

    # TODO remove h from api
    def __init__(
            self, path, warp_dimentions_px, calib_area_dimentions_m, M, colors_to_vehicles_types_map, threshold,
            directions=None, h=600
    ):
        ''' initiate polygones when they changes on server 
            path = [[x,y],[x,y],[x,y],[x,y]],
            warp_dimentions_px,                 # width, height Top view of calibration zone
            calib_area_dimentions_m,            # width, height of calibration zone in meter
            M,                                  # transition matrix
            directions = [0,0,0,0],             # 0 - direction dont set, 1 - set
            h                                   # process window height
        '''
        super().__init__(path, threshold)
        self.colors_to_vehicles_types_map = colors_to_vehicles_types_map
        self.vehicles_types_to_colors = {v: k for k,v in self.colors_to_vehicles_types_map.items()}

        # self.path -> np path
        # self.shapely_path -> shapely path
        # self.center -> np center
        # self.area -> float

        # TODO remove h
        # self.h = h  # frame height in web
        if directions is None:
            self.directions = [False] * 4
        else:
            self.directions = list(map(bool, directions))

        self.__triggered = False        # trigger for time in ramka measurement process
        self.__start_time = None
        self.__masks = None
        self.bbox = tuple(map(int, self.shapely_path.bounds))

        # status dictionary for avg speed intensity and others
        self.status = {
            'avg_speed_1': [],      # last minute avg speed, appends by each track

            'avg_speed_15': 0,      # average speed measured by sliding window 15 min interval
            'avg_speed_60': 0,      # same for 60 min interval
            'speeds_60': [],        # average speed samples during 1 hour (60 items)
            
            'avg_intens_15': 0,     # average intensity for 15 min interval 
            'avg_intens_60': 0,     # average intensity for 60 min interval 
            'intenses_60': [],      # intensity for 60 min sliding window interval (60 items)

            'avg_intens_1_tp': {"13": [], "2": [], "1": []},        # average intensity by types for 1 min interval
            'avg_intens_15_tp': {"13": 0, "2": 0, "1": 0},          # average intensity by types for 15 min interval
            'avg_intens_60_tp': {"13": 0, "2": 0, "1": 0},          # average intensity by types for 60 min interval
            'intenses_60_tp': {"13": [], "2": [], "1": []},         # intensity by types for 60 min interval (60 items)

            'cur_time_in_zone': 0,           # how much time car stays in detection zone, duration in sec
            'times_in_zone_1': [],           # cur_time_in_zone values array of 1 minute
            'times_in_zone_60': [],          # mass with times in 60 min for sliding window
            'avg_time_in_zone_15': 0,        # average average time in zone during 15 min (15 items)
            'avg_time_in_zone_60': 0         # average average time in zone during 1 hour (60 items)
        }

        self.arrows_path = self.arrows_path_calc(path, h)       # for dt
        self.up_down_side_center_calc()     # for dt
        self.warped_width_px, self.warped_height_px = warp_dimentions_px
        self.calib_area_width_m, self.calib_area_length_m = calib_area_dimentions_m
        # центр верхнего края рамки в формате нужном для трансформации в Top View
        self.up_side_center_np = np.array(
            [(self.up_side_center, self.up_side_center, self.up_side_center)], dtype=np.float32)
        # центр нижнего края рамки в формате нужном для трансформации в Top View
        self.down_side_center_np = np.array(
            [(self.down_side_center, self.down_side_center, self.down_side_center)], dtype=np.float32)

        # центр верхнего края рамки в Top View
        self.up_side_center_warped = cv2.perspectiveTransform(
            self.up_side_center_np, M)[0][0]
        # центр нижнего края рамки в Top View
        self.down_side_center_warped = cv2.perspectiveTransform(
            self.down_side_center_np, M)[0][0]

        # верхняя граница рамки в метрах от дальнего края калибровочного полигона
        self.up_limit_y_m = self.up_side_center_warped[1] / \
            self.warped_height_px * self.calib_area_length_m
        # нижняя граница от края ....
        self.down_limit_y_m = self.down_side_center_warped[1] / \
            self.warped_height_px * self.calib_area_length_m

        '''
        # moved to the main_proc
        @setInterval(20) # each {arg} seconds runs  self.sliding_wind for update zone status 
        def function():
            self.sliding_wind()
        # start new thread for average speed calculating
        self.stop = function() # self.stop is threading.Event object
        '''

    def __get_masks_simple(self):
        minx, miny, maxx, maxy = self.bbox
        self.__masks = {color: np.zeros((maxy-miny+1, maxx-minx+1, 3)) for color in self.colors_to_vehicles_types_map}
        indices = self.pixel_indices_inside_path - np.repeat([[minx,miny]], self.pixel_indices_inside_path.shape[0], axis=0)
        for color, mask in self.__masks.items():
            mask[tuple(indices.T[[1, 0]].tolist())] = colors_to_bgr_map[color]

    def __get_masks_with_color_sum(self):
        minx, miny, maxx, maxy = self.bbox
        self.__masks = {color: {'mask': np.zeros((maxy - miny + 1, maxx - minx + 1, 3), dtype=np.uint8), 'pixel_sum': 0} for color in
                        self.colors_to_vehicles_types_map}
        indices = self.pixel_indices_inside_path - np.repeat([[minx, miny]], self.pixel_indices_inside_path.shape[0],
                                                             axis=0)
        for color, aux_dict in self.__masks.items():
            aux_dict['mask'][tuple(indices.T[[1, 0]].tolist())] = colors_to_bgr_map[color]
            aux_dict['pixel_sum'] = sum(colors_to_bgr_map[color])

    def __get_white_masks(self):
        minx, miny, maxx, maxy = self.bbox
        indices = self.pixel_indices_inside_path - np.repeat([[minx, miny]], self.pixel_indices_inside_path.shape[0],
                                                             axis=0)
        indices_for_ndarray = tuple(indices.T[[1, 0]].tolist())

        self.__white_mask = np.zeros((maxy - miny + 1, maxx - minx + 1, 3), dtype=np.uint8)
        self.__white_mask[indices_for_ndarray] = colors_to_bgr_map[Colors.WHITE]

        self.__masks = {color: np.full((maxy-miny+1, maxx-minx+1, 3), colors_to_bgr_map[Colors.WHITE], dtype=np.uint8)
                        for color in self.colors_to_vehicles_types_map}
        for color in self.__masks:
            self.__masks[color][indices_for_ndarray] = colors_to_bgr_map[color]

    def __get_masks(self):
        self.__get_white_masks()
        # self.__get_masks_with_color_sum()

    def triggered(self) -> bool:
        return self.__triggered

    def activate(self, vehicle_type: VehicleTypes):
        if self.is_activated() and self.vehicle_type is vehicle_type:
            return

        super().activate()
        self.vehicle_type = vehicle_type
        color = self.vehicles_types_to_colors[vehicle_type]
        self.set_color(color)

    def deactivate(self):
        super().deactivate()
        self.vehicle_type = None
        self.set_color(self.default_color)

    def start_time_measuremnet(self):
        self.__start_time = time.time()
        self.__triggered = True

    def stop_time_measurement(self):
        overall_time = time.time() - self.__start_time
        self.status['cur_time_in_zone'] = overall_time
        self.status['times_in_zone_1'].append(overall_time)

        self.__triggered = False
        self.__start_time = None

    def __segmentation_recognize_white_masks(self, image:np.ndarray):
        if not self.__masks:
            self.__get_masks()

        minx, miny, maxx, maxy = self.bbox
        roi = image[miny:maxy + 1, minx:maxx + 1]
        masked_roi = cv2.bitwise_and(roi, self.__white_mask)
        colors_to_percent = {}
        for color, mask in self.__masks.items():
            result1 = masked_roi - mask
            result2 = np.logical_or.reduce(result1, axis=-1)
            result3 = np.count_nonzero(result2)
            correct_pixels_num = masked_roi.shape[0]*masked_roi.shape[1] - np.count_nonzero(np.logical_or.reduce(masked_roi - mask, axis=-1))
            colors_to_percent[color] = correct_pixels_num / self.pixel_indices_inside_path.shape[0]
        colors_to_persent = OrderedDict(sorted(colors_to_percent.items(), key=lambda item: item[1], reverse=True))
        first_color, first_percent = colors_to_persent.popitem(last=False)
        if first_percent >= self.threshold:
            self.activate(self.colors_to_vehicles_types_map[first_color])
        else:
            self.deactivate()


    def __segmentation_recognize(self, image: np.ndarray):
        # create masks if not before
        if not self.__masks:
            self.__get_masks()

        minx, miny, maxx, maxy = self.bbox
        roi = image[miny:maxy + 1, minx:maxx + 1]
        colors_to_persent = {}
        for color, aux_dict in self.__masks.items():
            mask, pixel_sum = aux_dict['mask'], aux_dict['pixel_sum']
            try:
                masked_roi = cv2.bitwise_and(roi, mask)
            except:
                # TODO error raises here periodically
                print('bad')
            # if color is Colors.RED:
            #     cv2.imshow('roi', roi)
            #     cv2.imshow('mask', mask)
            #     cv2.imshow('result', masked_roi)
            #     cv2.waitKey(500)
            pixel_sum_array = np.sum(masked_roi, axis=-1)
            correct_pixels_num = np.count_nonzero(pixel_sum_array == pixel_sum)
            colors_to_persent[color] = correct_pixels_num / self.pixel_indices_inside_path.shape[0]
        colors_to_persent = OrderedDict(sorted(colors_to_persent.items(), key=lambda item: item[1], reverse=True))
        first_color, first_percent = colors_to_persent.popitem(last=False)
        if first_percent >= self.threshold:
            self.activate(self.colors_to_vehicles_types_map[first_color])
        else:
            self.deactivate()


    def segmentation_recognize(self, image: np.ndarray):
        self.__segmentation_recognize_white_masks(image)
        #self.__segmentation_recognize(image)
        # if not self.__masks:
        #     self.__get_masks()
        #
        # minx, miny, maxx, maxy = self.bbox
        # roi = image[miny:maxy+1, minx:maxx+1]
        # colors_to_percent_map = {color: np.count_nonzero(np.logical_and.reduce(roi == mask)) / self.pixel_indices_inside_path.shape[0] for color, mask in
        #                                 self.__masks.items()}
        # colors_to_percent_tuple = sorted(tuple(colors_to_percent_map.items()), key=lambda x: x[1], reverse=True)
        # if colors_to_percent_tuple[0][1] >= self.threshold:
        #     self.activate(self.colors_to_vehicles_types_map[colors_to_percent_tuple[0][0]])
        # else:
        #     self.deactivate()

        # image = np.copy(image)
        # if not self.__masks or ((self.current_frame['height'], self.current_frame['width']) != image.shape[:2]):
        #     self.__get_masks(image.shape[1], image.shape[0])

        # minx, miny, maxx, maxy = self.shapely_path.bounds
        # result = [image[miny:maxy+1, minx:maxx+1] == mask for mask in self.__masks.values()]

        # colors_to_pixels_num_map = {color: np.count_nonzero(np.logical_and.reduce(image == mask)) for color, mask in self.__masks.items()}
        # colors_to_percent_tuple = sorted(tuple(colors_to_pixels_num_map.items()), key=lambda x: x[1], reverse=True)
        # if colors_to_percent_tuple[0][1] >= self.threshold:
        #     self.activate(self.colors_to_vehicles_types_map[colors_to_percent_tuple[0][0]])
        # else:
        #     self.deactivate()

        # roi = mask[tuple(self.pixel_indices_inside_path.T[[1, 0]].tolist())]
        # roi = np.reshape(roi, (-1, 3))
        # pixels_num = roi.shape[0]
        # colors_to_percent_map = {}
        # interesting_colors_to_bgr_map = {k:colors_to_bgr_map[k] for k in self.colors_to_vehicles_types_map}
        # for color_name, color_tuple in interesting_colors_to_bgr_map.items():
        #     color_tuple = np.repeat(np.array([color_tuple]), roi.shape[0], axis=0)
        #     colors_to_percent_map[color_name] = np.count_nonzero(np.logical_and.reduce(roi == color_tuple, axis=1)) / pixels_num
        # colors_to_percent_tuple = sorted(tuple(colors_to_percent_map.items()), key=lambda x: x[1], reverse=True)
        # if colors_to_percent_tuple[0][1] >= self.threshold:
        #     self.activate(self.colors_to_vehicles_types_map[colors_to_percent_tuple[0][0]])
        # else:
        #     self.deactivate()

    def up_down_side_center_calc(self):
        """
            calc zone up side center point. Its y coord use for speed calc
            coords in pixels on the perspective view
        """
        p1, p2, p3, p4 = self.path
        self.up_side_center = (p1[0]+p2[0])//2, (p1[1]+p2[1])//2
        self.down_side_center = (p3[0]+p4[0])//2, (p3[1]+p4[1])//2

    def arrows_path_calc(self, path, h):
        ''' gets argument - polygon path as [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
            returns arrows as  [[[x,y],[x,y],[x,y]],  [..],[..],[..]]]'''
        arrowsPath_ = [[[0, 0], [0, 0], [0, 0]], [[0, 0], [0, 0], [0, 0]], [
            [0, 0], [0, 0], [0, 0]], [[0, 0], [0, 0], [0, 0]]]
        for i in range(4):  # for each kernel of polygon
            # // координата x 1 угла стрелки совпадает с x первого угла полигона
            x1 = arrowsPath_[i][0][0] = path[i][0]
            y1 = arrowsPath_[i][0][1] = path[i][1]   # // то-же для y
            # // для третьего угла полигона второй угол рамки будет нулевой угол полигона
            if (i < 3):
                # // координата x 2 угла стрелки совпадает с x второго угла полигона
                x2 = arrowsPath_[i][1][0] = path[i + 1][0]
                y2 = arrowsPath_[i][1][1] = path[i + 1][1]   # // то-же для y
            else:
                x2 = arrowsPath_[i][1][0] = path[0][0]
                y2 = arrowsPath_[i][1][1] = path[0][1]
            # // найдем стороны прямоугольного треугольника - половинки основания стрелки
            # //первый катет
            a = math.sqrt((x2-x1)*(x2-x1)+(y1-y2)*(y1-y2)) / 2
            # //второй катет просто задается как половина первого
            b = a / 2
            if (b > h / 20):
                # // чтоб стрелка не сильно выпирала на больших полигонах
                b = h / 20
            с = math.sqrt(a*a+b*b)                              # //гипотенуза
            if x2 != x1:
                ''' prevent division by zero'''
                alfa = math.atan(
                    (y1-y2)/(x2-x1))               # //угол поворота основания стрелки к горизонту в радианах
            else:
                alfa = math.pi/2
            # // вспомогательные величины смещения по X
            shiftX = round((math.cos(alfa+math.asin(b/с)))*с)
            # // вспомогательные величины смещения по Y
            shiftY = round((math.sin(alfa+math.asin(b/с)))*с)
            if (i != 2):
                # // координата x 3 угла стрелки
                x3 = arrowsPath_[i][2][0] = shiftX+x1
                y3 = arrowsPath_[i][2][1] = -shiftY+y1
            else:
                x3 = arrowsPath_[i][2][0] = -shiftX + x1
                y3 = arrowsPath_[i][2][1] = shiftY + y1
            # // координата y 3 угла стрелки
            if ((i == 3) | (i == 1)):
                if (x1 > x2):
                    x3 = arrowsPath_[i][2][0] = -shiftX+x1
                    y3 = arrowsPath_[i][2][1] = shiftY+y1
            # print(f'i{i} x3y3 {x3, y3}')
        return arrowsPath_

    def sliding_wind(self):
        ''' sliding window for calculating detector ctatus starts each 1 minute 
            calls from calculating process '''
        
        ### Average speed calculating section ###
        
        # добавляем в минутный список сред скорость каждого трека
        # print("                                                   self.status['avg_speed_1']", self.status['avg_speed_1'])
        # вычисляем среднюю скорость за последнюю минуту
        if len(self.status['avg_speed_1']) != 0:
            minute_avg_speed = sum(
                self.status['avg_speed_1'])/len(self.status['avg_speed_1'])
            # добавляем ее в часовой массив скоростей, но только если это не 0.
            self.status['speeds_60'].append(minute_avg_speed)
        else:
            minute_avg_speed = 0
        
        # удаляем первое значение из часового массива скоростей, если там больше 60-ти значений
        if len(self.status['speeds_60']) > 60:
            self.status['speeds_60'].pop(0)

        # вычисляем среднюю скорость за час
        if len(self.status['speeds_60']) != 0:
            self.status['avg_speed_60'] = int(sum(
                self.status['speeds_60'])/len(self.status['speeds_60']))
        else:
            self.status['avg_speed_60'] = 0

        # если в массиве часовых скоростей <=15 значений, то средняяя скорость за час
        # равна средней скорости за последние 15 минут
        if len(self.status['speeds_60']) <= 15:
            self.status['avg_speed_15'] = self.status['avg_speed_60']
        # если больше 15 значений, то берем срез последних 15-ти из часового массива и по 
        # нему считаем среднюю скорость за последние 15 минут
        else:
            self.status['avg_speed_15'] = int(sum(
                self.status['speeds_60'][-15:])/len(self.status['speeds_60'][-15:]))

        
        ### Intensity calculating section ###
        
        # количество машин в минуту делим на 60 получаем машин в час.
        # в intense_60 добавляем число машин в час.
        n_cars_60 = len(self.status['avg_speed_1'])*60
        # каждую минуту добавляем в status['intenses_60'] это количество
        self.status['intenses_60'].append(n_cars_60)
        # если значений там больше 60, удаляем первое
        if len(self.status['intenses_60']) > 60:
            self.status['intenses_60'].pop(0)
        # вычисляем среднюю интенсвность в час 
        if len(self.status['intenses_60']):
            self.status['avg_intens_60'] = int(sum(
                self.status['intenses_60'])/len(self.status['intenses_60']))
        else:
            self.status['avg_intens_60'] = 0

        # если в массиве часовых интенсивностей <=15 значений, то средняяя интенсивность за час
        # равна средней интенсивности за последние 15 минут
        if len(self.status['intenses_60']) <= 15:
            self.status['avg_intens_15'] = self.status['avg_intens_60']
        # если больше 15 значений, то берем срез последних 15-ти из часового массива и по 
        # нему считаем среднюю интенсивность за последние 15 минут
        else:
            self.status['avg_intens_15'] = int(sum(
                self.status['intenses_60'][-15:])/len(self.status['intenses_60'][-15:]))


        ### Intense by vehicle types calculating section ###
        
        # тип тс из трека надо сунуть в рамку. 
        # потом посчитать в рамке количество каждого типа в минуту по аналогии с интенсивностью
        # все так-же только в цикле по ключам - которые есть типы тс
        for key in self.types:
            n_cars_60_tp =  len(self.status['avg_intens_1_tp'][key])*60
            self.status['intenses_60_tp'][key].append(n_cars_60_tp)

            if len(self.status['intenses_60_tp'][key]) > 60:
                self.status['intenses_60_tp'][key].pop(0)

            if len(self.status['intenses_60_tp'][key]):
                self.status['avg_intens_60_tp'][key] = int(sum(
                    self.status['intenses_60_tp'][key])/len(self.status['intenses_60_tp'][key]))
            else:
                self.status['avg_intens_60_tp'][key] = 0
            
            if len(self.status['intenses_60_tp'][key]) <= 15:
                self.status['avg_intens_15_tp'][key] = self.status['avg_intens_60_tp'][key]
            else:
                self.status['avg_intens_15_tp'][key] = int(sum(
                    self.status['intenses_60_tp'][key][-15:])/len(self.status['intenses_60_tp'][key][-15:]))            
            
            # обнуляем минутный массив
            self.status['avg_intens_1_tp'][key] = []

        ### Average time in zone calculating section ###

        # вычисляем среднее время нахождения в зоне за последнюю минуту
        if len(self.status['times_in_zone_1']) != 0:
            minute_avg_time_in_zone = sum(
                self.status['times_in_zone_1'])/len(self.status['times_in_zone_1'])
            # добавляем ее в часовой массив времени, но только если это не 0.
            self.status['times_in_zone_60'].append(minute_avg_time_in_zone)
        else:
            minute_avg_time_in_zone = 0

        # удаляем первое значение из часового массива времен в зоне, 
        # если там больше 60-ти значений
        if len(self.status['times_in_zone_60']) > 60:
            self.status['times_in_zone_60'].pop(0)
        # вычисляем среднее время в зоне за час
        if len(self.status['times_in_zone_60']) != 0:
            self.status['avg_time_in_zone_60'] = round((sum(
                self.status['times_in_zone_60'])/len(self.status['times_in_zone_60'])), 1)
        else:
            self.status['avg_time_in_zone_60'] = 0

        # если в массиве часовых времен в зоне <= 15 значений, то среднее время в зоне за час
        # равна среднему времени в зоне за последние 15 минут
        if len(self.status['times_in_zone_60']) <= 15:
            self.status['avg_time_in_zone_15'] = self.status['avg_time_in_zone_60']
        # если больше 15 значений, то берем срез последних 15-ти из часового массива и по 
        # нему считаем среднее время в зоне за последние 15 минут
        else:
            self.status['avg_time_in_zone_15'] = round((sum(
                self.status['times_in_zone_60'][-15:])/len(self.status['times_in_zone_60'][-15:])), 1)
        

            ### END ###
    
        # обнуляем массив скоростей за минуту
        self.status['avg_speed_1'] = []
        # print(
            # "                                                   self.status['avg_speed_15']", self.status['avg_speed_15'])

if __name__ == '__main__':
    # check List, ndarray paths
    # check integer only
    # check closed, unclosed paths
    good_paths = [
        [[0, 0], [5, 30], [35, 33], [40, 10]],
        np.array([[0, 1], [2,3], [4, 5]])
    ]
    bad_paths = [
        [[0, 0], [1, 1], [2, 2.]],
        [[0., 0.], [1., 1.], [2, 2.]]
    ]

    for path in good_paths:
        ramka = BasicRamka(path)
    for path in bad_paths:
        try:
            ramka = BasicRamka(path)
        except Exception:
            pass
        else:
            raise Exception("assertion failed")

    # print (ramka.area, ramka.center)