#!/usr/bin/python
#
import jetson.utils
import argparse
import numpy as numpy
import cv2

# parse the command line
parser = argparse.ArgumentParser(description='Copy a test image from numpy to CUDA and save it to disk')

parser.add_argument("--width", type=int, default=512, help="width of the array (in float elements)")
parser.add_argument("--height", type=int, default=256, help="height of the array (in float elements)")
parser.add_argument("--depth", type=int, default=4, help="depth of the array (in float elements)")
parser.add_argument("--filename", type=str, default="cuda-from-numpy.jpg", help="filename of the output test image")

opt = parser.parse_args()

# create numpy ndarray
array = numpy.ndarray(shape=(opt.height, opt.width, opt.depth))

# fill array with test colors
for y in range(opt.height):
	for x in range(opt.width):
		array[y, x] = [ 0, float(x) / float(opt.width) * 255, float(y) / float(opt.height) * 255, 255]


video_src = "U524806_3.avi"

cap = cv2.VideoCapture(video_src)

ret, img = cap.read()

img = cv2.resize(img, (512, 256))
height, width = img.shape[:2]
print ('img shape=', img.shape)
cv2.imshow('img',img)
cv2.waitKey()
img = cv2.cvtColor(img, cv2.COLOR_BGR2RGBA)
# copy to CUDA memory
cuda_mem = jetson.utils.cudaFromNumpy(img)
print(cuda_mem)

# save as image
jetson.utils.saveImageRGBA(opt.filename, cuda_mem, width, height)
print("saved {:d}x{:d} test image to '{:s}'".format(width, height, opt.filename))

