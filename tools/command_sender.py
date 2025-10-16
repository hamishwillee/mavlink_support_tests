"""
Run script to get data about supported messages and commands against target autopilot.
It is rough and ready. By default connects to connectionType (search).

Outputs useful lists like "commands that didn't response with whether they are supported or not.
"""

import libmav
import time
import pprint

# from collections import deque
# import numpy as np
import threading
import math  # for NaN


INT32_MAX = 2147483647


def inspect_object(object):
    print(f"Public API: {type(object).__name__}")
    for attr in dir(object):
        if not attr.startswith("__"):
            value = getattr(object, attr)
            print(f"  {attr} (Value: {value}) (type: {type(value)})")


class CommandSender:
    def __init__(self, mav_component):
        print(f"debug: CommandSender.__init__")
        self.mav_component = mav_component
        self.mav_connection = self.mav_component.mav_connection
        self.connection = self.mav_connection.connection
        self.docs = self.mav_connection.docs
        self.message_set = self.mav_connection.message_set

        self.own_system_id = self.mav_connection.own_system_id
        self.own_component_id = self.mav_connection.own_component_id
        self.target_system_id = self.mav_component.target_system_id  # default to None
        self.target_component_id = self.mav_component.target_component_id

        self.mav_connection.add_threaded_message_callback(self.ackArrived)

        # dict of command acks we are waiting on + the time when sent
        self.ackWaiting = dict()
        # Variable to keep track of the timer
        self.timer = None

        #print("debug: EXIT CommandSender.__init__() ")

    def set_interval(self, func, sec):
        #print(f"debug: set_interval() called with sec={sec}")

        def func_wrapper():
            if self.ackWaiting:
                print(" debug: func_wrapper: true - calling func() and rescheduling")
                func()  # Call the actual function first
                # Reschedule the timer
                self.timer = threading.Timer(sec, func_wrapper)
                self.timer.start()
            else:
                print(" debug: func_wrapper: false/else - no ACKs, stopping timer")
                # If no ACKs are waiting, stop the timer by not rescheduling
                self.timer = None  # Clear the timer reference

        # Only start a new timer if one isn't already running
        if self.timer is None:
            print(" debug: timer not running - starting initial timer")
            self.timer = threading.Timer(sec, func_wrapper)
            self.timer.start()
        else:
            print(
                " debug: timer already running, not starting a new one from set_interval."
            )

    def checkForAcks(self):
        print(f"debug:checkForAcks() called: {self.ackWaiting}")
        if self.ackWaiting:
            delkey = []
            for key, value in self.ackWaiting.items():
                # print(f"Debug: Key: {key} Value: {value}")
                if time.time() > value["time"] + 5:
                    # it's been sitting there too long
                    print(f"Command {key} too slow")
                    # del self.ackWaiting[key]
                    delkey.append(key)
                    # TODO: Some kind of callback and perhaps resend.
                else:
                    print(f"Key: {key} Rem {time.time() - value['time']}: still good")
                    pass
            for key in delkey:
                del self.ackWaiting[key]

        else:
            print("NO ACKS WAITING")
            pass

    def ackArrived(self, msg):
        if msg.name != "COMMAND_ACK":
            return  # Not a command ack, so ignore it.

        lookupResult = {  # TODO change to a lookup from the docs library.
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

        # print(msg.name)

        # Any command ack arrives we should check it is intended for us based on command target id.
        # self.own_system_id = own_system_id # The system ID of this system running the tests/sending commands
        # self.own_component_id = own_component_id  # The component ID of this system running the tests/sending commands
        message_dict = msg.to_dict()

        # Reject any messages intended for other systems (not broadcast and has non-matching id)
        # TODO maybe also reject for other components if targetted.
        target_system = message_dict.get("target_system", 0)
        if target_system != 0 and target_system != self.own_system_id:
            print(f"not matching system: {target_system}, {self.own_system_id} ")
            return

        # Reject any messages intended for other component (not broadcast and has non-matching id)
        if "target_component" not in message_dict:
            # broadcast system message.
            pass
        elif message_dict["target_component"] == 0:
            # broadcast system message.
            pass
        elif message_dict["target_component"] != self.own_component_id:
            print(
                f"not matching component: {message_dict['target_component']}, {self.own_component_id} "
            )
            return
        # Note for above, we now have to consider how we deal with broadcast

        print(message_dict)
        # inspect_object(msg)

        # print(self.ackWaiting)
        if msg["command"] in self.ackWaiting:
            ackedCommand = self.ackWaiting[msg["command"]]
            # print('1x')

            commandName = self.docs.getCommandName(msg["command"])
            # print(commandName)
            # print('2x')
            # print(f'xxxxCOMMAND_ACK: ({msg["command"]}): {lookupResult[msg["result"]]} (prog: {msg["progress"]}, resparm2: {msg["result_param2"]})')
            # print(ackedCommand)
            if ackedCommand["callback"]:
                # print('2x_a')
                # Callback the result
                ackResultName = self.docs.getEnumEntryNameFromId(
                    "MAV_RESULT", msg["result"]
                )
                ackedCommand["callback"](
                    msg["command"],
                    commandName,
                    ackResultName,
                    message_dict,
                    ackedCommand,
                )
                # print('2x_b')
                # print('3x')
                # print(self.ackWaiting[msg["command"]])
                del self.ackWaiting[msg["command"]]
                print("4x")

            else:
                print(f"xx Unexpected ack in CommandSender: {msg['command']}")

    def defaultCallback(command, commandName, result, ack_message, ackedCommand):
        # print(f'defcallbackCOMMAND_ACK: ({command}): {result} (prog: {message["progress"]}, resparm2: {message["result_param2"]})')
        print(
            f"defaultCallback:COMMAND_ACK: ({commandName}): {result} (ACK: {ack_message}), originalCommand: {ackedCommand}"
        )


    def commandSenderNonBlocking(
        self,
        commandName,
        target_system=None,
        target_component=None,
        connection=None,
        senderType=1,
        param1=math.nan,
        param2=math.nan,
        param3=math.nan,
        param4=math.nan,
        param5=INT32_MAX,
        param6=INT32_MAX,
        param7=math.nan,
        callback=defaultCallback,
    ):
        # TODO - handle wrong sender type callback?
        # Record sending of deprecated /wip type?
        # Record receiving of deprecated/WIP message.
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
            param5 (int): Value to send in param 5 (default INT32_MAX)
            param6 (int): Value to send in param 6 (default INT32_MAX)
            param7 (float): Value to send in param 7

        """
        print(f"debug: commandSenderNonBlocking()")
        # Set value of connection to be self.connection if it is passed in as None.
        # (Instance variables cant be function defaults)

        target_system = target_system if target_system else self.target_system_id
        target_component = (
            target_component if target_component else self.target_component_id
        )
        usedConnection = connection if connection else self.connection

        sent_command = {
            "commandName": commandName,
            "target_system": target_system,
            "target_component": target_component,
            "senderType": senderType,
            "param1": param1,
            "param2": param2,
            "param3": param3,
            "param4": param4,
            "param5": param5,
            "param6": param6,
            "param7": param7,
            "callback": callback,
        }

        # create our command long message.

        if senderType == 0:  # command long
            print("commandSenderNonBlocking: " + commandName + "(COMMAND_LONG)")
            command_sender = self.message_set.create("COMMAND_LONG")
            command_sender["param5"] = param5
            command_sender["param6"] = param6
            command_sender["param7"] = param7
        else:
            print("commandSenderNonBlocking: " + commandName + "(COMMAND_INT)")
            command_sender = self.message_set.create("COMMAND_INT")
            command_sender["x"] = param5
            command_sender["y"] = param6
            command_sender["z"] = param7

        # inspect_object(command_sender)
        commandId = self.message_set.enum(commandName)
        # print("commandName")
        # inspect_object(commandId)
        command_sender["command"] = commandId
        command_sender["param1"] = param1
        command_sender["param2"] = param2
        command_sender["param3"] = param3
        command_sender["param4"] = param4

        command_sender["target_component"] = target_component
        command_sender["target_system"] = target_component

        print(f"Sending: {commandName} ({commandId})")
        self.ackWaiting[commandId] = {
            "time": time.time(),
            "sent_command": sent_command,
            "target_system": target_system,
            "target_component": target_component,
            "callback": callback,
        }
        self.set_interval(self.checkForAcks, 1)

        usedConnection.send(command_sender)

    def requestMessage(
        self,
        request_message_id,
        index_id=0,
        param3=0,
        param4=0,
        param5=0,
        param6=0,
        response_target=0,
        target_system=None,
        target_component=None,
        connection=None,
        callback=defaultCallback,
    ):
        """
        Request a message

        Args
            request_message_id (int): Id of message that has been requested - param1
            index_id (int): index if used (corresponds to message) - param2
            response_target (int): Target address of message stream (if message has target address fields). 0: Flight-stack default (recommended), 1: address of requester, 2: broadcast.
            target_system (int): MAVLink system ID
            target_component (int): MAVLink component ID
            connection: Connection object for sending. Default None means "self.connection"
            callback (function): Optional callback function to call when the command is acknowledged. Default will be used otherwise.

        """
        print(f"debug: requestMessage: {request_message_id}")
        target_system = target_system if target_system else self.target_system_id
        target_component = (
            target_component if target_component else self.target_component_id
        )
        usedConnection = connection if connection else self.connection

        self.commandSenderNonBlocking(
            commandName="MAV_CMD_REQUEST_MESSAGE",
            param1=request_message_id,
            param2=index_id,
            param3=param3,
            param4=param4,
            param5=param5,
            param6=param6,
            param7=response_target,
            connection=usedConnection,
            target_system=target_system,
            target_component=target_component,
            callback=callback,
        )


    def setMessageInterval(
        self,
        request_message_id,
        interval=-1, #us -  disable by default (-1)
        index_id=0, # id 0 by default.
        response_target=0,
        target_system=None,
        target_component=None,
        connection=None,
        callback=defaultCallback,
    ):
        """
        Set interval for message
        https://mavlink.io/en/messages/common.html#MAV_CMD_SET_MESSAGE_INTERVAL

        Args
            request_message_id (int): Id of message to be streamed
            interval (int): Interval in us requested. -1 to disable.
            index_id (int): index if used (corresponds to message) - param2
            response_target (int): Target address of message stream (if message has target address fields). 0: Flight-stack default (recommended), 1: address of requester, 2: broadcast.
            callback (func): Callback with result. Default to ... default.
            connection etc BD.

        """
        print("Debug: Send: MAV_CMD_SET_MESSAGE_INTERVAL")
        target_system = target_system if target_system else self.target_system_id
        target_component = (
            target_component if target_component else self.target_component_id
        )
        usedConnection = connection if connection else self.connection

        self.commandSenderNonBlocking(
            commandName="MAV_CMD_SET_MESSAGE_INTERVAL",
            param1=request_message_id,
            param2=interval,
            param3=index_id,
            param7=response_target,
            connection=usedConnection,
            target_system=target_system,
            target_component=target_component,
            callback=callback,
        )


    def getMessageInterval(
        self,
        message_id,
        index_id=0, # id 0 by default.
        response_target=0,
        target_system=None,
        target_component=None,
        connection=None,
        callback=defaultCallback,
        ):

        """
        Get interval for message.

        Uses MAV_CMD_REQUEST_MESSAGE (512) by default to request MESSAGE_INTERVAL.
        https://mavlink.io/en/messages/common.html#MAV_CMD_GET_MESSAGE_INTERVAL - deprecated
        https://mavlink.io/en/messages/common.html#MESSAGE_INTERVAL

        Args
            message_id (int): Id of message for which we want the rate
            response_target (int): Target address of message stream (if message has target address fields). 0: Flight-stack default (recommended), 1: address of requester, 2: broadcast.
            callback (function): Optional callback function to call when the command is acknowledged. Default will be used otherwise.
            target_system (int): MAVLink system ID
            target_component (int): MAVLink component ID
            connection: Connection object for sending. Default None means "self.connection"
            senderType (int): 0 for command_long , 1 for command_int (default).

        The interval between messages for a particular MAVLink message ID. This message is sent in response to the MAV_CMD_REQUEST_MESSAGE command with param1=244 (this message) and param2=message_id (the id of the message for which the interval is required). It may also be sent in response to MAV_CMD_GET_MESSAGE_INTERVAL. This interface replaces DATA_STREAM.
            Field Name	Type	Units	Description
            message_id	uint16_t		The ID of the requested MAVLink message. v1.0 is limited to 254 messages.
            interval_us	int32_t	us	The interval between two messages. A value of -1 indicates this stream is disabled, 0 indicates it is not available, > 0 indicates the interval at which it is sent.

        """
        target_system = target_system if target_system else self.target_system_id
        target_component = (
            target_component if target_component else self.target_component_id
        )
        usedConnection = connection if connection else self.connection

        self.requestMessage(
            #request_message_id='MESSAGE_INTERVAL',
            request_message_id=244,
            index_id=message_id,
            response_target=response_target,
            connection=usedConnection,
            target_system=target_system,
            target_component=target_component,
            callback=callback,
        )

        ##TODO TRY using the deprecated requester?


    def getMessageIntervalDeprecated(
        self,
        message_id,
        target_system=None,
        target_component=None,
        connection=None,
        callback=defaultCallback,
        ):

        """
        Get interval for message using deprecated MAV_CMD_GET_MESSAGE_INTERVAL method.

        Args
            message_id (int): Id of message for which we want the rate
            callback (function): Optional callback function to call when the command is acknowledged. Default will be used otherwise.
            target_system (int): MAVLink system ID
            target_component (int): MAVLink component ID
            connection: Connection object for sending. Default None means "self.connection"
        """
        target_system = target_system if target_system else self.target_system_id
        target_component = (
            target_component if target_component else self.target_component_id
        )
        usedConnection = connection if connection else self.connection

        self.commandSenderNonBlocking(
            commandName="MAV_CMD_GET_MESSAGE_INTERVAL",
            param1=message_id,
            connection=usedConnection,
            target_system=target_system,
            target_component=target_component,
            callback=callback,
        )



    def setGlobalOrigin(
        self,
        lat,
        lon,
        alt,
        target_system=None,
        target_component=None,
        connection=None,
        callback=defaultCallback,
    ):
        """
        Send MAV_CMD_DO_SET_GLOBAL_ORIGIN

        Args
            lat: latitude 1E7 (WGS84) param 5
            long: longitude 1E7  (WGS84) param 6
            alt: m MSL param 7
            target_system (int): MAVLink system ID
            target_component (int): MAVLink component ID
            connection: Connection object for sending. Default None means "self.connection"
            senderType (int): 0 for command_long , 1 for command_int (default).
        """
        print("SetGlobalOrigin - MAV_CMD_DO_SET_GLOBAL_ORIGIN")
        target_system = target_system if target_system else self.target_system_id
        target_component = (
            target_component if target_component else self.target_component_id
        )
        usedConnection = connection if connection else self.connection

        self.commandSenderNonBlocking(
            commandName="MAV_CMD_DO_SET_GLOBAL_ORIGIN",
            target_system=target_system,
            target_component=target_component,
            connection=usedConnection,
            param5=lat,
            param6=lon,
            param7=alt,
            callback=callback,
        )
        # Should get back ACK and GPS_GLOBAL_ORIGIN

    def arm(
        self,
        arm=1,
        target_system=None,
        target_component=None,
        connection=None,
        callback=defaultCallback,
    ):
        """
        Send command to arm.

        Note, force-disarm in flight not supported

        Args
            target_system (int): MAVLink system ID
            target_component (int): MAVLink component ID

            connection: Connection object for sending. Default None means "self.connection"
            senderType (int): 0 for command_long , 1 for command_int (default).
            arm (bool): Arm 1 (default) or disarm 0

        """
        target_system = target_system if target_system else self.target_system_id
        target_component = (
            target_component if target_component else self.target_component_id
        )
        usedConnection = connection if connection else self.connection

        self.commandSenderNonBlocking(
            commandName="MAV_CMD_COMPONENT_ARM_DISARM",
            param1=arm,
            connection=usedConnection,
            target_system=target_system,
            target_component=target_component,
            callback=callback,
        )

    def rebootShutdown(
        self,
        autopilot=0,
        companion=0,
        component=0,
        component_id=0,
        force=False,
        camera_id=-1,
        connection=None,
        target_system=None,
        target_component=None,
        callback=defaultCallback,
    ):
        """
        Send command to force reboot shutdown (MAV_CMD_PREFLIGHT_REBOOT_SHUTDOWN)
        https://mavlink.io/en/messages/common.html#MAV_CMD_PREFLIGHT_REBOOT_SHUTDOWN

        Args
            target_system (int): MAVLink system ID
            target_component (int): MAVLink component ID

            connection: Connection object for sending. Default None means "self.connection"
            autopilot (int): 0: nothing (default), 1 reboot , 2 shutdown, 3 reboot and keep in bootloader until upgraded.
            companion (int): 0: nothing (default), 1 reboot , 2 shutdown, 3 reboot and keep in bootloader until upgraded.
            component (int): 0: nothing (default), 1 reboot , 2 shutdown, 3 reboot and keep in bootloader until upgraded.
            component_id (int): 0 all components or component id.
            camera_id (int): 0 all components or component id.
            force (bool): true to force even when safe
        """
        target_system = target_system if target_system else self.target_system_id
        target_component = (
            target_component if target_component else self.target_component_id
        )
        usedConnection = connection if connection else self.connection

        force_value = 0
        if force:
            force_value = 20190226

        self.commandSenderNonBlocking(
            commandName="MAV_CMD_PREFLIGHT_REBOOT_SHUTDOWN",
            target_system=target_system,
            target_component=target_component,
            param1=autopilot,
            param2=companion,
            param3=component,
            param4=component_id,
            param6=force_value,
            param7=camera_id,
            connection=usedConnection,
            callback=callback,
        )  # Note, default sender type.

    def setMode(
        self,
        base_mode,
        custom_mode,
        custom_submode,
        connection=None,
        target_system=None,
        target_component=None,
        callback=defaultCallback,
    ):
        """
        Send command to set a mode

        MAV_CMD_DO_SET_MODE

        Args
            base_mode (int): MAV_MODE_FLAG value
            custom_mode (int): Custom mode
            custom_submode (int): Custom sub mode. Note sure this really is an int.
            target_system (int): MAVLink system ID
            target_component (int): MAVLink component ID
            connection: Connection object for sending. Default None means "self.connection"
        """
        target_system = target_system if target_system else self.target_system_id
        target_component = (
            target_component if target_component else self.target_component_id
        )
        usedConnection = connection if connection else self.connection
        self.commandSenderNonBlocking(
            commandName="MAV_CMD_DO_SET_MODE",
            param1=base_mode,
            param2=custom_mode,
            param3=custom_submode,
            connection=usedConnection,
            target_system=target_system,
            target_component=target_component,
            callback=callback,
        )



    def sendTestCommands(self):
        print("sleep 1 before takeoff and arm")
        time.sleep(1)
        targetSystem = 1
        targetComponent = message_set.enum("MAV_COMP_ID_AUTOPILOT1")
        self.sendCommandArm(
            target_system=targetSystem, target_component=targetComponent
        )
        time.sleep(5)

        """
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
        """
