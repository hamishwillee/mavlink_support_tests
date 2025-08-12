"""
Run script to get data about supported messages and commands against target autopilot.
It is rough and ready. By default connects to connectionType (search).

Outputs useful lists like "commands that didn't response with whether they are supported or not.
"""

from tools import command_sender
from mavdocs import XMLDialectInfo
import libmav
import time
import pprint
from collections import deque
import numpy as np




def inspect_object(object):
    print(f"Public API: {type(object).__name__}")
    for attr in dir(object):
        if not attr.startswith('__'):
            value = getattr(object, attr)
            print(f"  {attr} (Value: {value}) (type: {type(value)})")


# XMLDialectInfo really need to be able to specify path to this

mavlinkDocs = XMLDialectInfo(dialect='development')


# print(id_value_dict_MAV_TYPE)

# TODO The script to get data about APIs
# Want to be able to get handle to any enum using its enum name.
# Want to get any enum name from an enum value.
# Want to get any enum value from an enum name. (not as imp - can do in libmav)
# Want to be able to get list of all messages
# Want to be able to get list of all command names

# TODO
# Check unknown responses - i.e if we get a message we don't know. This is something PYMAV can detect.


# Create a message set from a mavlink xml file
# message_set = libmav.MessageSet('./mavlink/message_definitions/v1.0/common.xml')
# message_set = libmav.MessageSet('./mavlink/message_definitions/v1.0/ardupilotmega.xml')
message_set = libmav.MessageSet(
    './mavlink/message_definitions/v1.0/development.xml')

# Create a heartbeat message
heartbeat_message = message_set.create('HEARTBEAT')
heartbeat_dict = {
    "type": message_set.enum("MAV_TYPE_GCS"),
    "autopilot": message_set.enum("MAV_AUTOPILOT_INVALID"),
    "base_mode": 0,
    "custom_mode": 0,
    "system_status": message_set.enum("MAV_STATE_ACTIVE"),
    "mavlink_version": 2,
}

heartbeat_message.set_from_dict(heartbeat_dict)

"""
PX4
INFO  [mavlink] mode: Normal, data rate: 4000000 B/s on udp port 18570 remote port 14550
INFO  [mavlink] mode: Onboard, data rate: 4000000 B/s on udp port 14580 remote port 14540
INFO  [mavlink] mode: Onboard, data rate: 4000 B/s on udp port 14280 remote port 14030
INFO  [mavlink] mode: Gimbal, data rate: 400000 B/s on udp port 13030 remote port 13280
"""

# connectionType = 'px4wsl2_companion_udp_client'
connectionType = 'px4wsl2_companion_udp_server'
# connectionType = 'px4wsl2_normal_udp_client'
# connectionType = 'px4wsl2_normal_udp_server'

if connectionType == 'px4wsl2_companion_udp_client':
    connection_address = '172.19.48.140'
    # Onboard, data rate: 4000000 B/s on udp port 14580 remote port 14540
    connection_port = 14580
    conn_physical = libmav.UDPClient(connection_address, connection_port)

# Normal, data rate: 4000000 B/s on udp port 18570 remote port 14550
if connectionType == 'px4wsl2_normal_udp_client':
    connection_address = '172.19.48.140'
    connection_port = 18570  # 18570
    conn_physical = libmav.UDPClient(connection_address, connection_port)

# Normal, data rate: 4000000 B/s on udp port 18570 remote port 14550
if connectionType == 'px4wsl2_normal_udp_server':
    # connection_address = '172.19.48.140'
    connection_port = 14550  # 18570
    conn_physical = libmav.UDPServer(connection_port)

# Normal, data rate: 4000000 B/s on udp port 18570 remote port 14550
if connectionType == 'px4wsl2_companion_udp_server':
    # connection_address = '172.19.48.140'
    # Onboard, data rate: 4000000 B/s on udp port 14580 remote port 14540
    connection_port = 14540
    conn_physical = libmav.UDPServer(connection_port)

# INFO  [mavlink] mode:
# INFO  [mavlink] mode:

# elif connectionType == 'px4wsl2_companion':

