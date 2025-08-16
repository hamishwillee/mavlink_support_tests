"""
Test script for sending all commands
"""

import time
import pprint
# from tools.timer_resettable import ResettableTimer


class SendAllCommandsTest:
    def __init__(self, mav_component):
        # super().__init__(mav_component)
        self.mav_component = mav_component
        self.target_system_id = mav_component.target_system_id
        self.target_component_id = mav_component.target_component_id
        # self._accumulator = dict()
        self.docs = self.mav_component.docs
        self.commandSender = self.mav_component.commander

        # self.__commands = dict()  # The logged info about commands
        # self._timer_new_messages = ResettableTimer( 10, self.accumulator_callback)  # Timer for new messages
        # mav_component.mav_connection.add_threaded_message_callback(self._messageAccumulator)

    def defaultCallback(self, command, commandName, result, ack_message, ackedCommand):
        # print(f'defcallbackCOMMAND_ACK: ({command}): {result} (prog: {message["progress"]}, resparm2: {message["result_param2"]})')
        print(f"sendalAckcallback_COMMAND_ACK: ({commandName}): {result}")
        # TODO - Log the result

    def sendAllCommands(self):
        print("testSendAllCommands")
        allCommands = self.docs.getCommands()
        for name in allCommands.keys():
            print(f"Sending: {name}")
            self.commandSender.commandSenderNonBlocking(
                commandName=name,
                target_system=self.target_system_id,
                target_component=self.target_component_id,
                param1=0,
                param2=0,
                param3=0,
                param4=0,
                param5=0,
                param6=0,
                param7=0,
                callback=self.defaultCallback,
            )
            time.sleep(0.5)

        # Send all commands (to test ACKS)

        # pprint.pprint(msgInfo.getCommandInfo())
        """
        def sendAllCommands(self, target_system, target_component, connection=None, senderType=0):
            # Sends all commands, one after another with a space between. We're just trying to work out if supported or not.
            # Get all commands
            # targetSystem = 1
            # targetComponent = message_set.enum("MAV_COMP_ID_AUTOPILOT1")
            allCommands = self.docs.getCommands()
            for name in allCommands.keys():
                print(f"Sending: {name}")
                self.commandSenderNonBlocking(connection=connection, senderType=senderType, commandName=name, target_system=target_system,
                                            target_component=target_component, param1=0, param2=0, param3=0, param4=0, param5=0, param6=0, param7=0)
                time.sleep(1)
        """

    def accumulator_callback(self):
        """
        Callback function to be executed when the accumulator timer expires.
        This works out if our average Hz is changing.
        """
        pass

    def _messageAccumulator(self, msg):
        messageName = msg.name
        message_dict = msg.to_dict()
        self.mav_component.msgNotForComponent(message_dict)
        # Log messages as they are recieved
        # (this is a "working" repo of info used for stats, which we may clear at various points)

    def report(self):
        # Adds report with a key to the component._report dict.
        messages = dict()
        for messageName in self._accumulator:
            messages[messageName] = dict()
            try:
                messages[messageName]["rate"] = self._accumulator[messageName]["Hz"]
            except:
                messages[messageName]["rate"] = 0
            messages[messageName]["xml"] = self.mav_component.docs.getMessage(
                name=messageName
            )["basename"]

        self.mav_component._report["all_messages"] = messages
