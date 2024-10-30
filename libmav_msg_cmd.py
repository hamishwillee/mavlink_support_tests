"""
Run script to get data about supported messages and commands against target autopilot.
It is rough and ready. By default connects to connectionType (search).

Outputs useful lists like "commands that didn't response with whether they are supported or not.
"""

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



from mavdocs import XMLDialectInfo
#XMLDialectInfo really need to be able to specify path to this

mavlinkDocs = XMLDialectInfo(dialect='development')



#print(id_value_dict_MAV_TYPE)

# TODO The script to get data about APIs
# Want to be able to get handle to any enum using its enum name.
# Want to get any enum name from an enum value.
# Want to get any enum value from an enum name. (not as imp - can do in libmav)
# Want to be able to get list of all messages
# Want to be able to get list of all command names

# TODO
# Check unknown responses - i.e if we get a message we don't know. This is something PYMAV can detect.


# Create a message set from a mavlink xml file
#message_set = libmav.MessageSet('./mavlink/message_definitions/v1.0/common.xml')
#message_set = libmav.MessageSet('./mavlink/message_definitions/v1.0/ardupilotmega.xml')
message_set = libmav.MessageSet('./mavlink/message_definitions/v1.0/development.xml')

#Create a heartbeat message
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

#connectionType = 'px4wsl2_companion_udp_client'
connectionType = 'px4wsl2_companion_udp_server'
#connectionType = 'px4wsl2_normal_udp_client'
#connectionType = 'px4wsl2_normal_udp_server'

if connectionType == 'px4wsl2_companion_udp_client':
    connection_address = '172.19.48.140'
    connection_port = 14580 # Onboard, data rate: 4000000 B/s on udp port 14580 remote port 14540
    conn_physical = libmav.UDPClient(connection_address, connection_port)

if connectionType == 'px4wsl2_normal_udp_client':  #Normal, data rate: 4000000 B/s on udp port 18570 remote port 14550
    connection_address = '172.19.48.140'
    connection_port = 18570 #18570
    conn_physical = libmav.UDPClient(connection_address, connection_port)

if connectionType == 'px4wsl2_normal_udp_server':  #Normal, data rate: 4000000 B/s on udp port 18570 remote port 14550
    #connection_address = '172.19.48.140'
    connection_port = 14550 #18570
    conn_physical = libmav.UDPServer(connection_port)

if connectionType == 'px4wsl2_companion_udp_server':  #Normal, data rate: 4000000 B/s on udp port 18570 remote port 14550
    #connection_address = '172.19.48.140'
    connection_port = 14540 # Onboard, data rate: 4000000 B/s on udp port 14580 remote port 14540
    conn_physical = libmav.UDPServer(connection_port)

#INFO  [mavlink] mode:
#INFO  [mavlink] mode:

#elif connectionType == 'px4wsl2_companion':

# Connect to a UDP server
#APM work:
#connection_address = '127.0.0.1'
#connection_port = 14551 #note, # works UDP amp
#connection_port = 14550 #note, is int
#connection_port = 14550 # Works for PX4 UDP


#conn_physical = libmav.UDPServer(connection_port)

#conn_physical = libmav.UDPClient(connection_address, connection_port)
#conn_physical = libmav.TCPClient(connection_address, connection_port)
#conn_physical = libmav.UDPServer(connection_port)
#conn_physical = libmav.TCPServer(connection_port)

# inspect_object(conn_physical) # (a UDPServer)

conn_runtime = libmav.NetworkRuntime(message_set, heartbeat_message, conn_physical)

#inspect_object(conn_runtime) # (a NetworkRuntime)

connection = conn_runtime.await_connection(5000)
# connection = conn_runtime.await_connection(-1) - waits forever and you get stuck until is a connection
# connection = conn_runtime.await_connection(0) - "RuntimeError: Timeout while waiting for first connection

# inspect_object(connection) # (a Connection)
#inspect_object(connection.partner()) # (a Connection)

# inspect_object(connection.alive()) # (a Connection)

autopilotInfoAll = dict()


#identity_check_callback_handle = connection.add_message_callback(identityCheck)