# Connect to a UDP server
# APM work:
# connection_address = '127.0.0.1'
# connection_port = 14551 #note, # works UDP amp
# connection_port = 14550 #note, is int
# connection_port = 14550 # Works for PX4 UDP


# conn_physical = libmav.UDPServer(connection_port)

# conn_physical = libmav.UDPClient(connection_address, connection_port)
# conn_physical = libmav.TCPClient(connection_address, connection_port)
# conn_physical = libmav.UDPServer(connection_port)
# conn_physical = libmav.TCPServer(connection_port)

# inspect_object(conn_physical) # (a UDPServer)

# default system ID=componentID=97
own_mavlink_ids = {
    "system_id": 250,  # Some GCS unallocated id
    "component_id": 194  # MAV_COMP_ID_ONBOARD_COMPUTER4 - could be anything
}
conn_runtime = libmav.NetworkRuntime(libmav.Identifier(
    own_mavlink_ids["system_id"], own_mavlink_ids["component_id"]), message_set, heartbeat_message, conn_physical)


# inspect_object(conn_runtime) # (a NetworkRuntime)

connection = conn_runtime.await_connection(5000)
# connection = conn_runtime.await_connection(-1) - waits forever and you get stuck until is a connection
# connection = conn_runtime.await_connection(0) - "RuntimeError: Timeout while waiting for first connection

# inspect_object(connection) # (a Connection)
# inspect_object(connection.partner()) # (a Connection)

# inspect_object(connection.alive()) # (a Connection)

autopilotInfoAll = dict()


# identity_check_callback_handle = connection.add_message_callback(identityCheck)

