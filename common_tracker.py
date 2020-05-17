''' tools for tracker '''
import numpy as np
import math

blue = (255, 0, 0)  # BGR format
green = (0, 255, 0)
red = (0, 0, 255)
purple = (255, 0, 255)

CLASSES = {6:"bus", 3:"car", 8:"truck", 4:"motorcicle", 1:"person", 76:"keyboard", 
           7:"train", 10:"traffic light", 12:"street sign", 13:"stop sign", 14:"parking meter"}

def arrows_path(path, h):
    ''' gives 1 argument - polygon path as [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
        returns arrows as  [[[x,y],[x,y],[x,y]],  [..],[..],[..]]]'''
    arrowsPath= [[[0,0],[0,0],[0,0]],[[0,0],[0,0],[0,0]],[[0,0],[0,0],[0,0]],[[0,0],[0,0],[0,0]]]
    for i in range(4): # for each kernel of polygon
        x1 = arrowsPath[i][0][0] = path[i][0]   # // координата x 1 угла стрелки совпадает с x первого угла полигона
        y1 = arrowsPath[i][0][1] = path[i][1]   # // то-же для y
        if (i<3):                               # // для третьего угла полигона второй угол рамки будет нулевой угол полигона
            x2 = arrowsPath[i][1][0] = path[i + 1][0]   # // координата x 2 угла стрелки совпадает с x второго угла полигона
            y2 = arrowsPath[i][1][1] = path[i + 1][1]   # // то-же для y
        else:
            x2 = arrowsPath[i][1][0] = path[0][0]
            y2 = arrowsPath[i][1][1] = path[0][1]
        # // найдем стороны прямоугольного треугольника - половинки основания стрелки
        a = math.sqrt((x2-x1)*(x2-x1)+(y1-y2)*(y1-y2))/2    # //первый катет
        b=a/2                                               # //второй катет просто задается как половина первого
        if (b>h/20):
            b = h//20                                       # // чтоб стрелка не сильно выпирала на больших полигонах
        с = math.sqrt(a*a+b*b)                              # //гипотенуза
        if x2!=x1:                         
            ''' prevent division by zero'''
            alfa = math.atan((y1-y2)/(x2-x1))               # //угол поворота основания стрелки к горизонту в радианах
        else:
            alfa = math.pi/2
        shiftX = round((math.cos(alfa+math.asin(b/с)))*с)   # // вспомогательные величины смещения по X
        shiftY = round((math.sin(alfa+math.asin(b/с)))*с)   # // вспомогательные величины смещения по Y
        if (i!=2):
            x3 = arrowsPath[i][2][0] = shiftX+x1            # // координата x 3 угла стрелки
            y3 = arrowsPath[i][2][1] = -shiftY+y1
        else:
            x3 = arrowsPath[i][2][0] = -shiftX + x1
            y3 = arrowsPath[i][2][1] = shiftY + y1
        # // координата y 3 угла стрелки
        if ((i==3)|(i==1)):
            if (x1>x2):
                x3 = arrowsPath[i][2][0] = -shiftX+x1
                y3 = arrowsPath[i][2][1] = shiftY+y1
        # print(f'i{i} x3y3 {x3, y3}')
    return arrowsPath


def gamma(image, gamma=0.4):
    '''makes gamma coorection'''
    img_float = np.float32(image)
    max_pixel = np.max(img_float)
    img_normalized = img_float/max_pixel
    gamma_corr = np.log(img_normalized) * gamma
    gamma_corrected = np.exp(gamma_corr)*255.0
    gamma_corrected = np.uint8(gamma_corrected)
    return gamma_corrected


def bbox_touch_the_border(bbox, height, width, bord_lim=10):
    ''' check if bbox touches the frame border'''
    x1 = bbox[0]
    y1 = bbox[1]
    x2 = bbox[2]
    y2 = bbox[3]
    if (x1 < bord_lim) | (height - y2 < bord_lim) |\
       (y1 < bord_lim) | (width - x2 < bord_lim):
        # wait = input("PRESS ENTER TO CONTINUE.")
        return True
    else:
        return False
