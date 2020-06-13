# import the necessary packages
import numpy as np
import cv2


def order_points(pts):
    ''' achtung! works not all the time!! use version 2 below!'''
    # initialzie a list of coordinates that will be ordered
    # such that the first entry in the list is the top-left,
    # the second entry is the top-right, the third is the
    # bottom-right, and the fourth is the bottom-left
    rect = np.zeros((4, 2), dtype="float32")

    # the top-left point will have the smallest sum, whereas
    # the bottom-right point will have the largest sum
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]
    rect[2] = pts[np.argmax(s)]

    # now, compute the difference between the points, the
    # top-right point will have the smallest difference,
    # whereas the bottom-left will have the largest difference
    diff = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diff)]
    rect[3] = pts[np.argmax(diff)]

    # return the ordered coordinates
    return rect


def order_points2(pts):
    # input format
    #pts = [(x1,y1),(x2,y2),(x3,y3),(x4,y4)]

    # sort points by x
    tmp = sorted(pts, key=lambda point: point[0])

    # tmp[0] and tmp[1] is left point
    # determine, which is top, and which is bottom by y coordinate
    if tmp[0][1] > tmp[1][1]:
        tl = tmp[1]
        bl = tmp[0]
    else:
        tl = tmp[0]
        bl = tmp[1]

    # do it with right tmp[2] and tmp[3]
    if tmp[2][1] > tmp[3][1]:
        tr = tmp[3]
        br = tmp[2]
    else:
        tr = tmp[2]
        br = tmp[3]

    return np.array([tl, tr, br, bl])


def four_point_transform(image, pts, picMode=False):
	# in picMode function returns picture, else only M, Hight and Width
    # obtain a consistent order of the points and unpack them
    # individually
    # rect = order_points(pts)
    rect = order_points2(pts)
    (tl, tr, br, bl) = rect

    # compute the width of the new image, which will be the
    # maximum distance between bottom-right and bottom-left
    # x-coordiates or the top-right and top-left x-coordinates
    widthA = np.sqrt(((br[0] - bl[0]) ** 2) + ((br[1] - bl[1]) ** 2))
    widthB = np.sqrt(((tr[0] - tl[0]) ** 2) + ((tr[1] - tl[1]) ** 2))
    maxWidth = max(int(widthA), int(widthB))

    # compute the height of the new image, which will be the
    # maximum distance between the top-right and bottom-right
    # y-coordinates or the top-left and bottom-left y-coordinates
    heightA = np.sqrt(((tr[0] - br[0]) ** 2) + ((tr[1] - br[1]) ** 2))
    heightB = np.sqrt(((tl[0] - bl[0]) ** 2) + ((tl[1] - bl[1]) ** 2))
    # print("heightA, heightB", heightA, heightB)
    maxHeight = max(int(heightA), int(heightB))

    # now that we have the dimensions of the new image, construct
    # the set of destination points to obtain a "birds eye view",
    # (i.e. top-down view) of the image, again specifying points
    # in the top-left, top-right, bottom-right, and bottom-left
    # order
    dst = np.array([
        [0, 0],
        [maxWidth - 1, 0],
        [maxWidth - 1, maxHeight - 1],
        [0, maxHeight - 1]], dtype="float32")

    # compute the perspective transform matrix and then apply it
    M = cv2.getPerspectiveTransform(rect, dst)
    # print ('M=', M)
    warped = cv2.warpPerspective(image, M, (maxWidth, maxHeight))

    # return the warped image and matrix
    if picMode:
        return warped, M
    else:
        return M, maxWidth, maxHeight

# can be deleted
def windowToFieldCoordinates(originalPoint, perspectiveCoords, width=0, height=0):
    """Get 2D coordinates by transforming inputed perspective ones.

    Args:
        originalPoint (tuple): Position coordinates of a point in the perspective view.
        perspectiveCoords (list): Perspective field's 4 points' coordinates.
        width (int): Width in pixels for the 2D top-view field.
        height (int): Height in pixels for the 2D top-view field.

    Returns:
        list: Transformed coordinates [x,y].

    """
    (xp, yp) = originalPoint
    (x1, y1) = perspectiveCoords[0]
    (x2, y2) = perspectiveCoords[1]
    (x3, y3) = perspectiveCoords[2]
    (x4, y4) = perspectiveCoords[3]

    src = np.array([
        [x1, y1],
        [x2, y2],
        [x3, y3],
        [x4, y4]], dtype="float32")

    # those should be the same aspect as the real width/height of field
    width = (x4-x1) if width == 0 else width
    height = (y1-y2) if height == 0 else height

    # make a destination rectangle with the width and height of above (starts at 0,0)
    dst = np.array([
        [0, 0],
        [width - 1, 0],
        [width - 1, height - 1],
        [0, height - 1]], dtype="float32")

    # find the transformation matrix for our transforms
    transformationMatrix = cv2.getPerspectiveTransform(src, dst)

    # put the original (source) x,y points in an array
    original = np.array([((xp, yp), (xp, yp), (xp, yp))], dtype=np.float32)

    # use perspectiveTransform to transform our original to new coords with the transformation matrix
    transformedCoord = cv2.perspectiveTransform(
        original, transformationMatrix)[0][0]

    return transformedCoord
''' check 
calib = [[208,48],[566,34],[799,206],[239,294]] # calibration polygon 
ramkaPath = [[412, 84], [489, 66], [583, 138], [491, 164]]
up_ramka_point = 451, 75
down_ramka_point = 451, 75

fact_coord = windowToFieldCoordinates(up_ramka_point, calib, width=7, height=30 )
print('fact_ccord ', fact_coord)
'''
