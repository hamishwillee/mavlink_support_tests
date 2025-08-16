"""
Test script for messages
"""

import time
import pprint
from tools.timer_resettable import ResettableTimer


class MessagesTest:
    def __init__(self, mav_component):
        # super().__init__(mav_component)
        self.mav_component = mav_component
        self.target_system_id = mav_component.target_system_id
        self.target_component_id = mav_component.target_component_id
        self._accumulator = dict()

        # self.__messages = dict()  # The logged info about messages
        # self.__commands = dict()  # The logged info about commands
        self._timer_new_messages = ResettableTimer(
            10, self.accumulator_callback
        )  # Timer for new messages
        mav_component.mav_connection.add_threaded_message_callback(
            self._messageAccumulator        )

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
        self.mav_component.msgNotForComponent(message_dict)
        # Log messages as they are recieved
        # (this is a "working" repo of info used for stats, which we may clear at various points)
        if messageName not in self._accumulator:
            self._timer_new_messages.start()  # start/reset timer
            print(
                f"Debug: Acc: New Message: [{self.target_system_id}:{self.target_component_id}] {messageName}"
            )
            first_timestamp = time.monotonic()
            self._accumulator[messageName] = {
                "count": 1,
                "first_timestamp": first_timestamp,
                "last_timestamp": first_timestamp,
                "maxHz": 0,
                "minHz": 1000000,
            }
            # if self.__no_message_change:  # ie haven't started changing what gets streamed
            #    self._accumulator[messageName]['initial'] = True

        else:
            if "Hz" in self._accumulator[messageName]:
                # print(f'Debug: Acc: HZ defined done {self._accumulator[messageName]["Hz"]}')
                return  # We already have a Hz defined, so don't update it
            self._accumulator[messageName]["count"] += 1
            last_timestamp = time.monotonic()
            timediff_last = (
                last_timestamp - self._accumulator[messageName]["last_timestamp"]
            )
            # print(timediff_last)
            hz_last = 1 / timediff_last
            if hz_last > self._accumulator[messageName]["maxHz"]:
                self._accumulator[messageName]["maxHz"] = hz_last
            if hz_last < self._accumulator[messageName]["minHz"]:
                self._accumulator[messageName]["minHz"] = hz_last
            # TODO perhaps look at last values for packetloss?

            # print(hz_last)
            self._accumulator[messageName]["hz_last"] = hz_last
            hz_avg = 1 / (
                (last_timestamp - self._accumulator[messageName]["first_timestamp"])
                / self._accumulator[messageName]["count"]
            )
            # print(hz_avg)
            # Across the whole queue
            self._accumulator[messageName]["hz_avg"] = hz_avg

            # update the last timestamp
            self._accumulator[messageName]["last_timestamp"] = time.monotonic()

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