class MAVLinkSupportInfo:
    def __init__(self):
        # Creating instance variables
        self.__accumulator = dict()
        self.__messages = dict() # The logged info about messages
        self.__commands = dict() # The logged info about commands
        self.__identity = dict()
        self.__first_timestamp = None
        self.__last_timestamp = None
        self.__new_message_timestamp = None
        self.__starting = True
        self.__no_message_change = True

        #Populate the commands with info about what we're interested in:
        allCommands = mavlinkDocs.getCommands()
        for name in allCommands.keys():
            self.__commands[name] = { 'name': name, 'id': allCommands[name]['value'], 'result': None, }


    def messageArrived(self, msg):

        self.identityCheck(msg) # Add code in to work out what autopilot we are talking to.

        # Discard messages if we haven't yet found an autopilot (or "not a GCS")
        if 'system_id' not in self.__identity:
            #print("Identity of system not yet known")
            return

        # Discard messages if from wrong type (ie "a GCS")
        if not self.__identity['system_id'] == msg.header.system_id:
            #print(f"Wrong system id: {msg.header.system_id}")
            return

        # Record timestamp of first message, time running, time since last new message
        self.__last_timestamp=time.monotonic()
        if not self.__first_timestamp:
            self.__first_timestamp=time.monotonic()

        timeRunning = self.__last_timestamp - self.__first_timestamp
        #print(f"timeRunning {timeRunning}")
        timeSinceLastNewMessage=0
        if self.__new_message_timestamp:
            timeSinceLastNewMessage = self.__last_timestamp - self.__new_message_timestamp

        if timeSinceLastNewMessage> 20:
            pass
            #print(f"No new messages: {timeSinceLastNewMessage}s")

        # After 30 s of run-time we clear the starting flag
        # This allows us to identify all the messages that arrive on first boot.
        if self.__starting and timeRunning > 30: # TODO Should set this to be passed in or global value
            #print(f"timeSinceLastNewMessage {timeSinceLastNewMessage}, timeRunning {timeRunning}")
            self.__starting = None


        # Log supported messages as they are received (this is the output version)
        # Add "initial" if we are running this in the intial state.
        messageName = msg.name
        if messageName not in self.__messages:
            self.__new_message_timestamp = self.__last_timestamp
            self.__messages[messageName]={}
            if self.__starting:
                self.__messages[messageName]["initial"] = True

        #messageName = msg.get_type() #pymav variant

        # Log messages as they are recieved
        # (this is a "working" repo of info used for stats, which we may clear at various points)
        if messageName not in self.__accumulator:
            first_timestamp=time.monotonic()
            self.__accumulator[messageName]={"count": 1, "first_timestamp": first_timestamp, "last_timestamp": first_timestamp, "maxHz": 0, "minHz": 1000000}
            if self.__no_message_change: #ie haven't started changing what gets streamed
                self.__accumulator[messageName]['initial']=True

            print(f'Acc: New Message: {messageName}')
        else:
            self.__accumulator[messageName]["count"]+=1
            last_timestamp = time.monotonic()
            timediff_last=last_timestamp-self.__accumulator[messageName]["last_timestamp"]
            #print(timediff_last)
            hz_last = 1 / timediff_last
            if hz_last > self.__accumulator[messageName]["maxHz"]:
                self.__accumulator[messageName]["maxHz"] = hz_last
            if hz_last < self.__accumulator[messageName]["minHz"]:
                self.__accumulator[messageName]["minHz"] = hz_last
            #TODO perhaps look at last values for packetloss?

            #print(hz_last)
            self.__accumulator[messageName]["hz_last"]=hz_last
            hz_avg = 1 / ((last_timestamp-self.__accumulator[msg.name]["first_timestamp"])/self.__accumulator[messageName]["count"])
            #print(hz_avg)
            self.__accumulator[messageName]["hz_avg"]=hz_avg # Across the whole queue
            #update the last timestamp
            self.__accumulator[messageName]["last_timestamp"]=time.monotonic()

            #Store some data
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
            #inspect_object(command_dict)
            #print(command_dict)
            #for key, field in command_dict.items():
            #   print(f"{key}: {field}")
            # get id from command
            command_id_in_ack = command_dict['command']
            #print(f"debug: command_id_in_ack: {command_id_in_ack}")
            command_name_for_ack = mavlinkDocs.getCommandName(command_id_in_ack)
            #pprint.pprint(command_name_for_ack)
            result_in_ack = command_dict['result']
            #result_name = mavlinkDocs.getEnumEntryNameFromId('MAV_RESULT', result_in_ack)
            command_supported = False if result_in_ack==3 else True



            if command_name_for_ack not in self.__commands:
                # We don't expect extra commands to be received than the ones we send.
                self.__commands[command_name_for_ack] = { 'name': command_name_for_ack, 'id': command_id_in_ack, 'result': command_supported, 'unexpected': True}
            else:
                if self.__commands[command_name_for_ack]['result'] is None:
                    self.__commands[command_name_for_ack]['result'] = command_supported
                else:
                    if self.__commands[command_name_for_ack]['result'] is not command_supported:
                        print(f"debug: ACK changed from supported to unsupported (or visa versa)!: {command_name_for_ack}")

            #pprint.pprint(self.__commands)

            #print(failHere)


    def identityCheck(self, msg):
        #todo - could also add sitl check etc
        #print(inspect_object(msg))
        #print(inspect_object(msg.header))

        #print(msg.name)
        if msg.name == "HEARTBEAT" and not 'autopilot' in self.__identity:
            #print(msg)
            message_dict = msg.to_dict()
            #print(message_dict)
            #inspect_object(msg)
            # do I want to store under 'identity" Do I want to store under component id? After all, I might have multiple components, systems in some cases?
            # I think I only want things that identify as an autopilot component for this. Should check component iD too just to see.

            autopilot_type = mavlinkDocs.getEnumEntryNameFromId('MAV_AUTOPILOT', message_dict['autopilot'])
            if 'MAV_AUTOPILOT_INVALID' == autopilot_type:
                print("ignore GCS")
                #TODO A MORE THOROUGH CHECK that locks to a component id.
                return

            self.__identity['system_id'] = msg.header.system_id
            self.__identity['component_id'] =msg.header.component_id

            self.__identity['autopilot'] = autopilot_type
            self.__identity['type'] = mavlinkDocs.getEnumEntryNameFromId('MAV_TYPE', message_dict['type'])
            print(self.__identity)
        if msg.name == "AUTOPILOT_VERSION" and not 'version' in self.__identity and 'autopilot' in self.__identity:
            message_dict = msg.to_dict()
            #print(message_dict)

            major_version = (message_dict['middleware_sw_version'] >> (8 * 3)) & 0xFF
            minor_version = (message_dict['middleware_sw_version'] >> (8 * 2)) & 0xFF
            patch_version = (message_dict['middleware_sw_version'] >> (8 * 1)) & 0xF
            self.__identity['version'] = f"{major_version}.{minor_version}.{patch_version}"
            print(self.__identity)

    def __round_to_nearest_standard_hz(self, value):
            # List of standard frequencies
        standard_frequencies = [100, 50, 40, 30, 20, 10, 5, 4, 3, 2, 1, 0.5, 0.33, 0.25, 0.2, 0.1, 0.02, 0.01]
        array = np.array(standard_frequencies)
        index = (np.abs(array - value)).argmin()
        standard_value = array[index]
        diff = np.abs(value - standard_value)/standard_value*100
        if value > 110 or value <0.006:
            print(f"val: {value} outside expected range (st_val: {standard_value})")
            pass
        if diff > 10:
            print(f"diff: {diff} (value different to standard value) - st_val: {standard_value}")
            pass
        return standard_value

    def getMessageCurrentHz(self, msgName):
        if "queue" not in self.__accumulator[msgName]:
            return None

        lastPeriod = self.__accumulator[msgName]["queue"][-1]
        lastFrequency = 1/lastPeriod

        timeDiffLastStamp = time.monotonic() - self.__accumulator[msgName]["last_timestamp"]
        ageOfLastMessage = timeDiffLastStamp/lastPeriod #More than 2 times measured period old we don't know actual
        #print(f"msgName: {msgName}, lastPeriod: {lastPeriod}, lastFrequency: {lastFrequency}, ageOfLastMessage: {ageOfLastMessage}")
        if ageOfLastMessage > 2:
            return None
        else:
            return lastFrequency




    def getMessageEstHz(self, msgName):
        """
        Gets the std and av Hz of message as an object { std, av }, or None if not streamed
        """
        #print(f'msg: {msgName}')
        totaltimeAllMessages = self.__last_timestamp - self.__first_timestamp
        # Function to round to the nearest standard frequency

        if "queue" not in self.__accumulator[msgName]:
            return None

        queueList=self.__accumulator[msgName]["queue"]
        averagePeriod = np.mean(queueList)


        roundedHzAv = self.__round_to_nearest_standard_hz(1/averagePeriod)
        roundedPeriodAv = 1/roundedHzAv

        maxHz = self.__accumulator[msgName]["maxHz"]
        minHz = self.__accumulator[msgName]["minHz"]
        avMaxMin = 100* (maxHz - minHz)/maxHz

        if avMaxMin < 20:
            return { "std": roundedHzAv, "av": round(1/averagePeriod,3) }


        #print(f"mean (T): {averagePeriod}, (Hz): {1/averagePeriod}, rndHz: {round(1/averagePeriod)}, rndstd: {roundedHzAv}, maxHz: {maxHz}, minHz: {minHz}, avMaxMin: {avMaxMin}")

        #median = np.median(queueList)
        #print(f"median (T): {median}, (Hz): {1/median}, rndHz: {round(1/median)}, rndstd: {1/self.__round_to_nearest_standard_hz(median)}")

        #Get mode but assume values are about right
        #mode_hz_rounded_values = [round(1/value) for value in queueList]
        #mode = np.bincount(mode_hz_rounded_values).argmax()
        #print(f"mode (T): {mode}, (Hz) {1/mode}")

        #std_dev = np.std(queueList)  # For population standard deviation
        #print(f"std_dev {std_dev}")

        countIfStreamed= totaltimeAllMessages // roundedPeriodAv # whole number part
        count = self.__accumulator[msgName]['count']
        streamTest = (abs(countIfStreamed-count)/countIfStreamed)*100

        print(f"{msgName} MaybeNotStreamed: streamed% {streamTest},  avMaxMin: {avMaxMin}, Hz: {1/averagePeriod})")

        """
        if streamTest < 50:
            return roundedHzAv
        #print(f"streamed% {streamTest} (count: {count}, est: {countIfStreamed}, Hz: {1/averagePeriod})")
        """

        return None

        ##messageAccumulator[messageName]["hz_avg_acc_last_rounded_mode"] = round(1/average)

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

        return {'supported': true_commands, 'unsupported':false_commands, 'unknown': none_commands}



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
#all_messages_callback_handle = connection.add_message_callback(lambda msg: print(f'Yay {msg.name}'))
all_messages_callback_handle = connection.add_message_callback(msgInfo.messageArrived)



