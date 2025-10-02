"""
Test script for messages
"""

import time
import pprint


class MessageGetRatesTest:
    def __init__(self, mav_component):
        # super().__init__(mav_component)
        self.mav_component = mav_component
        self.commandSender = self.mav_component.commander
        self.target_system_id = self.mav_component.target_system_id
        self.target_component_id = self.mav_component.target_component_id
        self._accumulator = dict()
        self.messages = dict()

    def _messageAccumulator(self, msg):
        messageName = msg.name
        message_dict = msg.to_dict()
        if messageName == "MESSAGE_INTERVAL":
            print(f"debug: MESSAGE_INTERVAL: {message_dict}")
            message_id = message_dict["message_id"]
            message_name = ""
            try:
                message_name = self.mav_component.docs.getMessageName(message_id)
            except KeyError:
                message_name = ""
                print(f"debug: MESSAGE_INTERVAL: No message found for id {message_id}")
            interval_us = message_dict["interval_us"]
            frequency_hz = 0
            streamable = False
            if interval_us > 0:
                streamable = "default"
                frequency_hz = 1000000 / interval_us
            if interval_us == 0:
                streamable = True
            if message_name not in self.messages:
                if streamable == "default":
                    self.messages[message_name] = {
                        "_id": message_id,
                        "_name": message_name,
                        "interval_us": interval_us,
                        "frequency_hz": frequency_hz,
                        "streamable": streamable,
                    }
                else:
                    self.messages[message_name] = {
                        "_id": message_id,
                        "_name": message_name,
                        "streamable": streamable,
                    }
                print(f"debug: MESSAGE_INTERVAL: ADD: {self.messages[message_name]}")

    def ackGetRates(self, command, commandName, result, ack_message, ackedCommand):
        message_id = ackedCommand["sent_command"]["param1"]
        message_name = self.mav_component.docs.getMessageName(message_id)
        # print(f"defaultCallback:COMMAND_ACK: ({commandName}): {result} (ACK: {ack_message}), originalCommand: {ackedCommand}")
        print(f"ackGetRates: {message_name}: {result}")
        # Not sure what to do here.
        # Probably - add denied to the record.
        # self.messages[message_name] = result

    def getAllRates(self):
        # Get the rates for all messages
        messages = self.mav_component.docs.getMessages()
        for name, message in messages.items():
            id = message["id"]
            print(f"Debug: getRatesTest: {name}: {id}")

            """ THIS is the right way to do this, but need to use this then fallback. For the moment disable this
            self.commandSender.getMessageInterval(
                message_id=id,
                callback=self.ackGetRates
                )

            """
            self.commandSender.getMessageIntervalDeprecated(
                message_id=id, callback=self.ackGetRates
            )
            time.sleep(0.5)

    def startTest(self):
        # Starts the test
        self.mav_component.mav_connection.add_threaded_message_callback(
            self._messageAccumulator
        )
        self.getAllRates()

    def report(self):
        # TODO add additional info.
        # Adds report with a key to the component._report dict.
        pprint.pprint(self.messages)
        self.mav_component._report["get_message_interval_all_messages"] = (
            self.messages
        )  # The messages streamed by default
