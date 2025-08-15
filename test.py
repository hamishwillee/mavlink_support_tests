"""
Run script to get data about supported messages and commands against target autopilot.
It is rough and ready. By default connects to connectionType (search).

Outputs useful lists like "commands that didn't response with whether they are supported or not.
"""

import time
import pprint
from tools.connection import MAVConnection

#connectionType = 'px4wsl2_companion_udp_client'
connectionType = 'px4wsl2_companion_udp_server' # Works PX4
#connectionType = 'px4wsl2_normal_udp_client'
# connectionType = 'px4wsl2_normal_udp_server'
#connectionType = 'ardupilot_wsl2_companion_udp_server'
#connectionType = 'ardupilot_wsl2_companion_tcp_server'

mavConnection = MAVConnection(connection_type=connectionType)

time.sleep(5)

print(mavConnection.components)


# time.sleep(10)

# The code that does stuff

testSendAllCommands = True
testGetAllMessages = False #



testGetSupportedModes = False  # depr
testGetSupportedModes2 = False
printMessageAcc = False
testStreamingBatteryMessages = False

testMAV_CMD_DO_SET_MODE = False
testMAV_CMD_DO_SET_GLOBAL_ORIGIN = False
testMAV_CMD_PREFLIGHT_REBOOT_SHUTDOWN = False

if testGetAllMessages:
    print("TEST: testGetAllMessages")
    from tests.all_messages import MessagesTest
    messageTest = MessagesTest(mav_component=mavConnection.components['1_1']) # Probably need to think about checking type etc for this. Good enough for now.
    time.sleep(20)
    messageTest.report()
    #pprint.pprint()


if testSendAllCommands:
    print("testSendAllCommands")
    from tests.all_commands_send import SendAllCommandsTest
    allCommandsTest = SendAllCommandsTest(mav_component=mavConnection.components['1_1'])
    allCommandsTest.sendAllCommands() # perhaps standardize on runTests
    time.sleep(20)
    allCommandsTest.report()



if testGetSupportedModes2:
    from tools import mode_manager
    # sysid = own_mavlink_ids["system_id"] - # TODO We should get from our connection and pass as a singleton.
    # compid = own_mavlink_ids["component_id"] # TODO We should get from our connection and pass as a singleton.
    # Ditto the message_set and the docs. In theory you could pass the thing that represents the connection and the target.

    modethingy = mode_manager.StandardModes(connection=connection, mavlinkDocs=mavlinkDocs,
                                            libmav_message_set=message_set, target_system=targetSystem, target_component=targetComponent)
    modethingy.requestModes()
    time.sleep(20)



time.sleep(10)
pprint.pprint(mavConnection.components['1_1'].report())
print("complete")

#pprint.pprint(mavConnection.components['1_1']._accumulator)
