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
        self.docs = self.mav_component.docs
        self.commandSender = self.mav_component.commander
        self.all_commands = dict()
        _all_commands = self.docs.getCommands()

        # self.__commands = dict()  # The logged info about commands
        # self._timer_new_messages = ResettableTimer( 10, self.accumulator_callback)  # Timer for new messages
        # mav_component.mav_connection.add_threaded_message_callback(self._messageAccumulator)

    def defaultCallback(self, command, commandName, result, ack_message, ackedCommand):
        # print(f'defcallbackCOMMAND_ACK: ({command}): {result} (prog: {message["progress"]}, resparm2: {message["result_param2"]})')
        print(f"sendalAckcallback_COMMAND_ACK: ({commandName}): {result}")
        # TODO - Log the result
        if result == "MAV_RESULT_UNSUPPORTED":
            self.all_commands[commandName]["result"] = False
        else:
            self.all_commands[commandName]["result"] = True

    def sendAllCommands(self):
        print("testSendAllCommands")
        all_commands = self.docs.getCommands()

        for name, command in all_commands.items():
            #pprint.pprint(command)
            self.all_commands[name]={"result": None, "dialect":  command["basename"] }
            print(f"Sending: {name}")
            self.commandSender.commandSenderNonBlocking(
                commandName=name,
                callback=self.defaultCallback,
            )
            time.sleep(0.5)
        time.sleep(1.5) #give all a chance to arrive


    def report(self):
        # Adds report with a key to the component._report dict.
        commands = {'supported': {}, 'unsupported': {}, 'unknown': {}}
        for command, item in self.all_commands.items():
            if item["result"] is True:
                commands['supported'][command] = { "dialect": item["dialect"] }
            elif item["result"] is False:
                commands['unsupported'][command] = { "dialect": item["dialect"] }
            else:  # result is None - no response received.
                commands['unknown'][command] = { "dialect": item["dialect"] }

        #TODO Add the command origin - i.e where defined?
        self.mav_component._report["commands_supported"] = commands
        self.mav_component._report["commands_all"] = self.all_commands

        """
            try:
                messages[messageName]["rate"] = self._accumulator[messageName]["Hz"]
            except:
                messages[messageName]["rate"] = 0
            messages[messageName]["xml"] = self.mav_component.docs.getMessage(
                name=messageName
            )["basename"]
            ###

        """



