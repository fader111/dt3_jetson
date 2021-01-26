# gst-launch-1.0 videotestsrc ! 'video/x-raw,width=320,height=240,framerate=30/1' ! omxh264enc ! rtspclientsink location=rtsp://localhost:8001/sample protocols=tcp

# At start
# first stop current computing
# make new background
# start record

# At finish
# stop record
# start computing
# set camera background in web

import glob
import pathlib
import subprocess

import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst, GLib, Gtk
gi.require_version('Gtk', '3.0')

Gst.init()

RTSP_ENDPOINT = 'rtsp://localhost:8001/sample'
RTSP_MEDIA_SERVER_NAME = 'rtsp-simple-server'
WIDTH = 1280
HEIGHT = 720
FPS = 60

def run_rtsp_media_server():
    """
    alternative_path = '/home/a/sources/RtspRestreamServer/build/RestreamServerApp/RestreamServerApp'
    :return:
    """
    path_of_executable = pathlib.Path('/home/a/sources/rtsp-simple-server/rtsp-simple-server /home/a/sources/rtsp-simple-server/rtsp-simple-server.yml')
    subprocess.Popen(str(path_of_executable), shell=True)

def check_process_runs(name):
    cmd_filenames = glob.glob('/proc/*/cmdline')
    for filename in cmd_filenames:
        with open(filename, 'r') as cmd_file:
            cmd = cmd_file.read()
            if name in cmd:
                return True

    return False


def start_RTSP_record_stream():
    # check that media server runs
    if not check_process_runs(RTSP_MEDIA_SERVER_NAME):
        run_rtsp_media_server()

    # construct pipeline
    pipeline = Gst.Pipeline.new()
    src = Gst.ElementFactory.make('nvarguscamerasrc')
    capsfilter = Gst.ElementFactory.make('capsfilter')
    src_caps = Gst.Caps.from_string(f'video/x-raw,width={WIDTH},height={HEIGHT},framerate={FPS}/1')
    capsfilter.set_property('caps', src_caps)
    encoder = Gst.ElementFactory.make('omxh264enc')
    output = Gst.ElementFactory.make('rtspclientsink')
    output.set_property('location', RTSP_ENDPOINT)
    output.set_property('protocols', 'tcp')

    pipeline.add(src)
    pipeline.add(capsfilter)
    pipeline.add(encoder)
    pipeline.add(output)

    src.link(capsfilter)
    capsfilter.link(encoder)
    encoder.link(output)

    pipeline.set_state(Gst.State.PLAYING)

start_RTSP_record_stream()
Gtk.main()