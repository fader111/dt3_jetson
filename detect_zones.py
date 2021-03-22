''' Ramka - class for detect zones'''

from typing import List, Union

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
        - if activated Ramka can have some class in it
        - Ramka has color
        - if activated Ramka can change color
        - Ramka can have size (in real values (meters etc))
        
    Q:
        - do we need to use shapely for geometry?
        - which transformations do we apply?
        - which methods do we use for activation of ramka
        - what about time counting?
        
"""
class BasicRamka:
    """
        We must syncronize np.path and shapely_path
    """
    path_type = Union[np.ndarray, List[List[int]]]

    def __init__(self, path: path_type):
        self.path = path

        self.shapely_center = Point(0., 0.)
        self.np_center = np.asarray(self.shapely_center, dtype=np.int)
        self.__center_changed = True

        self.__area = 0.
        self.__area_changed = True

        self.activated = False

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

    def activate(self):
        self.activated = True

    def deactivate(self):
        self.activated = False

    def is_activated(self):
        return self.activated

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
"""
class VehicleRamka(BasicRamka):
    '''has path, color, shapely state fields'''
    # need to delete state = 0               # state of polygon On/Off
    # arrows graphical path of this polygon.[[[x,y],[x,y],[x,y]], [..], [..]]]
    arrows = []
    ramki_directions = []
    color = blue
    types = {"13": 0, "2": 0, "1": 0} # vehicle types

    # TODO remove h from api
    def __init__(self, path, warp_dimentions_px, calib_area_dimentions_m, M, directions=None, h=600):
        ''' initiate polygones when they changes on server 
            path = [[x,y],[x,y],[x,y],[x,y]],
            warp_dimentions_px,                 # width, height Top view of calibration zone
            calib_area_dimentions_m,            # width, height of calibration zone in meter
            M,                                  # transition matrix
            directions = [0,0,0,0],             # 0 - direction dont set, 1 - set
            h                                   # process window height
        '''
        super().__init__(path)
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

        self.__triggered = False        # trigger for time in ramka measurement process
        self.__start_time = None

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

    def triggered(self) -> bool:
        return self.__triggered

    def start_time_measuremnet(self):
        self.__start_time = time.time()
        self.__triggered = True

    def stop_time_measurement(self):
        overall_time = time.time() - self.__start_time
        self.status['cur_time_in_zone'] = overall_time
        self.status['times_in_zone_1'].append(overall_time)

        self.__triggered = False
        self.__start_time = None

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