class MAVLinkSupportInfo:
    def __init__(self):
        # Creating instance variables
        self.__accumulator = dict()
        self.__messages = dict()  # The logged info about messages
        self.__commands = dict()  # The logged info about commands
        self.__identity = dict()
        self.__first_timestamp = None
        self.__last_timestamp = None
        self.__new_message_timestamp = None
        self.__starting = True
        self.__no_message_change = True

        # Populate the commands with info about what we're interested in:
        allCommands = mavlinkDocs.getCommands()
        for name in allCommands.keys():
            self.__commands[name] = {
                'name': name, 'id': allCommands[name]['value'], 'result': None, }

    def messageArrived(self, msg):

        # Add code in to work out what autopilot we are talking to.
        self.identityCheck(msg)

        # This is just to give us a pulse. This stuff should be abstracted
        self.currentMode(msg)

        # Discard messages if we haven't yet found an autopilot (or "not a GCS")
        if 'system_id' not in self.__identity:
            # print("Identity of system not yet known")
            return

        # Discard messages if from wrong type (ie "a GCS")
        if not self.__identity['system_id'] == msg.header.system_id:
            # print(f"Wrong system id: {msg.header.system_id}")
            return

        # Record timestamp of first message, time running, time since last new message
        self.__last_timestamp = time.monotonic()
        if not self.__first_timestamp:
            self.__first_timestamp = time.monotonic()

        timeRunning = self.__last_timestamp - self.__first_timestamp
        # print(f"timeRunning {timeRunning}")
        timeSinceLastNewMessage = 0
        if self.__new_message_timestamp:
            timeSinceLastNewMessage = self.__last_timestamp - self.__new_message_timestamp

        if timeSinceLastNewMessage > 20:
            pass
            # print(f"No new messages: {timeSinceLastNewMessage}s")

        # After 30 s of run-time we clear the starting flag
        # This allows us to identify all the messages that arrive on first boot.
        if self.__starting and timeRunning > 30:  # TODO Should set this to be passed in or global value
            # print(f"timeSinceLastNewMessage {timeSinceLastNewMessage}, timeRunning {timeRunning}")
            self.__starting = None

        # Log supported messages as they are received (this is the output version)
        # Add "initial" if we are running this in the intial state.
        messageName = msg.name
        if messageName not in self.__messages:
            self.__new_message_timestamp = self.__last_timestamp
            self.__messages[messageName] = {}
            if self.__starting:
                self.__messages[messageName]["initial"] = True

        # messageName = msg.get_type() #pymav variant

        # Log messages as they are recieved
        # (this is a "working" repo of info used for stats, which we may clear at various points)
        if messageName not in self.__accumulator:
            first_timestamp = time.monotonic()
            self.__accumulator[messageName] = {
                "count": 1, "first_timestamp": first_timestamp, "last_timestamp": first_timestamp, "maxHz": 0, "minHz": 1000000}
            if self.__no_message_change:  # ie haven't started changing what gets streamed
                self.__accumulator[messageName]['initial'] = True

            print(f'Debug: Acc: New Message: {messageName}')
            new_message_dict = msg.to_dict()
            print(f'Debug: Acc: New Message: {new_message_dict}')

        else:
            self.__accumulator[messageName]["count"] += 1
            last_timestamp = time.monotonic()
            timediff_last = last_timestamp - \
                self.__accumulator[messageName]["last_timestamp"]
            # print(timediff_last)
            hz_last = 1 / timediff_last
            if hz_last > self.__accumulator[messageName]["maxHz"]:
                self.__accumulator[messageName]["maxHz"] = hz_last
            if hz_last < self.__accumulator[messageName]["minHz"]:
                self.__accumulator[messageName]["minHz"] = hz_last
            # TODO perhaps look at last values for packetloss?

            # print(hz_last)
            self.__accumulator[messageName]["hz_last"] = hz_last
            hz_avg = 1 / \
                ((last_timestamp-self.__accumulator[msg.name]
                 ["first_timestamp"])/self.__accumulator[messageName]["count"])
            # print(hz_avg)
            # Across the whole queue
            self.__accumulator[messageName]["hz_avg"] = hz_avg
            # update the last timestamp
            self.__accumulator[messageName]["last_timestamp"] = time.monotonic()

            # Store some data
            if "queue" in self.__accumulator[msg.name]:
                msgQueueTime = self.__accumulator[msg.name]["queue"]
                pass
            else:
                msgQueueTime = msgQueueTime = deque(maxlen=100)
            msgQueueTime.append(timediff_last)
            self.__accumulator[msg.name]["queue"] = msgQueueTime

        # COMMAND_ACK handling
        if messageName == 'COMMAND_ACK':
            command_dict = msg.to_dict()
            # inspect_object(command_dict)
            # print(command_dict)
            # for key, field in command_dict.items():
            #   print(f"{key}: {field}")
            # get id from command
            command_id_in_ack = command_dict['command']
            # print(f"debug: command_id_in_ack: {command_id_in_ack}")
            command_name_for_ack = mavlinkDocs.getCommandName(
                command_id_in_ack)
            # pprint.pprint(command_name_for_ack)
            result_in_ack = command_dict['result']
            # result_name = mavlinkDocs.getEnumEntryNameFromId('MAV_RESULT', result_in_ack)
            command_supported = False if result_in_ack == 3 else True

            if command_name_for_ack not in self.__commands:
                # We don't expect extra commands to be received than the ones we send.
                self.__commands[command_name_for_ack] = {
                    'name': command_name_for_ack, 'id': command_id_in_ack, 'result': command_supported, 'unexpected': True}
            else:
                if self.__commands[command_name_for_ack]['result'] is None:
                    self.__commands[command_name_for_ack]['result'] = command_supported
                else:
                    if self.__commands[command_name_for_ack]['result'] is not command_supported:
                        print(
                            f"debug: ACK changed from supported to unsupported (or visa versa)!: {command_name_for_ack}")

            # pprint.pprint(self.__commands)

            # print(failHere)

    def identityCheck(self, msg):
        # todo - could also add sitl check etc
        # print(inspect_object(msg))
        # print(inspect_object(msg.header))

        # print(msg.name)
        if msg.name == "HEARTBEAT" and not 'autopilot' in self.__identity:
            # print(msg)
            message_dict = msg.to_dict()
            # print(message_dict)
            # inspect_object(msg)
            # do I want to store under 'identity" Do I want to store under component id? After all, I might have multiple components, systems in some cases?
            # I think I only want things that identify as an autopilot component for this. Should check component iD too just to see.

            autopilot_type = mavlinkDocs.getEnumEntryNameFromId(
                'MAV_AUTOPILOT', message_dict['autopilot'])
            if 'MAV_AUTOPILOT_INVALID' == autopilot_type:
                print("ignore GCS")
                # TODO A MORE THOROUGH CHECK that locks to a component id.
                return

            self.__identity['system_id'] = msg.header.system_id
            self.__identity['component_id'] = msg.header.component_id

            self.__identity['autopilot'] = autopilot_type
            self.__identity['type'] = mavlinkDocs.getEnumEntryNameFromId(
                'MAV_TYPE', message_dict['type'])
            print(self.__identity)
        if msg.name == "AUTOPILOT_VERSION" and not 'version' in self.__identity and 'autopilot' in self.__identity:
            message_dict = msg.to_dict()
            # print(message_dict)

            major_version = (
                message_dict['middleware_sw_version'] >> (8 * 3)) & 0xFF
            minor_version = (
                message_dict['middleware_sw_version'] >> (8 * 2)) & 0xFF
            patch_version = (
                message_dict['middleware_sw_version'] >> (8 * 1)) & 0xF
            self.__identity['version'] = f"{major_version}.{minor_version}.{patch_version}"
            print(self.__identity)

    def currentMode(self, msg):
        # todo - could also add sitl check etc
        # print(inspect_object(msg))
        # print(inspect_object(msg.header))

        # print(msg.name)
        if msg.name == "HEARTBEAT":
            # print(msg)
            message_dict = msg.to_dict()
            print(f"current_mode: {message_dict}")
        if msg.name == "CURRENT_MODE":
            # print(msg)
            message_dict = msg.to_dict()
            print(message_dict)
        if msg.name == "STATUSTEXT":
            # print(msg)
            message_dict = msg.to_dict()
            print(message_dict)

    def __round_to_nearest_standard_hz(self, value):
        # List of standard frequencies
        standard_frequencies = [100, 50, 40, 30, 20, 10, 5,
                                4, 3, 2, 1, 0.5, 0.33, 0.25, 0.2, 0.1, 0.02, 0.01]
        array = np.array(standard_frequencies)
        index = (np.abs(array - value)).argmin()
        standard_value = array[index]
        diff = np.abs(value - standard_value)/standard_value*100
        if value > 110 or value < 0.006:
            print(
                f"val: {value} outside expected range (st_val: {standard_value})")
            pass
        if diff > 10:
            print(
                f"diff: {diff} (value different to standard value) - st_val: {standard_value}")
            pass
        return standard_value

    def getMessageCurrentHz(self, msgName):
        if "queue" not in self.__accumulator[msgName]:
            return None

        lastPeriod = self.__accumulator[msgName]["queue"][-1]
        lastFrequency = 1/lastPeriod

        timeDiffLastStamp = time.monotonic(
        ) - self.__accumulator[msgName]["last_timestamp"]
        # More than 2 times measured period old we don't know actual
        ageOfLastMessage = timeDiffLastStamp/lastPeriod
        # print(f"msgName: {msgName}, lastPeriod: {lastPeriod}, lastFrequency: {lastFrequency}, ageOfLastMessage: {ageOfLastMessage}")
        if ageOfLastMessage > 2:
            return None
        else:
            return lastFrequency

    def getMessageEstHz(self, msgName):
        """
        Gets the std and av Hz of message as an object { std, av }, or None if not streamed
        """
        # print(f'msg: {msgName}')
        totaltimeAllMessages = self.__last_timestamp - self.__first_timestamp
        # Function to round to the nearest standard frequency

        if "queue" not in self.__accumulator[msgName]:
            return None

        queueList = self.__accumulator[msgName]["queue"]
        averagePeriod = np.mean(queueList)

        roundedHzAv = self.__round_to_nearest_standard_hz(1/averagePeriod)
        roundedPeriodAv = 1/roundedHzAv

        maxHz = self.__accumulator[msgName]["maxHz"]
        minHz = self.__accumulator[msgName]["minHz"]
        avMaxMin = 100 * (maxHz - minHz)/maxHz

        if avMaxMin < 20:
            return {"std": roundedHzAv, "av": round(1/averagePeriod, 3)}

        # print(f"mean (T): {averagePeriod}, (Hz): {1/averagePeriod}, rndHz: {round(1/averagePeriod)}, rndstd: {roundedHzAv}, maxHz: {maxHz}, minHz: {minHz}, avMaxMin: {avMaxMin}")

        # median = np.median(queueList)
        # print(f"median (T): {median}, (Hz): {1/median}, rndHz: {round(1/median)}, rndstd: {1/self.__round_to_nearest_standard_hz(median)}")

        # Get mode but assume values are about right
        # mode_hz_rounded_values = [round(1/value) for value in queueList]
        # mode = np.bincount(mode_hz_rounded_values).argmax()
        # print(f"mode (T): {mode}, (Hz) {1/mode}")

        # std_dev = np.std(queueList)  # For population standard deviation
        # print(f"std_dev {std_dev}")

        countIfStreamed = totaltimeAllMessages // roundedPeriodAv  # whole number part
        count = self.__accumulator[msgName]['count']
        streamTest = (abs(countIfStreamed-count)/countIfStreamed)*100

        print(f"{msgName} MaybeNotStreamed: streamed% {streamTest},  avMaxMin: {avMaxMin}, Hz: {1/averagePeriod})")

        """
        if streamTest < 50:
            return roundedHzAv
        #print(f"streamed% {streamTest} (count: {count}, est: {countIfStreamed}, Hz: {1/averagePeriod})")
        """

        return None

        # messageAccumulator[messageName]["hz_avg_acc_last_rounded_mode"] = round(1/average)

    def getMessageInfo(self):
        return self.__messages

    def getCommandInfo(self):
        return self.__commands

    def getCommandSupportInfoSorted(self):
        true_commands = []
        false_commands = []
        none_commands = []

        for command_name in self.__commands.keys():
            if self.__commands[command_name]['result'] is True:
                true_commands.append(command_name)
            elif self.__commands[command_name]['result'] is False:
                false_commands.append(command_name)
            else:
                none_commands.append(command_name)

        return {'supported': true_commands, 'unsupported': false_commands, 'unknown': none_commands}

        return self.__commands

    def populateMessageInfo(self):
        for msg in self.__accumulator:
            estRates = self.getMessageEstHz(msg)
            if estRates:
                avRate = estRates["av"]
                stdRate = estRates["std"]
                actualRate = self.getMessageCurrentHz(msg)
                if stdRate:
                    self.__messages[msg]['nominalHz'] = stdRate
                if avRate:
                    self.__messages[msg]['avHz'] = avRate


