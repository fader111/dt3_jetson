
import requests, time
from RepeatedTimer_ import RepeatedTimer

1

# det_status = [True,False,False,False]
# det_status = [True,False,False,False, True]
det_status = [1,0]
getan = None


# addrString = ['https://' + settings["hub"] + '/detect']
addrString = ['https://172.16.20.139/detect']




def send_det_status_to_hub(addrString, det_status):
    # передача состояний рамок на концентратор методом POST
    # addrString = 'http://' + hubAddress + '/detect'
    # must be a list to get an argument as a reference
    det_status[0] = not det_status[0]
    print('                              hub ', addrString, det_status)

#    requests.post('https://172.16.20.240/detect',json={"cars_detect":[True, False, False, False]}, verify=False).text
    ts = time.time()
    try:
        # pass
        # getan = requests.get(addrString[0], timeout=(1.1, 1.1), verify=False)
        # print('alala')
        # ans = requests.post(addrString[0], timeout=(1.0, 1.0), json={"cars_detect": det_status}, verify=False)
        ans = requests.post(addrString[0], json={"cars_detect": det_status}, verify=False)
        return (' ans.text ', ans.text)
    except Exception as error:
        pass
        print('expt from  sendColorStatusToHub', error)
        # return 'Disconnected...'
    # print(f'first {time.time()-ts:.7f}')
    1201
    # ts = time.time()
    # ans = requests.post(addrString[0], json={"cars_detect": det_status}, verify=False)
    # print('alala')

    # print(f'second {time.time()-ts:.7f}')

rtUpdStatusForHub = RepeatedTimer(
    0.4, send_det_status_to_hub, addrString, det_status)
rtUpdStatusForHub.start()

while 0:
    ts = time.time()
    det_status[0] = not det_status[0]
    print(send_det_status_to_hub(addrString, det_status))
    # time.sleep(0.4)
    print(f'spend {time.time()-ts:.7f}')

# print ('getan', getan.text)

# fad = [1,2,3,4]
# pp=print
# pp(fad)
# pp(fad[0:50])