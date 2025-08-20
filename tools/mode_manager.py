"""
This is an object the holds mode information about a system.
Under construction.

        https://mavlink.io/en/messages/development.html#MAV_CMD_DO_SET_STANDARD_MODE
        https://mavlink.io/en/messages/development.html#AVAILABLE_MODES
        https://mavlink.io/en/messages/development.html#CURRENT_MODE
        https://mavlink.io/en/messages/development.html#AVAILABLE_MODES_MONITOR
"""

# import libmav
import time
import pprint
import threading
# from collections import deque
# import numpy as np

# Library for sending commands
from tools import command_sender

# default system ID=componentID=97
# Can set this in connection. We'll may it some kind of global later.

own_mavlink_ids = {
    "system_id": 250,  # Some GCS unallocated id
    "component_id": 194,  # MAV_COMP_ID_ONBOARD_COMPUTER4 - could be anything
}


def inspect_object(object):
    print(f"Public API: {type(object).__name__}")
    for attr in dir(object):
        if not attr.startswith("__"):
            value = getattr(object, attr)
            print(f"  {attr} (Value: {value}) (type: {type(value)})")


# default system ID=componentID=97
# Can set this in connection. We'll may it some kind of global later.


own_mavlink_ids = {
    "system_id": 250,  # Some GCS unallocated id
    "component_id": 194,  # MAV_COMP_ID_ONBOARD_COMPUTER4 - could be anything
}


