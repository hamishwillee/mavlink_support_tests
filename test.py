"""
Run script to get data about supported messages and commands against target autopilot.
It is rough and ready. By default connects to connectionType (search).

Outputs useful lists like "commands that didn't response with whether they are supported or not.
"""

import time
import pprint
from tools.connection import MAVConnection

# connectionType = 'px4wsl2_companion_udp_client'
connectionType = 'px4wsl2_companion_udp_server'
# connectionType = 'px4wsl2_normal_udp_client'
# connectionType = 'px4wsl2_normal_udp_server'


mavConnection = MAVConnection(connection_type=connectionType)

time.sleep(10)


print(mavConnection.components)
# mavConnection.components['1_1'].startAccumulating()


# time.sleep(10)

# The code that does stuff

testGetSupportedModes = False  # depr
testGetSupportedModes2 = False
printMessageAcc = False
testStreamingBatteryMessages = False
testSendAllCommands = False
testMAV_CMD_DO_SET_MODE = False
testMAV_CMD_DO_SET_GLOBAL_ORIGIN = True
testMAV_CMD_PREFLIGHT_REBOOT_SHUTDOWN = False


if testGetSupportedModes2:
    from tools import mode_manager
    # sysid = own_mavlink_ids["system_id"] - # TODO We should get from our connection and pass as a singleton.
    # compid = own_mavlink_ids["component_id"] # TODO We should get from our connection and pass as a singleton.
    # Ditto the message_set and the docs. In theory you could pass the thing that represents the connection and the target.

    modethingy = mode_manager.StandardModes(connection=connection, mavlinkDocs=mavlinkDocs,
                                            libmav_message_set=message_set, target_system=targetSystem, target_component=targetComponent)
    modethingy.requestModes()
    time.sleep(20)



time.sleep(20)
print("complete")

pprint.pprint(mavConnection.components['1_1']._accumulator)