msgInfo = MAVLinkSupportInfo()


# Get callback for any message.
# all_messages_callback_handle = connection.add_message_callback(lambda msg: print(f'Yay {msg.name}'))
all_messages_callback_handle = connection.add_message_callback(
    msgInfo.messageArrived)


def getSupportedModes():
    print("debug: getSupportedModes: start")
    from service_tests import standard_modes
    modesTest = standard_modes.StandardModesTest(connection=connection, mavlinkDocs=mavlinkDocs, libmav_message_set=message_set,
                                                 own_system_id=own_mavlink_ids["system_id"], own_component_id=own_mavlink_ids["component_id"])
    modesTest.getSupportedModes()


# The code that does stuff

# Start with wait after connecting to accumulate default_streamed messages.
accumulate_time = 10
print(f"Accumulating default streamed messages ({accumulate_time})")
time.sleep(accumulate_time)
# After this we might start collecting some new messages, such as autopilot version
msgInfo.__no_message_change = False
msgInfo.populateMessageInfo()


# request more identity info
# Note, done after the accumulator part, because it isn't streamed.
# Todo add enough info to determine what is really streamed and what is not.
print("Getting autopilot version ... - 5s")

# Library for sending commands

targetSystem = 1
# TODO We should get from our connection.
targetComponent = message_set.enum("MAV_COMP_ID_AUTOPILOT1")
request_message_id = message_set.id_for_message('AUTOPILOT_VERSION')
commander = command_sender.CommandSender(connection=connection, mavlinkDocs=mavlinkDocs, libmav_message_set=message_set,
                                         own_system_id=own_mavlink_ids["system_id"], own_component_id=own_mavlink_ids["component_id"])