# modes list
class StandardModes:
    def __init__(
        self,
        connection,
        mavlinkDocs,
        libmav_message_set,
        target_system,
        target_component,
    ):
        self.connection = connection
        self.message_set = libmav_message_set
        self.docs = mavlinkDocs

        # Set this to the value for AVAILABLE_MODES_MONITOR to re-trigger getting modes.
        self._monitor_value = None
        # The system ID of this system owning component we want to get modes for
        self.target_system = target_system
        # The component ID of this system we want to get modes for
        self.target_component = target_component

        self.commander = command_sender.CommandSender(
            connection=self.connection,
            mavlinkDocs=self.docs,
            libmav_message_set=self.message_set,
            own_system_id=own_mavlink_ids["system_id"],
            own_component_id=own_mavlink_ids["component_id"],
        )

        # self.system_id = target_system_id # System ID of the system we're finding modes for
        # self.component_id = target_component_id # Component ID of the system we're finding modes for
        self._getting_modes = False  # True if we're currently getting modes
        self._got_all_modes = False  # True if we have all modes

        # True if the system supports the standard modes API
        self.supports_standard_modes_api = None
        self.supports_current_mode = None
        self.supports_available_modes_monitor = None
        self.supports_available_modes = None
        self.available_modes_seq = None  #
        self.connection = connection
        self.number_modes = None  # Initially unknown
        self.current_mode = None
        all_modes = None

        self.modesByIndex = dict()
        self.timerGetModes = None

        """
        self.own_system_id = own_system_id # The system ID of this system running the tests/sending commands
        self.own_component_id = own_component_id  # The component ID of this system running the tests/sending commands

        self.__modes_callback_handle = None
        self.current_mode_rate_avg = None
        self._available_modes_monitor_rate_avg = None
        self.availableModesAlwaysStreamed = False
        self.duplicateAvailableModes = False  # available_modes with same index

        # current_mode counters
        self._current_mode_last_timestamp = None
        self._current_mode_accumulated_time = 0
        self._current_mode_period_count = 0
        # available_modes_monitor counters
        self._modes_monitor_last_timestamp = None
        self._modes_monitor_accumulated_time = 0
        self._modes_monitor_period_count = 0

        self._notRequestedAvailableModes = True

        """

    def requestModes(self):
        """
        Requests modes from the component/system.
        Triggered when you connect, but also if AVAILABLE_MODES_MONITOR updates.
        """
        print("StandardModesTest.requestModes(): enter")

        self.__modes_callback_handle = self.connection.add_message_callback(
            self.standard_mode_listener
        )

        def check_value(x):
            if x is True or x is None:
                return True
            return False

        def getModesCallback(command, commandName, result, ack_message, ackedCommand):
            print(f"\nDebug: getModesCallbackCOMMAND_ACK: ({commandName}): {result}")
            if result != "MAV_RESULT_UNSUPPORTED":
                self.supports_standard_modes_api = True
            else:
                self.supports_standard_modes_api = False
                print("Standard modes API not supported by this system.")
                if self.timerGetModes is not None:
                    self.timerGetModes.cancel()

        def getModesTimeout(self):
            print("\ngetModesTimeout:")
            if self.timerGetModes is not None:
                self.timerGetModes.cancel()
            # Test code
            # del self.modesByIndex[2]
            # del self.modesByIndex[5]
            # end test code.
            all_keys = set(range(1, self.number_modes + 1))
            present_keys = set(self.modesByIndex.keys())
            missing_keys = sorted(all_keys - present_keys)
            print(missing_keys)
            for key in missing_keys:
                print(f"Requesting mode {key} again")
                request_message_id = self.message_set.id_for_message("AVAILABLE_MODES")
                self.commander.sendCommandRequestMessageNonBlocking(
                    target_system=self.target_system,
                    target_component=self.target_component,
                    request_message_id=request_message_id,
                    index_id=key,
                    callback=None,
                )

        # Unless we know that standard modes aren't supported we request them.
        if check_value(self.supports_standard_modes_api):
            request_message_id = self.message_set.id_for_message("AVAILABLE_MODES")
            print("Requesting modes")

            self.get_all_modes = True
            self._getting_modes = True
            self._got_all_modes = False
            self.number_modes = None
            # Clear the dictionary of modes. We could do a swap but let's see if we need it.
            self.modesByIndex = dict()

            self.timerGetModes = threading.Timer(5.0, getModesTimeout, args=[self])
            self.timerGetModes.start()

            get_all_modes = 0
            self.commander.sendCommandRequestMessageNonBlocking(
                target_system=self.target_system,
                target_component=self.target_component,
                request_message_id=request_message_id,
                index_id=get_all_modes,
                callback=getModesCallback,
            )

    def standard_mode_listener(self, msg):
        messageName = msg.name

        # TODO also listen on heartbeat for mode changes and for current mode.
        # Perhaps listen for current mode, and if we get that then use it, but otherwise use CURRENT MODE?

        if self._getting_modes:
            # We are only interested in handling modes when we requested them

            if messageName == "AVAILABLE_MODES":
                # print(f"Debug: AVAILABLE_MODES message: {message_dict}")
                self.supports_available_modes = True

                message_dict = msg.to_dict()

                if self.number_modes is None:
                    self.number_modes = message_dict["number_modes"]

                mode_index = message_dict["mode_index"]
                # print(f"mode index: {mode_index}")
                if mode_index not in self.modesByIndex:
                    self.modesByIndex[mode_index] = message_dict
                    self.modesByIndex[mode_index]["count"] = 1
                else:
                    self.modesByIndex[mode_index]["count"] = (
                        self.modesByIndex[mode_index]["count"] + 1
                    )
                    self.duplicateAvailableModes = True

                numMissingKeys = self.number_modes - len(self.modesByIndex)
                print(f"Debug: Remaining modes: {numMissingKeys}")
                # if len(missing_keys) == 0:
                if numMissingKeys == 0:
                    print("All modes received.")
                    self._getting_modes = False
                    self._got_all_modes = True

                    if self.timerGetModes is not None:
                        self.timerGetModes.cancel()

        if messageName == "CURRENT_MODE":
            self.supports_current_mode = True
            # Get average rate
            # timestamp = time.monotonic()
            message_dict = msg.to_dict()
            # print(f"Debug: CURRENT_MODE message: {message_dict}")
            self.current_mode = message_dict
            # TODO - log when mode changes
            # TODO - watch heartbeat for mode changes OO ?and update current_mode accordingly.

        if messageName == "AVAILABLE_MODES_MONITOR":
            self.supports_available_modes_monitor = True
            message_dict = msg.to_dict()
            print(f"Debug: AVAILABLE_MODES_MONITOR message: {message_dict}")
            if self.available_modes_seq is None:
                self.available_modes_seq = message_dict["seq"]
            elif self.available_modes_seq != message_dict["seq"]:
                print(
                    f"Debug: AVAILABLE_MODES_MONITOR sequence number changed: {self.available_modes_seq} -> {message_dict['seq']}"
                )
                self.available_modes_seq = message_dict["seq"]
                # Re-request modes to ensure we have the latest.
                print(
                    "Re-requesting modes due to AVAILABLE_MODES_MONITOR sequence change."
                )
                self.requestModes()  # Re-request modes to ensure we have the latest.

    def getCurrentMode(self):
        # Returns the current mode of the system.
        # But we need to do some translation work. May get mode from cached data about modes for PX4.
        # Also, perhaps combine heartbeat data so we use either CURRENT_MODE or HEARTBEAT.

        print("getCurrentMode: NOT IMPLEMENTED")

    def __report(self):
        pprint.pprint(self.modesByIndex)
        # Add other things such as whether modes are supported etc.
