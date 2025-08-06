"""
Test script for messages
"""

import time
import pprint
from timer_resettable import ResettableTimer




class MessagesTest:
    def __init__(self, mav_component):
        self.mav_component = mav_component
        self._accumulator = dict()

        # self.__messages = dict()  # The logged info about messages
        # self.__commands = dict()  # The logged info about commands
        self._timer_new_messages = ResettableTimer(
            10, self.accumulator_callback)  # Timer for new messages

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
            if value is 0:
                return 0
            rounded_value = None
            if value > 0.75:
                rounded_value = round(value, 0)
            else:
                try:
                    rounded_value = 1/round(1/value, 0)
                except ZeroDivisionError:
                    rounded_value = 0
            if rounded_value > 95 and rounded_value < 105:
                rounded_value = 100
            elif rounded_value > 45 and rounded_value < 55:
                rounded_value = 50
            elif rounded_value > 9 and rounded_value < 11:
                rounded_value = 10
            return rounded_value

        print(f"Debug: Timer callback for message accumulator")
        test_timestamp = time.monotonic()
        for messageName in self._accumulator:
            if self._accumulator[messageName]["count"] == 1:
                self._accumulator[messageName]["Hz"] = 0
                continue
            timediff = test_timestamp - \
                self._accumulator[messageName]["first_timestamp"]
            #print(f"Msg: {messageName}: timediff: {timediff}")
            hz_expected = self._accumulator[messageName]["count"] / timediff
            #print(f"Msg: {messageName}: hz_expected: {hz_expected} (count/timediff)")
            #hz_expected = round(hz_expected, 0)  # Round to 2 decimal places
            #print(f"Msg: {messageName}: hz_expected: {hz_expected} (rounded count/timediff)")
            hz_avg = self._accumulator[messageName].get("hz_avg", None)
            hz_last = self._accumulator[messageName].get("hz_last", None)

            hz_avg_rnd = special_round(hz_avg)
            hz_last_rnd = special_round(hz_last)
            hz_expected_rnd = special_round(hz_expected)
            #print(f"Msg: {messageName}: hz_expected_rnd: {hz_expected_rnd} hz_avg_rnd: {hz_avg_rnd}")
            expected_vs_avg = hz_expected_rnd - hz_avg_rnd
            if self._accumulator[messageName]["count"] > 3:
                #print(f"Msg: {messageName}: hz_expected_rnd: {hz_expected_rnd} hz_avg_rnd: {hz_avg_rnd} - hz_expected: {hz_expected}")
                # If we have more than 3 messages, we can do some stats
                if expected_vs_avg == 0:
                    self._accumulator[messageName]["Hz"] = hz_avg_rnd
                if expected_vs_avg < 0:
                    self._accumulator[messageName]["Hz"] = 0
                else:
                    print(f"Msg: {messageName}: expected_vs_avg: {expected_vs_avg} expected: {hz_expected}/rnd: {hz_expected_rnd}, avg: {hz_avg}, avg_rnd: {hz_avg_rnd}, hz_last_rnd: {hz_last_rnd}, last: {hz_last}")

            # self._accumulator[messageName]["hz_avg_rnd"] = hz_avg_rnd

    def messageAccumulator(self, messageName):
        # Log messages as they are recieved
        # (this is a "working" repo of info used for stats, which we may clear at various points)
        if messageName not in self._accumulator:
            self._timer_new_messages.start()  # start/reset timer
            # print(f'Debug: Acc: New Message: [{self.target_system_id}:{self.target_component_id}] {messageName}')
            first_timestamp = time.monotonic()
            self._accumulator[messageName] = {
                "count": 1, "first_timestamp": first_timestamp, "last_timestamp": first_timestamp, "maxHz": 0, "minHz": 1000000}
            # if self.__no_message_change:  # ie haven't started changing what gets streamed
            #    self._accumulator[messageName]['initial'] = True

        else:
            self._accumulator[messageName]["count"] += 1
            last_timestamp = time.monotonic()
            timediff_last = last_timestamp - \
                self._accumulator[messageName]["last_timestamp"]
            # print(timediff_last)
            hz_last = 1 / timediff_last
            if hz_last > self._accumulator[messageName]["maxHz"]:
                self._accumulator[messageName]["maxHz"] = hz_last
            if hz_last < self._accumulator[messageName]["minHz"]:
                self._accumulator[messageName]["minHz"] = hz_last
            # TODO perhaps look at last values for packetloss?

            # print(hz_last)
            self._accumulator[messageName]["hz_last"] = hz_last
            hz_avg = 1 / \
                ((last_timestamp-self._accumulator[messageName]
                 ["first_timestamp"])/self._accumulator[messageName]["count"])
            # print(hz_avg)
            # Across the whole queue
            self._accumulator[messageName]["hz_avg"] = hz_avg

            # 1, 2, 3, 4, 5, 10, 20, 30, 50
            # 3if hz_avg_rnd == 10 and count > 10:
            #    self._accumulator[messageName]["Hz"] = 5

            # update the last timestamp
            self._accumulator[messageName]["last_timestamp"] = time.monotonic()

            """Que of data for later analysis
            # Store some data
            if "queue" in self._accumulator[messageName]:
                msgQueueTime = self._accumulator[messageName]["queue"]
                pass
            else:
                msgQueueTime = msgQueueTime = deque(maxlen=100)
            msgQueueTime.append(timediff_last)
            self._accumulator[messageName]["queue"] = msgQueueTime
            """

    def getSupportedModes(self):
        """
        Test the standard modes microservice
        https://mavlink.io/en/messages/development.html#MAV_CMD_DO_SET_STANDARD_MODE
        https://mavlink.io/en/messages/development.html#AVAILABLE_MODES
        https://mavlink.io/en/messages/development.html#CURRENT_MODE
        https://mavlink.io/en/messages/development.html#AVAILABLE_MODES_MONITOR

        1. CURRENT_MODE should always stream at rate > ?
        1. CURRENT_MODE fields should ?
        2. AVAILABLE_MODES should be supplied on MAV_CMD_REQUEST_MESSAGE with param2=0
        - All modes should be supplied.
        - Modes should ACK if supports
        3. AVAILABLE_MODES should be supplied on MAV_CMD_REQUEST_MESSAGE with param2=? where ? is the index.
        4. AVAILABLE_MODES - fields - what should they be
        5. All modes appear only once in the index even if custom and standard
        5. AVAILABLE_MODES_MONITOR should stream and emit on change?
        - rate?
        - field values?
        -inspect code?
        6. MAV_CMD_DO_SET_STANDARD_MODE should change mode.

        """
        print("StandardModesTest.getSupportedModes(): enter")

        targetSystem = 1 # should get from connection
        targetComponent = self.message_set.enum("MAV_COMP_ID_AUTOPILOT1") # TODO We should get from our connection.
        request_message_id = self.message_set.id_for_message('AVAILABLE_MODES')
        print(f"ID for AVAILABLE_MODES: {request_message_id}")
        get_all_modes = 0


        self.__modes_callback_handle = self.connection.add_message_callback(self.supported_modes)
        time.sleep(15)
        notRequestedAvailableModes = False

        self.commander.sendCommandRequestMessageNonBlocking(connection=self.connection, target_system=targetSystem, target_component=targetComponent, request_message_id=request_message_id, index_id=get_all_modes)
        time.sleep(5)

        #print(f"count: {self._current_mode_period_count}, Acctime {self._current_mode_accumulated_time}, av: {self._current_mode_accumulated_time/self._current_mode_period_count}")


        self.__report()





    def __report(self):
        # This is data so far
        print(f"CURRENT_MODE streaming rate (Hz) =  {self.current_mode_rate_avg}")

        if self.availableModesAlwaysStreamed:
            print(f"PROBLEM: AVAILABLE_MODES streamed even when not requested")
        if self._available_modes_monitor_rate_avg:
            print(f"AVAILABLE_MODES_MONITOR streaming rate (Hz) =  {self._available_modes_monitor_rate_avg}")
        else:
            print(f"AVAILABLE_MODES_MONITOR: not streamed, may not be supported")
        if self.current_mode_rate_avg:
            print(f"CURRENT_MODE streaming rate (Hz) =  {self.current_mode_rate_avg}")
        else:
            print(f"PROBELM - CURRENT_MODE: not streamed")
        if self.duplicateAvailableModes:
            print(f"PROBLEM - AVAILABLE_MODE with same index sent twice - maybe not - this could be result of my follow up test")
        #pprint.pprint(self.modesByIndex)