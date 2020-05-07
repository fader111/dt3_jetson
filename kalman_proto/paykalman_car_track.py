from pykalman import KalmanFilter
import numpy as np
import time
import cv2

frame = np.zeros((800,800,3), np.uint8) # drawing canvas
meas=[]
pred=[]
mp = np.array((2,1)) # measurement

coef = 5000.0

# measurements = np.asarray([(186,43),(188,44),(189,48),(189,52),(192,55),
# (202,67),(215,77),(216,81),(222,87),(226,91),(230,95),(235,104),(241,109),
# (243,115),(251,123),(257,129),(261,141),(270,146),(281,158),(287,167),(289,179),(307,193)])

# # measurements = np.asarray([(366, 100), (381, 104), (386, 111), (395, 118), (408, 122), (418, 130), (429, 137), (438, 144), (453, 152), (471, 158), (486, 169), (502, 179), (521, 192)])
# measurements = np.asarray([(366, 100), (381, 104), (386, 111), (395, 118), (308, 122), (418, 130), 
#         (429, 137), (438, 144), (453, 152), (471, 158), (486, 169), (502, 179), 
#         (521, 192)])#, (521, 192), (521, 192), (521, 192)])

#measurements = np.asarray([(187, 44), (189, 45), (190, 49), (190, 53), (193, 56), (203, 68), (216, 78), (217, 82), (224, 88), (228, 92), (232, 96), (237, 105), (243, 110), (245, 116),
measurements = np.asarray([(187, 44), (189, 45), (190, 49), (190, 53), (193, 56), (263, 88), (216, 78), (217, 82), (224, 88), (228, 92), (232, 96), (237, 105), (243, 110), (245, 116),
 (253,124), (259,130), (263,142), (272,147), (283,159), (289,168), (300,180), (309,194), (322,205), 
 (333,220), (348,239), (366,255), (384,275), (384,275), (384,275), (384,275)])

print('measurements ', measurements)

def onmouse(k,x,y,s,p):
    global mp,meas
    mp = np.array([x,y])
    meas.append((x,y))
    if len(meas) >200:
        meas.pop(0)
    if len(pred) >200:
        pred.pop(0)


def paint():
    global frame,meas,pred
    frame = np.zeros((800,800,3), np.uint8)
    if len(meas) >200:
        meas.pop(0)
    if len(pred) >200:
        pred.pop(0)
        # pred.pop(0)
        # print('pred pop paint', len(pred))
        
    for i in range(len(meas)-1): 
        cv2.line(frame, meas[i], meas[i+1],(0,100,0))

    for i in range(len(pred)-1): 
        cv2.line(frame,pred[i],pred[i+1],(0,0,200))
    # draw circles
    for i in range(len(meas)-1): 
        cv2.circle(frame, meas[i], 3, (0,100,0))
    for i in range(len(pred)): 
        cv2.circle(frame, pred[i], 3, (0,0,200))


def reset():
    global meas,pred,frame
    meas=[]
    pred=[]
    frame = np.zeros((400,400,3), np.uint8)


# cv2.namedWindow("kalman", cv2.WINDOW_AUTOSIZE)
# cv2.setMouseCallback("kalman", onmouse)

# initial_state_mean = [0,0,0,0]
initial_state_mean = [measurements[0][0],0, measurements[0][1],0]

transition_matrix = [[1, 1, 0, 0],
                     [0, 1, 0, 0],
                     [0, 0, 1, 1],
                     [0, 0, 0, 1]]

# observation_covariance = [[ 6400, 0],
#                           [ 0, 6400]]

observation_matrix = [[1, 0, 0, 0],
                      [0, 0, 1, 0]]

kf1 = KalmanFilter(transition_matrices = transition_matrix,
                  observation_matrices = observation_matrix)#,
                #   initial_state_mean = initial_state_mean)#,
                #   observation_covariance = observation_covariance)
# print('kf1 initial state mean        ', kf1.initial_state_mean) # None
kf1 = kf1.em(np.asarray([(0,0), (0,0)]), n_iter=5)
# print('kf1 initial state mean aft em ', kf1.initial_state_mean) # [ 42.87447645 -14.30915798  42.87447645 -14.30915798]

kf1.initial_state_mean = initial_state_mean

filtered_state_means = kf1.initial_state_mean
filtered_state_covariances = kf1.initial_state_covariance
#observation_covariance need to be changed here, because default aren't ok, and em method changes it.
# kf1.observation_covariance = observation_covariance
print('obs_cov', kf1.observation_covariance)
kf1.observation_covariance = coef*kf1.observation_covariance
# kf1.observation_covariance = 2.0*kf1.observation_covariance
cur_previous = () # предыдущ значение предсказания фильтра

print('filtered_state_means',filtered_state_means)
print('filtered_state_covariances',filtered_state_covariances)
print('kf1.observation_covariance',kf1.observation_covariance)

for ind, mp in enumerate(measurements):
    # time.sleep(0.5)
    print('fst_mean ', filtered_state_means)
    meas.append((mp[0], mp[1]))
    filtered_state_means, filtered_state_covariances = \
        kf1.filter_update(filtered_state_means, filtered_state_covariances, observation = mp)
    cur_pred = (int(filtered_state_means[0]),int(filtered_state_means[2]))
    # print('filtr_st_m', cur_pred)
    # if cur_pred != cur_previous:
    pred.append(cur_pred) # нужно чтобы на графика сохранялись картинки предсказания, иначе исчезают, 
    #     # т.к. забиваются одинаковыми значениями. 
    paint()
    # print(' len pred', len(pred))
    # print('pred', pred)
    cur_previous = cur_pred
    frame = cv2.resize(frame,(800,800))
    # cv2.namedWindow('kalman', cv2.WINDOW_NORMAL)
    cv2.imshow('kalman', frame)
    if (cv2.waitKey(0) & 0xFF) == 27:
        break
    if (cv2.waitKey(2) & 0xFF) == ord('q'):
        #cv2.imwrite('kalman.jpg', frame)
        break
    if (cv2.waitKey(2) & 0xFF) == 32: 
        reset() # Space
print ('pred', pred)
cv2.waitKey(0)
# cv2.destroyAllWindows()