commander.sendCommandRequestMessageNonBlocking(
    target_system=targetSystem, target_component=targetComponent, request_message_id=request_message_id)

# Test send


time.sleep(3)


# connection.remove_message_callback(all_messages_callback_handle) # leave running - is handy
print("end first part")


# The code that does stuff

testGetSupportedModes = False #depr
testGetSupportedModes2 = False
printMessageAcc = True
testStreamingBatteryMessages = False
testSendAllCommands = False
testMAV_CMD_DO_SET_MODE = False
testMAV_CMD_DO_SET_GLOBAL_ORIGIN = True
testMAV_CMD_PREFLIGHT_REBOOT_SHUTDOWN = False


if testGetSupportedModes:
    getSupportedModes()  # This works


if testGetSupportedModes2:
    from tools import mode_manager
    ##sysid = own_mavlink_ids["system_id"] - # TODO We should get from our connection and pass as a singleton.
    ##compid = own_mavlink_ids["component_id"] # TODO We should get from our connection and pass as a singleton.
    ## Ditto the message_set and the docs. In theory you could pass the thing that represents the connection and the target.

    modethingy = mode_manager.StandardModes(connection=connection, mavlinkDocs=mavlinkDocs, libmav_message_set=message_set, target_system=targetSystem, target_component=targetComponent)
    modethingy.requestModes()
    time.sleep(15)

