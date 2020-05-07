import io
import time
import picamera
from picamera.array import PiRGBArray
from base_camera import BaseCamera


##width  = 480
##height = 368
##width  = 800
##height = 608
width  = 400
height = 300


class Camera(BaseCamera):
    @staticmethod
    def frames():
        with picamera.PiCamera() as camera:
            # camera setup
            camera.resolution = (width, height)
            camera.framerate = 25
            camera.hflip = True
            camera.vflip = True
            camera.brightness = 50
            
            # let camera warm up
            camera.start_preview()
            time.sleep(2)
            
            ##stream = io.BytesIO()
            stream = PiRGBArray(camera, size=camera.resolution)
            ##for _ in camera.capture_continuous(stream, 'jpeg', use_video_port=True):
            for _ in camera.capture_continuous(stream, format='bgr', use_video_port=True):
                # return current frame
                stream.seek(0)
                ##yield stream.read()
                yield _.array

                # reset stream for next frame
                stream.seek(0)
                stream.truncate()
