#!/usr/bin/env python

'''
car detection using haar cascades

USAGE:
    facedetect.py [--cascade <cascade_fn>] [--nested-cascade <cascade_fn>] [<video_source>]
'''

# Python 2/3 compatibility
from __future__ import print_function

import numpy as np
import cv2 as cv

# local modules
#from video import create_capture
from common import clock, draw_str

vfile_src = "G:/fotovideo/video_src/U524806_6.avi"
vfile_src = "G:/fotovideo/video_src/U524802_14.avi"
vfile_src = "G:/fotovideo/video_src/U524802_15.avi"
#vfile_src = "G:/fotovideo/video_src/U524802_16.avi"
vfile_src = "G:/fotovideo/video_src/U524806_3.avi"
#vfile_src = "G:/fotovideo/video_src/sunny.avi"

USE_GAMMA = False

def detect(img, cascade):
    # rects = cascade.detectMultiScale(img, scaleFactor=1.7, minNeighbors=9, minSize=(30, 30),flags=cv.CASCADE_SCALE_IMAGE)
    # rects = cascade.detectMultiScale(img, scaleFactor=1.03, minNeighbors=7, minSize=(30, 30),flags=cv.CASCADE_SCALE_IMAGE)
    rects = cascade.detectMultiScale(img, scaleFactor=1.5, minNeighbors=7, minSize=(50, 50),flags=cv.CASCADE_SCALE_IMAGE)
    if len(rects) == 0:
        return []
    rects[:,2:] += rects[:,:2]
    return rects

def square_calc(x1,y1,x2,y2):
	return (x2-x1)*(y2-y1)

		
def square_overlap(rect1, rect2):
    """ возвращает площадь прямоугольника перекрытия"""
    #print('rect1 ', rect1)
    x11,y11,x21,y21 = rect1
    x12,y12,x22,y22 = rect2
    x1=max(x11,x12)
    y1=max(y11,y12)
    x2=min(x21,x22)
    y2=min(y21,y22)
    sq_rect = square_calc(x1,y2,x2,y2)
    sq_rect1 = square_calc(rect1)
    sq_rect2 = square_calc(rect2)
    if sq_rect1<=sq_rect2:
        return sq_rect
    else: 
        return -sq-rect

def gamma(image,gamma = 0.5):
    img_float = np.float32(image)
    max_pixel = np.max(img_float)
    #image pixel normalisation
    img_normalised = img_float/max_pixel
    #gamma correction exponent calulated
    gamma_corr = np.log(img_normalised)*gamma
    #gamma correction being applied
    gamma_corrected = np.exp(gamma_corr)*255.0
    #conversion to unsigned int 8 bit
    gamma_corrected = np.uint8(gamma_corrected)
    return gamma_corrected

def draw_rects(img, rects, color):
    # print('\n\n ', )
    # print('rects ', rects)
    for x1, y1, x2, y2 in rects:
        #square = square_calc(x1, y1, x2, y2)	
        #print('square ',square )
        #print('x1, y1, x2, y2 ',x1, y1, x2, y2, '   ', square)
        cv.rectangle(img, (x1, y1), (x2, y2), color, 2)

def remove_bad_rects(rects):
    """удаляет лишние полигоны"""
	# ищем один полигон внутри другого и больший удаляем, внутренний оставляем
    for i, rect in enumerate (rects):
        for j in len(rects):
            sq = square_overlap(rect, rects[j]) # получаем площадь зоны перекрытия текущего прямоугольника в каждым
			# далее надо написать удалялку. но лень
        	
			
if __name__ == '__main__':
    import sys, getopt
    print(__doc__)

    args, video_src = getopt.getopt(sys.argv[1:], '', ['cascade=', 'nested-cascade='])
    try:
        video_src = video_src[1]
    except:
        video_src = 1
    args = dict(args)
    print('args ', args)
    #cascade_fn = args.get('--cascade', "data/haarcascades/cas3.xml")
    #cascade_fn = args.get('--cascade', "cascade10.xml")
    #cascade_fn = args.get('--cascade', "cascadeLBP.xml")
    #cascade_fn = args.get('--cascade', "cascadeLBP16.xml")
    #cascade_fn = args.get('--cascade', "cascade_lbp_w25_h25_p17116_n35275.xml")
    #cascade_fn = args.get('--cascade', "cascadeHaar_w25_h25_p17116_n35275.xml")
    #cascade_fn = args.get('--cascade', "cascadeLBP_w25_h25_p2572_n45259.xml")
	
	# пластины номеров 
    #cascade_fn = args.get('--cascade', "plate_cascade_haar_12.xml")
    
    cascade_fn = args.get('--cascade', "vehicles_cascadeLBP_w25_h25_p2572_n58652_neg_roof.xml")
    #cascade_fn = args.get('--cascade', "night_cascadeLBP_gamma_w25_h25_p9004_n13679.xml")
    #cascade_fn = args.get('--cascade', "night_cascadeLBP_w25_h25_p2454_n6734.xml")
    #cascade_fn = args.get('--cascade', "night_cascadeLBP_gamma_w25_h25_p9004_n23457.xml")
    #print('cascade_fn ',cascade_fn )
    #    cascade = cv.CascadeClassifier(cv.samples.findFile(cascade_fn))
    cascade = cv.CascadeClassifier(cascade_fn)
    #nested = cv.CascadeClassifier(cv.samples.findFile(nested_fn))

    #cam = create_capture(video_src, fallback='synth:bg={}:noise=0.05'.format(cv.samples.findFile('samples/data/lena.jpg')))
    cam = cv.VideoCapture(vfile_src)
    ret, img = cam.read()
    print('img schape ', img.shape)
	
    while ret:
        ret, img = cam.read()
        if ret:
            img = cv.resize(img, (640, 480))
            # img = cv.resize(img, (1440, 1200))
            if USE_GAMMA:
                img = gamma(img)
            gray = cv.cvtColor(img, cv.COLOR_BGR2GRAY)
            #gray = cv.equalizeHist(gray)
			
            t = clock()
            rects = detect(gray, cascade)
            #remove_bad_rects(rects)
			            
            dt = clock() - t
            vis = img.copy()
            draw_rects(vis, rects, (0, 255, 0))


            draw_str(vis, (20, 20), 'time: %.1f ms' % (dt*1000))
            cv.imshow(str(cascade_fn), vis)
            if cv.waitKey(1) == 27:
                break
    cam.release()		
    cv.destroyAllWindows()
    print('THE END')
