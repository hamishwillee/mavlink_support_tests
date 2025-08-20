"""
Test script for messages
"""

import time
import pprint
from tools.timer_resettable import ResettableTimer


class MessageSetRatesTest:
    def __init__(self, mav_component):
        # super().__init__(mav_component)
        self.mav_component = mav_component
        self.commandSender = self.mav_component.commander
        self.target_system_id = self.mav_component.target_system_id
        self.target_component_id = self.mav_component.target_component_id
        self._accumulator = dict()
        self.messages = dict()


    def accumulator_callback(self):
        """
        Callback function to be executed when the accumulator timer expires.
        This works out if our average Hz is changing.
        """

        def special_round(value):
            """
            Special rounding function to round to a specific precision.
            """
            if value is None:
                return None
            if value == 0:
                return 0
            rounded_value = None
            if value > 0.75:
                rounded_value = round(value, 0)
            else:
                try:
                    rounded_value = 1 / round(1 / value, 0)
                except ZeroDivisionError:
                    rounded_value = 0
            if rounded_value > 95 and rounded_value < 105:
                rounded_value = 100
            elif rounded_value > 45 and rounded_value < 55:
                rounded_value = 50
            elif rounded_value > 9 and rounded_value < 11:
                rounded_value = 10
            return rounded_value

        # print(f"Debug: Timer callback for message accumulator")
        test_timestamp = time.monotonic()
        for messageName in self._accumulator:
            if self._accumulator[messageName]["count"] == 1:
                self._accumulator[messageName]["Hz"] = 0
                continue
            timediff = (
                test_timestamp - self._accumulator[messageName]["first_timestamp"]
            )
            hz_expected = self._accumulator[messageName]["count"] / timediff
            hz_avg = self._accumulator[messageName].get("hz_avg", None)
            hz_last = self._accumulator[messageName].get("hz_last", None)

            hz_avg_rnd = special_round(hz_avg)
            hz_last_rnd = special_round(hz_last)
            hz_expected_rnd = special_round(hz_expected)
            # print(f"Msg: {messageName}: hz_expected_rnd: {hz_expected_rnd} hz_avg_rnd: {hz_avg_rnd}")
            expected_vs_avg = hz_expected_rnd - hz_avg_rnd
            if self._accumulator[messageName]["count"] > 3:
                # print(f"Msg: {messageName}: hz_expected_rnd: {hz_expected_rnd} hz_avg_rnd: {hz_avg_rnd} - hz_expected: {hz_expected}")
                # If we have more than 3 messages, we can do some stats
                if expected_vs_avg == 0:
                    self._accumulator[messageName]["Hz"] = hz_avg_rnd
                if expected_vs_avg < 0:
                    self._accumulator[messageName]["Hz"] = 0
                else:
                    # print(f"Debug: Msg: {messageName}: expected_vs_avg: {expected_vs_avg} expected: {hz_expected}/rnd: {hz_expected_rnd}, avg: {hz_avg}, avg_rnd: {hz_avg_rnd}, hz_last_rnd: {hz_last_rnd}, last: {hz_last}")
                    pass

            # self._accumulator[messageName]["hz_avg_rnd"] = hz_avg_rnd

    def _messageAccumulator(self, msg):
        messageName = msg.name
        message_dict = msg.to_dict()
        if messageName == "MESSAGE_INTERVAL":
            print(f"debug: MESSAGE_INTERVAL: {message_dict}")
            message_id = message_dict['message_id']
            message_name = ""
            try:
                message_name = self.mav_component.docs.getMessageName(message_id)
            except KeyError:
                message_name = ""
                print(f"debug: MESSAGE_INTERVAL: No message found for id {message_id}")
            interval_us = message_dict['interval_us']
            frequency_hz = 0
            streamable = "false"
            if interval_us > 0:
                streamable = 'default'
                frequency_hz = (1000000/ interval_us)
            if interval_us == 0:
                streamable = "true"
            if message_name not in self.messages:
                self.messages[message_name] = {'_id': message_id, '_name': message_name, 'interval_us': interval_us, 'frequency_hz': frequency_hz, 'streamable': streamable}
                print(f"debug: MESSAGE_INTERVAL: ADD: {self.messages[message_name]}")




    def ackSetRates(self, command, commandName, result, ack_message, ackedCommand):
        message_id = ackedCommand['sent_command']['param1']
        message_name = self.mav_component.docs.getMessageName(message_id)
        #print(f"defaultCallback:COMMAND_ACK: ({commandName}): {result} (ACK: {ack_message}), originalCommand: {ackedCommand}")
        print(
            f"ackSetRates: {message_name}: {result}"
        )
        self.messages[message_name] = result



    def setAllRates(self):
        # Starts the test
        # Get all the messages
        messages = self.mav_component.docs.getMessages()
        frequency = 2 #Hz
        period = (1 / frequency) * 1000000  # Convert to microseconds
        for name, message in messages.items():
            id = message["id"]
            print(f"Debug: setRatesTest: {name}: {id}")

            # Call the set rate command to set all of them to a level

            self.commandSender.setMessageInterval(
                request_message_id=id,
                interval=period,
                callback=self.ackSetRates
                )

            time.sleep(0.5)


    def ackGetRates(self, command, commandName, result, ack_message, ackedCommand):
        message_id = ackedCommand['sent_command']['param1']
        message_name = self.mav_component.docs.getMessageName(message_id)
        #print(f"defaultCallback:COMMAND_ACK: ({commandName}): {result} (ACK: {ack_message}), originalCommand: {ackedCommand}")
        print(
            f"ackGetRates: {message_name}: {result}"
        )
        # Not sure what to do here.
        # Probably - add denied to the record.
        #self.messages[message_name] = result


    def getAllRates(self):
        # Starts the test
        # Get all the messages
        messages = self.mav_component.docs.getMessages()
        #frequency = 2 #Hz
        #period = (1 / frequency) * 1000000  # Convert to microseconds
        for name, message in messages.items():
            id = message["id"]
            print(f"Debug: getRatesTest: {name}: {id}")

            # Call the set rate command to set all of them to a level
            """
            self.commandSender.getMessageInterval(
                message_id=id,
                callback=self.ackGetRates
                )

            """
            self.commandSender.getMessageIntervalDeprecated(
                message_id=id,
                callback=self.ackGetRates
                )
            time.sleep(0.5)


    def startTest(self):
        # Starts the test
        self.mav_component.mav_connection.add_threaded_message_callback(
            self._messageAccumulator
        )
        #self.setAllRates()
        self.getAllRates()

        # Check the interval?
        # Start accumulator and check it.
        """
        self._timer_new_messages = ResettableTimer(
            10, self.accumulator_callback
        )  # Timer for new messages


        """


    def report(self):
        # TODO add additional info.
        # Adds report with a key to the component._report dict.
        pprint.pprint(self.messages)



