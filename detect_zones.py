''' Ramka - class for detect zones'''
from shapely.geometry import Point, Polygon, box
import math
import numpy as np
import cv2

blue = (255, 0, 0)  # BGR format
green = (0, 255, 0)
red = (0, 0, 255)
purple = (255, 0, 255)


class Ramka:
    '''has path, color, state, shapely state fields'''
    state = 0               # state of polygon On/Off
    # arrows graphical path of this polygon.[[[x,y],[x,y],[x,y]], [..], [..]]]
    arrows = []
    ramki_directions = []
    color = blue

    def __init__(self, path, warp_dimentions_px, calib_area_dimentions_m, M, directions=[0, 0, 0, 0], h=600):
        ''' initiate polygones when they changes on server 
            path = [[x,y],[x,y],[x,y],[x,y]],
            warp_dimentions_px,                 # width, height Top view of calibration zone
            calib_area_dimentions_m,            # width, height of calibration zone in meter
            M,                                  # transition matrix
            directions = [0,0,0,0],             # 0 - direction dont set, 1 - set
            h                                   # process window height
        '''
        self.path = path
        self.h = h  # frame height in web
        self.directions = directions
        self.shapely_path = Polygon(path)
        self.center = self.center_calc(path)
        self.arrows_path = self.arrows_path_calc(path, h)
        self.area = round(self.shapely_path.area)
        self.up_down_side_center_calc()
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

        # посчитаем координаты кружочка в топвью плоскости и отобразим на варпед картинке
        '''top_point_np3D = np.array([((top_point[0], top_point[1]), (
            top_point[0], top_point[1]), (top_point[0], top_point[1]))], dtype=np.float32)
        down_point_np3D = np.array([((down_point[0], down_point[1]), (
            down_point[0], down_point[1]), (down_point[0], down_point[1]))], dtype=np.float32)
        trans_point_top = cv2.perspectiveTransform(top_point_np3D, M)[0][0]
        trans_point_down = cv2.perspectiveTransform(down_point_np3D, M)[0][0]
        '''

    def center_calc(self, path):
        ''' calc center of path to put zone number there
        '''
        x1 = path[0][0]         # polygon coordinates
        y1 = path[0][1]
        x2 = path[1][0]
        y2 = path[1][1]
        x3 = path[2][0]
        y3 = path[2][1]
        x4 = path[3][0]
        y4 = path[3][1]

        x12 = (x1 + x2) / 2     # center projection coordinates
        x23 = (x2 + x3) / 2
        x34 = (x3 + x4) / 2
        x41 = (x4 + x1) / 2
        y12 = (y1 + y2) / 2
        y23 = (y2 + y3) / 2
        y34 = (y3 + y4) / 2
        y41 = (y4 + y1) / 2
        return round((x12+x34)/2), round((y23+y41)/2)
        # return ((x12+x34)/2), ((y23+y41)/2)

    def up_down_side_center_calc(self):
        """ calc zone up side center point. Its y coord use for speed calc
            coords in pixels on the perspective view
        """
        p1, p2, p3, p4 = self.path
        self.up_side_center = (p1[0]+p2[0])//2, (p1[1]+p2[1])//2
        self.down_side_center = (p3[0]+p4[0])//2, (p3[1]+p4[1])//2

    def arrows_path_calc(self, path, h):
        ''' gives 1 argument - polygon path as [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
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
            a = math.sqrt((x2-x1)*(x2-x1)+(y1-y2)*(y1-y2)) / \
                2    # //первый катет
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


'''
test_path = [[0,0], [5,30], [35,33], [40,10]]
ramka = Ramka(test_path)
print (ramka.area, ramka.center )
'''