def commandSenderBlocking(connection, commandName, target_system, target_component, senderType=0, param1=0, param2=0, param3=0, param4=0, param5=0, param6=0, param7=0):
    """
    Sends a command as either a COMMAND_LONG or COMMAND_INT, based on the type.

    senderType (int): The type of sender - 0 is command long, 1 is command int.

    Args
        connection (Connection): The connection object to use for sending
        commandName (str): Name of command to send (is converted internally to an ID)
        target_system (int): MAVLink system ID
        target_component (int): MAVLink component ID
        senderType (int): 0 for command_long (default), 1 for command_int.
        param1 (float): Value to send in param 1
        param2 (float): Value to send in param 2
        param3 (float): Value to send in param 3
        param4 (float): Value to send in param 4
        param5 (float): Value to send in param 5
        param6 (float): Value to send in param 6
        param7 (float): Value to send in param 7

    """
    # create our command long message.

    if senderType==0:
        print('commandSenderBlocking: ' + commandName + "(COMMAND_LONG)")
        command_sender = message_set.create('COMMAND_LONG')
        command_sender['param5']=param5;
        command_sender['param6']=param6;
        command_sender['param7']=param7;
    else:
        print('commandSenderBlocking: ' + commandName + "(COMMAND_INT)")
        command_sender = message_set.create('COMMAND_INT')
        command_sender['x']=param5;
        command_sender['y']=param6;
        command_sender['z']=param7;

    #inspect_object(command_sender)
    commandId = message_set.enum(commandName)
    #print("commandName")
    #inspect_object(commandId)
    command_sender['command']=commandId;
    command_sender['param1']=param1;
    command_sender['param2']=param2;
    command_sender['param3']=param3;
    command_sender['param4']=param4;

    command_sender['target_component']=target_component;
    command_sender['target_system']=target_component;

    #print("exp")
    expectation = connection.expect("COMMAND_ACK")
    #inspect_object(expectation) # (a Connection)
    """
    Public API: _ExpectationWrapper
    """
    print("send")
    connection.send(command_sender)
    print("recv in 10s")
    command_ack = connection.receive(expectation, 5000) # With timeout, 3 seconds - should that be a param?


    #inspect_object(command_ack)
    #inspect_object(command_ack.header)
    #inspect_object(command_ack.type)
    #print(command_ack["command"])
    #print(command_ack["result"])

    lookupResult = {
        0: "MAV_RESULT_ACCEPTED",
        1: "MAV_RESULT_TEMPORARILY_REJECTED",
        2: "MAV_RESULT_DENIED",
        3: "MAV_RESULT_UNSUPPORTED",
        4: "MAV_RESULT_FAILED",
        5: "MAV_RESULT_IN_PROGRESS",
        6: "MAV_RESULT_CANCELLED",
        7: "MAV_RESULT_COMMAND_LONG_ONLY",
        8: "MAV_RESULT_COMMAND_INT_ONLY",
        9: "MAV_RESULT_COMMAND_UNSUPPORTED_MAV_FRAME",
    }
    print('COMMAND_ACK: ' + lookupResult[command_ack["result"]])