if testStreamingBatteryMessages:
    # Testing streaming of battery messages
    request_message_id = message_set.id_for_message('BATTERY_STATUS')
    sendCommandMessageIntervalNonBlocking(connection=connection, target_system=targetSystem,
                                          target_component=targetComponent, target_message_id=request_message_id, interval=0)
    time.sleep(10)


if testStreamingBatteryMessages:
    # Testing streaming of battery messages
    request_message_id = message_set.id_for_message('BATTERY_STATUS')
    sendCommandMessageIntervalNonBlocking(connection=connection, target_system=targetSystem,
                                          target_component=targetComponent, target_message_id=request_message_id, interval=0)
    time.sleep(15)

if testSendAllCommands:
    print("testSendAllCommands")
    # Send all commands (to test ACKS)
    commander.sendAllCommands(
        target_system=targetSystem, target_component=targetComponent)
    # TODO see if we get ack back for all the original messages.
    time.sleep(3)
    pprint.pprint(msgInfo.getCommandSupportInfoSorted())
    # pprint.pprint(msgInfo.getCommandInfo())

if printMessageAcc:
    print("printMessageAcc")
    #pprint.pprint(msgInfo.)
    #pprint.pprint(messageInfo)

# print(autopilotInfoAll)


# print(msgInfo.__identity)
pprint.pprint(msgInfo.getMessageInfo())


if testMAV_CMD_DO_SET_GLOBAL_ORIGIN:
    print("testMAV_CMD_DO_SET_GLOBAL_ORIGIN")
    # Try send MAV_CMD_DO_SET_GLOBAL_ORIGIN
    commander.sendCommandSetGlobalOriginNonBlocking(
        target_system=targetSystem, target_component=targetComponent, lat=3, lon=3, alt=4)
    # Want to get back GPS_GLOBAL_ORIGIN

    # Test send
    time.sleep(18)


if testMAV_CMD_PREFLIGHT_REBOOT_SHUTDOWN:
    # def sendCommandRebootShutdown(self, target_system, target_component, autopilot = 0, companion = 0, component = 0, component_id = 0, force = False, camera_id = -1, connection=None, senderType=0):
    # Testing send reboot for autopilot without forcing
    commander.sendCommandRebootShutdown(
        connection=connection, target_system=targetSystem, target_component=targetComponent, autopilot=1)
    time.sleep(5)
    # Testing send reboot for autopilot with forcing
    commander.sendCommandRebootShutdown(
        connection=connection, target_system=targetSystem, target_component=targetComponent, autopilot=1, force=True)
    time.sleep(10)


