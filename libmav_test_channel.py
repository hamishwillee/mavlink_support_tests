"""
Run script to get data about supported messages and commands against target autopilot.
It is rough and ready. By default connects to connectionType (search).

Outputs useful lists like "commands that didn't response with whether they are supported or not.
"""

import time

from tools import channel_manager
from mavdocs import XMLDialectInfo
#XMLDialectInfo really need to be able to specify path to this
mavlinkDocs = XMLDialectInfo(dialect='development')

channel = channel_manager.Channel(mavlinkDocs, port = '14540')
time.sleep(10)
print("complete")
