#!/bin/bash
if ps aux | grep [g]unicorn;
then
kill -9 `pidof sudo python3`
sleep 2
echo "python3 process killed"
fi
echo "start pedestrian detector" 
arg=$1
sleep 2
#sudo python3 /home/pi/dp/dp_web_main.py
cd /home/a/dp2/ && gunicorn --threads 10 --workers 1 --bind 0.0.0.0:80 dp_web_main:app > /dev/null
exit 0