# Gobal dict of command acks we are waiting on
# Along with the time when sent
ackWaiting = dict()

import threading
# Global variable to keep track of the timer
timer = None

def set_interval(func, sec):
    #print('debug: set_interval() called')
    global timer

    def func_wrapper():
        global timer
        if ackWaiting:
            set_interval(func, sec)
            func()
        else:
            #print(" debug: No ACKs waiting, stopping the timer.")
            timer = None

    if timer is None:
        #print(" debug: timer stopped - starting")
        timer = threading.Timer(sec, func_wrapper)
        timer.start()
    else:
        #print(" debug: timer running still")
        pass

def checkForAcks():
    print('checkForAcks() called')
    if ackWaiting:
        for key, value in ackWaiting.items():
            if time.time() > value + 5:
                # it's been sitting there too long
                print(f"Command {key} too slow")
                del ackWaiting[key]
                # Some kind of callback
            else:
                print(f"Key: {key} Rem {time.time() - value}: still good")
    else:
        print("NO ACKS WAITING")
        pass


def ackArrived(msg):
    lookupResult = {
    0: "MAV_RESULT_ACCEPTED",
    1: "MAV_RESULT_TEMPORARILY_REJECTED",
    2: "MAV_RESULT_DENIED",
    3: "MAV_RESULT_UNSUPPORTED",
    4: "MAV_RESULT_FAILED",
    5: "MAV_RESULT_IN_PROGRESS",
    6: "MAV_RESULT_CANCELLED",
    7: "MAV_RESULT_COMMAND_LONG_ONLY",
    8: "MAV_RESULT_COMMAND_INT_ONLY",
    9: "MAV_RESULT_COMMAND_UNSUPPORTED_MAV_FRAME",
    }
    #print(msg.name)
    if msg.name == "COMMAND_ACK":

        #print(ackWaiting)
        print(f'COMMAND_ACK: ({msg["command"]}): {lookupResult[msg["result"]]} (prog: {msg["progress"]}, resparm2: {msg["result_param2"]})')
        if msg["command"] in ackWaiting:
            #print('3')
            #print(ackWaiting)
            del ackWaiting[msg["command"]]
            #print('4')
            #print(ackWaiting)
            #if not ackWaiting:
            #    #print("Not waiting on acks")
            #    #print(ackWaiting)
            #    connection.remove_message_callback(command_ack_callback_handle)

        else:
            print(f"Unexpected ack: {msg['command']}")
    else:
        pass
        #print(msg.name)


