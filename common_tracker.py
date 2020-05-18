''' tools for tracker '''
import numpy as np
import math

blue = (255, 0, 0)  # BGR format
green = (0, 255, 0)
red = (0, 0, 255)
purple = (255, 0, 255)

CLASSES = {6:"bus", 3:"car", 8:"truck", 4:"motorcicle"}

CLASSES_EXTENDED = {6:"bus", 3:"car", 8:"truck", 4:"motorcicle", 1:"person", 76:"keyboard", 
           7:"train", 10:"traffic light", 12:"street sign", 13:"stop sign", 14:"parking meter"}


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
