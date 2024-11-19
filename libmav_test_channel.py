"""
Run script to get data about supported messages and commands against target autopilot.
It is rough and ready. By default connects to connectionType (search).

Outputs useful lists like "commands that didn't response with whether they are supported or not.
"""

import time

from tools import channel_manager

channel = channel_manager.Channel(None, None, port = '14540')
time.sleep(10)
print("complete")