command_ack_callback_handle = connection.add_message_callback(ackArrived)


def commandSenderNonBlocking(connection, commandName, target_system, target_component, senderType=0, param1=0, param2=0, param3=0, param4=0, param5=0, param6=0, param7=0):
    """
    Sends a command as either a COMMAND_LONG or COMMAND_INT, based on the type.

    senderType (int): The type of sender - 0 is command long, 1 is command int.

    Args
        connection (Connection): The connection object to use for sending
        commandName (str): Name of command to send (is converted internally to an ID)
        target_system (int): MAVLink system ID
        target_component (int): MAVLink component ID
        senderType (int): 0 for command_long (default), 1 for command_int.
        param1 (float): Value to send in param 1
        param2 (float): Value to send in param 2
        param3 (float): Value to send in param 3
        param4 (float): Value to send in param 4
        param5 (float): Value to send in param 5
        param6 (float): Value to send in param 6
        param7 (float): Value to send in param 7

    """

    # create our command long message.

    if senderType==0: #command long
        print('commandSenderNonBlocking: ' + commandName + "(COMMAND_LONG)")
        command_sender = message_set.create('COMMAND_LONG')
        command_sender['param5']=param5
        command_sender['param6']=param6
        command_sender['param7']=param7
    else:
        print('commandSenderNonBlocking: ' + commandName + "(COMMAND_INT)")
        command_sender = message_set.create('COMMAND_INT')
        command_sender['x'] = param5
        command_sender['y'] = param6
        command_sender['z'] = param7

    #inspect_object(command_sender)
    commandId = message_set.enum(commandName)
    #print("commandName")
    #inspect_object(commandId)
    command_sender['command']=commandId
    command_sender['param1']=param1
    command_sender['param2']=param2
    command_sender['param3']=param3
    command_sender['param4']=param4

    command_sender['target_component']=target_component
    command_sender['target_system']=target_component

    #print("exp")
    #expectation = connection.expect("COMMAND_ACK")
    #inspect_object(expectation) # (a Connection)
    print(f"Sending: {commandName} ({commandId})")
    ackWaiting[commandId] = time.time()
    set_interval(checkForAcks, 1)

    connection.send(command_sender)
    #print("waiting to recv in ?s")
    #command_ack = connection.receive(expectation, 5000) # With timeout, 3 seconds - should that be a param?
    #time.sleep(5)
    #if ackReceived:
    #    print("acc rec")
    #else:
    #    print("acc_not_rec timout")
    #    connection.remove_message_callback(command_ack_callback_handle)