if testMAV_CMD_DO_SET_MODE:
    print("\ntestMAV_CMD_DO_SET_MODE")

    # From \src\modules\commander\px4_custom_mode.h
    # PX4 custom mode definitions
    PX4_CUSTOM_MAIN_MODE_MANUAL = 1
    PX4_CUSTOM_MAIN_MODE_ALTCTL = 2
    PX4_CUSTOM_MAIN_MODE_POSCTL = 3
    PX4_CUSTOM_MAIN_MODE_AUTO = 4
    PX4_CUSTOM_MAIN_MODE_ACRO = 5
    PX4_CUSTOM_MAIN_MODE_OFFBOARD = 6
    PX4_CUSTOM_MAIN_MODE_STABILIZED = 7
    PX4_CUSTOM_MAIN_MODE_RATTITUDE_LEGACY = 8
    PX4_CUSTOM_MAIN_MODE_SIMPLE = 9  # reserved
    PX4_CUSTOM_MAIN_MODE_TERMINATION = 10

    # PX4 custom auto sub-mode definitions
    PX4_CUSTOM_SUB_MODE_AUTO_READY = 1
    PX4_CUSTOM_SUB_MODE_AUTO_TAKEOFF = 2
    PX4_CUSTOM_SUB_MODE_AUTO_LOITER = 3
    PX4_CUSTOM_SUB_MODE_AUTO_MISSION = 4
    PX4_CUSTOM_SUB_MODE_AUTO_RTL = 5
    PX4_CUSTOM_SUB_MODE_AUTO_LAND = 6
    PX4_CUSTOM_SUB_MODE_AUTO_RESERVED_DO_NOT_USE = 7
    PX4_CUSTOM_SUB_MODE_AUTO_FOLLOW_TARGET = 8
    PX4_CUSTOM_SUB_MODE_AUTO_PRECLAND = 9
    PX4_CUSTOM_SUB_MODE_AUTO_VTOL_TAKEOFF = 10
    PX4_CUSTOM_SUB_MODE_EXTERNAL1 = 11
    PX4_CUSTOM_SUB_MODE_EXTERNAL2 = 12
    PX4_CUSTOM_SUB_MODE_EXTERNAL3 = 13
    PX4_CUSTOM_SUB_MODE_EXTERNAL4 = 14
    PX4_CUSTOM_SUB_MODE_EXTERNAL5 = 15
    PX4_CUSTOM_SUB_MODE_EXTERNAL6 = 16
    PX4_CUSTOM_SUB_MODE_EXTERNAL7 = 17
    PX4_CUSTOM_SUB_MODE_EXTERNAL8 = 18,

    # From mavlink
    MAV_MODE_FLAG_CUSTOM_MODE_ENABLED = 0b00000001
    MAV_MODE_FLAG_TEST_ENABLED = 0b00000010
    MAV_MODE_FLAG_AUTO_ENABLED = 0b00000100
    MAV_MODE_FLAG_GUIDED_ENABLED = 0b00001000
    MAV_MODE_FLAG_STABILIZE_ENABLED = 0b00010000
    MAV_MODE_FLAG_HIL_ENABLED = 0b00100000
    MAV_MODE_FLAG_MANUAL_INPUT_ENABLED = 0b01000000
    MAV_MODE_FLAG_SAFETY_ARMED = 0b10000000

    # from commander.cpp interpretation of mode requirements.
    auto_mode_flags = MAV_MODE_FLAG_AUTO_ENABLED | MAV_MODE_FLAG_STABILIZE_ENABLED | MAV_MODE_FLAG_GUIDED_ENABLED
    custom_auto_mode_flags = MAV_MODE_FLAG_CUSTOM_MODE_ENABLED | auto_mode_flags
    manual_mode_flags = MAV_MODE_FLAG_CUSTOM_MODE_ENABLED | MAV_MODE_FLAG_MANUAL_INPUT_ENABLED
    manual_mode_stabilize_flags = MAV_MODE_FLAG_CUSTOM_MODE_ENABLED | MAV_MODE_FLAG_STABILIZE_ENABLED | MAV_MODE_FLAG_MANUAL_INPUT_ENABLED

    map_modes = {"MANUAL":        (manual_mode_stabilize_flags, PX4_CUSTOM_MAIN_MODE_MANUAL, 0),
                 "STABILIZED":    (manual_mode_stabilize_flags, PX4_CUSTOM_MAIN_MODE_STABILIZED, 0),
                 "ACRO":          (manual_mode_flags, PX4_CUSTOM_MAIN_MODE_ACRO, 0),
                 "ALTCTL":        (manual_mode_stabilize_flags, PX4_CUSTOM_MAIN_MODE_ALTCTL, 0),
                 "POSCTL":        (manual_mode_stabilize_flags, PX4_CUSTOM_MAIN_MODE_POSCTL, 0),
                 "LOITER":        (custom_auto_mode_flags, PX4_CUSTOM_MAIN_MODE_AUTO, PX4_CUSTOM_SUB_MODE_AUTO_LOITER),
                 "MISSION":       (custom_auto_mode_flags, PX4_CUSTOM_MAIN_MODE_AUTO, PX4_CUSTOM_SUB_MODE_AUTO_MISSION),
                 "RTL":           (custom_auto_mode_flags, PX4_CUSTOM_MAIN_MODE_AUTO, PX4_CUSTOM_SUB_MODE_AUTO_RTL),
                 "LAND":          (custom_auto_mode_flags, PX4_CUSTOM_MAIN_MODE_AUTO, PX4_CUSTOM_SUB_MODE_AUTO_LAND),
                 "FOLLOWME":      (custom_auto_mode_flags, PX4_CUSTOM_MAIN_MODE_AUTO, PX4_CUSTOM_SUB_MODE_AUTO_FOLLOW_TARGET),
                 "OFFBOARD":      (custom_auto_mode_flags, PX4_CUSTOM_MAIN_MODE_OFFBOARD, 0),
                 "TAKEOFF":       (custom_auto_mode_flags, PX4_CUSTOM_MAIN_MODE_AUTO, PX4_CUSTOM_SUB_MODE_AUTO_TAKEOFF)}


    print("\nSwitching to MANUAL mode")
    target_mode_name = 'MANUAL'
    base_mode, target_custom_mode_main, target_custom_sub_mode_auto = map_modes.get(
        target_mode_name)
    commander.sendCommandSetModeNonBlocking(target_system=targetSystem, target_component=targetComponent,
                                            base_mode=base_mode, custom_mode=target_custom_mode_main, custom_submode=target_custom_sub_mode_auto)
    time.sleep(6)

    target_mode_name = 'TAKEOFF'
    base_mode, target_custom_mode_main, target_custom_sub_mode_auto = map_modes.get(
        target_mode_name)
    commander.sendCommandSetModeNonBlocking(target_system=targetSystem, target_component=targetComponent,
                                            base_mode=base_mode, custom_mode=target_custom_mode_main, custom_submode=target_custom_sub_mode_auto)
    time.sleep(6)

    target_mode_name = 'MISSION'
    base_mode, target_custom_mode_main, target_custom_sub_mode_auto = map_modes.get(
        target_mode_name)
    commander.sendCommandSetModeNonBlocking(target_system=targetSystem, target_component=targetComponent,
                                            base_mode=base_mode, custom_mode=target_custom_mode_main, custom_submode=target_custom_sub_mode_auto)
    time.sleep(6)

    target_mode_name = 'OFFBOARD'
    base_mode, target_custom_mode_main, target_custom_sub_mode_auto = map_modes.get(
        target_mode_name)
    commander.sendCommandSetModeNonBlocking(target_system=targetSystem, target_component=targetComponent,
                                            base_mode=base_mode, custom_mode=target_custom_mode_main, custom_submode=target_custom_sub_mode_auto)
    time.sleep(6)

    target_mode_name = 'LOITER'
    base_mode, target_custom_mode_main, target_custom_sub_mode_auto = map_modes.get(
        target_mode_name)
    commander.sendCommandSetModeNonBlocking(target_system=targetSystem, target_component=targetComponent,
                                            base_mode=base_mode, custom_mode=target_custom_mode_main, custom_submode=target_custom_sub_mode_auto)
    time.sleep(6)

    target_mode_name = 'POSCTL'
    base_mode, target_custom_mode_main, target_custom_sub_mode_auto = map_modes.get(
        target_mode_name)
    commander.sendCommandSetModeNonBlocking(target_system=targetSystem, target_component=targetComponent,
                                            base_mode=base_mode, custom_mode=target_custom_mode_main, custom_submode=target_custom_sub_mode_auto)
    time.sleep(6)




print("complete")
