
from threading import Timer
class RepeatedTimer(object):
    def __init__(self, interval, function, *args, **kwargs):
        self._timer = None
        self.interval = interval
        self.function = function
        self.args = args
        self.kwargs = kwargs
        self.is_running = False
        # self.start()

    def _run(self):
        ##self.is_running = False
        self._start()
        self.function(*self.args, **self.kwargs)

    def _start(self):
        # if self._timer and self._timer.isAlive(): 
            # self._timer.cancel()
            # self._timer = None
            # print('NONE!!!!!!!!!!!!!!!!!!!!')
        self._timer = Timer(self.interval, self._run)
        self._timer.start()

    def start(self):
        if not self.is_running:
            self._timer = Timer(self.interval, self._run)
            self._timer.start()
            self.is_running = True

    def stop(self):
        if self._timer:
            self._timer.cancel()
            self.is_running = False

    def isAlive(self):
        return self.is_running