def setMessageIntervalBlocking(connection, target_system, target_component, target_message, interval, senderType=0):
    """
    Set message interval for specified message in us.

    Args
        connection (Connection): The connection object to use for sending
        target_system (int): MAVLink system ID
        target_component (int): MAVLink component ID
        target_message (string): String name for message for which interval is set.
        interval (int): Interval between messages of type target_message in us. -1 to disable.
        senderType (int): 0 for command_long (default), 1 for command_int.
    """
    targetMessageId = message_set.id_for_message(target_message)
    commandSenderBlocking(connection=connection, senderType=senderType, commandName='MAV_CMD_SET_MESSAGE_INTERVAL', target_system=target_system, target_component=target_component, param1=targetMessageId, param2=interval)

    #Note, target id of command ACK is   target_component: 97, target_system: 97. Is that what we are by default?


def sendCommandRequestMessageNonBlocking(connection, target_system, target_component, target_message_id, index_id, param3=0, param4=0, param5=0, param6=0, param7=0,senderType=0):
    """
    Request a message.

    Args
        connection (Connection): The connection object to use for sending
        target_system (int): MAVLink system ID
        target_component (int): MAVLink component ID
        senderType (int): 0 for command_long (default), 1 for command_int.

        1: (Message ID)	The MAVLink message ID of the requested message.	min: 0 max: 16777215 inc: 1
        2: Use for index ID, if required. Otherwise, the use of this parameter (if any) must be defined in the requested message. By default assumed not used (0).
        3: The use of this parameter (if any), must be defined in the requested message. By default assumed not used (0).
        4: The use of this parameter (if any), must be defined in the requested message. By default assumed not used (0).
        5: The use of this parameter (if any), must be defined in the requested message. By default assumed not used (0).
        6: The use of this parameter (if any), must be defined in the requested message. By default assumed not used (0).
        7: Target address for requested message (if message has target address fields). 0: Flight-stack default, 1: address of requestor, 2: broadcast.

    """

    commandSenderNonBlocking(connection=connection, senderType=senderType, commandName='MAV_CMD_REQUEST_MESSAGE', target_system=target_system, target_component=target_component, param1=target_message_id, param2=index_id, param3=param3, param4=param4, param5=param4, param6=param6, param7=param7)



