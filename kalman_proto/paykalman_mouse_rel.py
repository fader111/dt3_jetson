from pykalman import KalmanFilter
import numpy as np
import time
import cv2

frame = np.zeros((400,400,3), np.uint8) # drawing canvas
meas=[]
pred=[]
mp = np.array((2,1)) # measurement


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
    frame = np.zeros((400,400,3), np.uint8)
    if len(meas) > 200:
        meas.pop(0)
    if len(pred) > 200:
        pred.pop(0)
        # pred.pop(0)
        # print('pred pop paint', len(pred))
    for i in range(len(meas)-1): cv2.line(frame,meas[i],meas[i+1],(0,100,0))
    for i in range(len(pred)-1): cv2.line(frame,pred[i],pred[i+1],(0,0,200))


def reset():
    global meas,pred,frame
    meas=[]
    pred=[]
    frame = np.zeros((400,400,3), np.uint8)

cv2.namedWindow("kalman")
cv2.setMouseCallback("kalman", onmouse)

# initial_state_mean = [0,0,0,0]

transition_matrix = [[1, 1, 0, 0],
                     [0, 1, 0, 0],
                     [0, 0, 1, 1],
                     [0, 0, 0, 1]]

observation_covariance = [[ 6400, 0],
                          [ 0, 6400]]

observation_matrix = [[1, 0, 0, 0],
                      [0, 0, 1, 0]]

kf1 = KalmanFilter(transition_matrices = transition_matrix,
                  observation_matrices = observation_matrix)#,
                #   initial_state_mean = initial_state_mean)#,
                #   observation_covariance = observation_covariance)
# print('kf1 initial state mean        ', kf1.initial_state_mean) # None
kf1 = kf1.em(np.asarray([(100,100), (0,0)]), n_iter=5)
# print('kf1 initial state mean aft em ', kf1.initial_state_mean) # [ 42.87447645 -14.30915798  42.87447645 -14.30915798]

filtered_state_means = kf1.initial_state_mean
filtered_state_covariances = kf1.initial_state_covariance
#observation_covariance need to be changed here, because default aren't ok, and em method changes it.
kf1.observation_covariance = observation_covariance
cur_previous = () # предыдущ значение предсказания фильтра
while True:
    filtered_state_means, filtered_state_covariances = \
        kf1.filter_update(filtered_state_means, filtered_state_covariances, observation = mp)
    cur_pred = (int(filtered_state_means[0]),int(filtered_state_means[2]))
    # print('filtr_st_m', cur_pred)
    if cur_pred != cur_previous :
        pred.append(cur_pred) # нужно чтобы на графика сохранялись картинки предсказания, иначе исчезают, 
        # т.к. забиваются одинаковыми значениями. 
    paint()
    # print(' len pred', len(pred))
    # print('pred', pred)
    cur_previous = cur_pred
    cv2.imshow('kalman', frame)
    if (cv2.waitKey(2) & 0xFF) == 27:
        break
    if (cv2.waitKey(2) & 0xFF) == ord('q'):
        #cv2.imwrite('kalman.jpg', frame)
        break
    if (cv2.waitKey(2) & 0xFF) == 32: 
        reset() # Space

cv2.destroyAllWindows()