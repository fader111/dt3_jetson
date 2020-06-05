''' Alt Sh F - win; Ctrl Sh D - lin'''
from shapely.geometry import Point, Polygon, box
import math

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

    def __init__(self, path, directions=[0, 0, 0, 0], h=600):
        ''' initiate polygones when they changes on server 
            path = [[x,y],[x,y],[x,y],[x,y]]
            directions = [0,0,0,0] 0 - direction dont set, 1 - set
        '''
        self.path = path
        self.h = h  # frame height in web
        self.directions = directions
        self.shapely_path = Polygon(path)
        self.center = self.center_calc(path)
        self.arrows_path = self.arrows_path_calc(path, h)
        self.area = round(self.shapely_path.area)

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