def sendCommandMessageIntervalNonBlocking(connection, target_system, target_component, target_message_id, interval, response_target=0, param3=0, param4=0, param5=0, param6=0, param7=0,senderType=0):
    """
    Set message interval for specified message in us.

    Args
        connection (Connection): The connection object to use for sending
        target_system (int): MAVLink system ID
        target_component (int): MAVLink component ID
        target_message (string): String name for message for which interval is set.
        interval (int): Interval between messages of type target_message in us. -1 to disable. 0: request default rate (which may be zero).
        senderType (int): 0 for command_long (default), 1 for command_int.
        responseTarget: Target address for requested message (if message has target address fields). 0: Flight-stack default, 1: address of requestor, 2: broadcast.
    """

    commandSenderNonBlocking(connection=connection, senderType=senderType, commandName='MAV_CMD_SET_MESSAGE_INTERVAL', target_system=target_system, target_component=target_component, param1=target_message_id, param2=interval, param3=param3, param4=param4, param5=param4, param6=param6, param7=param7)



def setCommandTakeoff(connection, target_system, target_component, pitch, yaw, lat, lon, alt, senderType=0):
    """
    Set message interval for specified message in us.

    Args
        connection (Connection): The connection object to use for sending
        target_system (int): MAVLink system ID
        target_component (int): MAVLink component ID
        senderType (int): 0 for command_long (default), 1 for command_int.

        1: Pitch	Minimum pitch (if airspeed sensor present), desired pitch without sensor	deg
        2	Empty
        3	Empty
        4: Yaw	Yaw angle (if magnetometer present), ignored without magnetometer. NaN to use the current system yaw heading mode (e.g. yaw towards next waypoint, yaw to home, etc.).	deg
        5: Latitude	Latitude
        6: Longitude	Longitude
        7: Altitude	Altitude

    """

    #commandSenderBlocking(connection=connection, senderType=senderType, commandName='MAV_CMD_NAV_TAKEOFF', target_system=target_system, target_component=target_component, param1=pitch, param4=yaw, param5=lat, param6=lon, param7=alt)
    commandSenderNonBlocking(connection=connection, senderType=senderType, commandName='MAV_CMD_NAV_TAKEOFF', target_system=target_system, target_component=target_component, param1=pitch, param4=yaw, param5=lat, param6=lon, param7=alt)

    #Note, target id of command ACK is   target_component: 97, target_system: 97. Is that what we are by default?
    #print('setCommandTakeoff() fell through')


def setCommandArm(connection, target_system, target_component, senderType=0):
    """
    Set message interval for specified message in us.

    Args
        connection (Connection): The connection object to use for sending
        target_system (int): MAVLink system ID
        target_component (int): MAVLink component ID
        senderType (int): 0 for command_long (default), 1 for command_int.

        1: Pitch	Minimum pitch (if airspeed sensor present), desired pitch without sensor	deg
        2	Force = 1


    """

    #commandSenderBlocking(connection=connection, senderType=senderType, commandName='MAV_CMD_NAV_TAKEOFF', target_system=target_system, target_component=target_component, param1=pitch, param4=yaw, param5=lat, param6=lon, param7=alt)
    commandSenderNonBlocking(connection=connection, senderType=senderType, commandName='MAV_CMD_COMPONENT_ARM_DISARM', target_system=target_system, target_component=target_component, param1=1)

    #Note, target id of command ACK is   target_component: 97, target_system: 97. Is that what we are by default?
    #print('setCommandArm() fell through')

def sendTestCommands():
    print("sleep 1 before takeoff and arm")
    time.sleep(1)
    targetSystem = 1
    targetComponent = message_set.enum("MAV_COMP_ID_AUTOPILOT1")

    # Try same command with command int
    setCommandTakeoff(connection=connection, target_system=targetSystem, target_component=targetComponent, pitch=0, yaw=0, lat=0, lon=0, alt=500, senderType=1)
    setCommandArm(connection=connection, target_system=targetSystem, target_component=targetComponent, senderType=1)

    print("sleep 5 after takeoff version 1")
    time.sleep(5)
    print("sleep v1 end")

    # Try the nav_takeoff command
    setCommandTakeoff(connection=connection, target_system=targetSystem, target_component=targetComponent, pitch=0, yaw=0, lat=0, lon=0, alt=500, senderType=0)
    setCommandArm(connection=connection, target_system=targetSystem, target_component=targetComponent, senderType=0)
    print("sleep 5 after takeoff version 2")
    time.sleep(5)
    print("sleep v2 end")

    #print("start blocking command")
    #setMessageIntervalBlocking(connection=connection, target_system=targetSystem, target_component=targetComponent, target_message=targetMessage, interval=10000, senderType=0)
    #print("end blocking command")
    # Try same command with command int
    #time.sleep(5)
    #setMessageIntervalBlocking(connection=connection, target_system=targetSystem, target_component=targetComponent, target_message=targetMessage, interval=10000, senderType=1)

    #time.sleep(2) # TODO Did we get command_ACK in log? Yes!

    #messageAccumulator= dict()
    #time.sleep(5)
    #pprint.pprint(messageAccumulator)


def sendAllCommands():
    # Sends all commands, one after another with a space between. We're just trying to work out if supported or not.
    # Get all commandds
    targetSystem = 1
    targetComponent = message_set.enum("MAV_COMP_ID_AUTOPILOT1")
    allCommands = mavlinkDocs.getCommands()
    for name in allCommands.keys():
        print(f"Sending: {name}")
        commandSenderNonBlocking(connection=connection, commandName=name, target_system=targetSystem, target_component=targetComponent)
        time.sleep(1)



# The code that does stuff



# Start with wait after connecting to accumulate default_streamed messages.
accumulate_time = 10
print(f"Accumulating default streamed messages ({accumulate_time})")
time.sleep(accumulate_time)
msgInfo.__no_message_change = False #After this we might start collecting some new messages, such as autopilot version
msgInfo.populateMessageInfo()



# request more identity info
# Note, done after the accumulator part, because it isn't streamed.
# Todo add enough info to determine what is really streamed and what is not.
print("Getting autopilot version ... - 5s")

targetSystem = 1
targetComponent = message_set.enum("MAV_COMP_ID_AUTOPILOT1") # TODO We should get from our connection.
request_message_id = message_set.id_for_message('AUTOPILOT_VERSION')
sendCommandRequestMessageNonBlocking(connection=connection, target_system=targetSystem, target_component=targetComponent, target_message_id=request_message_id, index_id=0)
time.sleep(3)



# connection.remove_message_callback(all_messages_callback_handle) # leave running - is handy
print("end first part")

## Send all commands (to test ACKS)
sendAllCommands()
# TODO see if we get ack back for all the original messages.



#pprint.pprint(messageAccumulator)

# Testing streaming of battery messages
request_message_id = message_set.id_for_message('BATTERY_STATUS')
sendCommandMessageIntervalNonBlocking(connection=connection, target_system=targetSystem, target_component=targetComponent, target_message_id=request_message_id, interval=0)
time.sleep(15)

#sendTestCommands()

if ackWaiting:
    print(ackWaiting)






#print(autopilotInfoAll)
print("complete")

#print(msgInfo.__identity)

pprint.pprint(msgInfo.getMessageInfo())
pprint.pprint(msgInfo.getCommandSupportInfoSorted())

#pprint.pprint(msgInfo.getCommandInfo())


#pprint.pprint(messageInfo)
