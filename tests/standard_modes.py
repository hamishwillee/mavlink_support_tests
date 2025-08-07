"""
Test script for standard modes: ???
"""

#import libmav
import time
import pprint
#from collections import deque
#import numpy as np

# Library for sending commands
from tools import command_sender



def inspect_object(object):
    print(f"Public API: {type(object).__name__}")
    for attr in dir(object):
        if not attr.startswith('__'):
            value = getattr(object, attr)
            print(f"  {attr} (Value: {value}) (type: {type(value)})")


class StandardModesTest:
    def __init__(self, connection, mavlinkDocs, libmav_message_set, own_system_id, own_component_id):
        self.connection = connection
        self.docs = mavlinkDocs
        self.message_set = libmav_message_set
        self.own_system_id = own_system_id # The system ID of this system running the tests/sending commands
        self.own_component_id = own_component_id  # The component ID of this system running the tests/sending commands

        self.__modes_callback_handle = None
        self.current_mode_rate_avg = None
        self._available_modes_monitor_rate_avg = None
        self.availableModesAlwaysStreamed = False
        self.duplicateAvailableModes = False  # available_modes with same index
        self.modesByIndex = dict()
        # current_mode counters
        self._current_mode_last_timestamp = None
        self._current_mode_accumulated_time = 0
        self._current_mode_period_count = 0
        # available_modes_monitor counters
        self._modes_monitor_last_timestamp = None
        self._modes_monitor_accumulated_time = 0
        self._modes_monitor_period_count = 0

        self._notRequestedAvailableModes = True
        self.commander = command_sender.CommandSender(connection=self.connection, mavlinkDocs=self.docs, libmav_message_set = self.message_set, own_system_id=self.own_system_id, own_component_id=self.own_component_id)



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

    def supported_modes(self,msg):
        messageName = msg.name

        if messageName == 'CURRENT_MODE':
            # Get average rate
            timestamp=time.monotonic()

            if self._current_mode_last_timestamp:
                self._current_mode_period_count += 1
                timediff = timestamp - self._current_mode_last_timestamp
                self._current_mode_accumulated_time += timediff
                self.current_mode_rate_avg = self._current_mode_period_count/self._current_mode_accumulated_time
                #print(f"count: {self._current_mode_period_count}, Acctime {self._current_mode_accumulated_time}, av: {self.current_mode_rate_avg}")
            self._current_mode_last_timestamp=timestamp

            message_dict = msg.to_dict()
            print(message_dict)


        if messageName == 'AVAILABLE_MODES_MONITOR':
            # Get average rate
            timestamp=time.monotonic()

            if self._modes_monitor_last_timestamp:
                self._modes_monitor_period_count += 1
                timediff = timestamp - self._modes_monitor_last_timestamp
                self._modes_monitor_accumulated_time += timediff
                self._available_modes_monitor_rate_avg = self._modes_monitor_period_count/self._modes_monitor_accumulated_time
                #print(f"count: {self._modes_monitor_period_count}, Acctime {self._modes_monitor_accumulated_time}, av: {self._available_modes_monitor_rate_avg}")
            self._modes_monitor_last_timestamp=timestamp
            message_dict = msg.to_dict()
            print(message_dict)

        if messageName == 'AVAILABLE_MODES':
            #inspect_object(msg)
            if self._notRequestedAvailableModes:
                self.availableModesAlwaysStreamed = True # Bad!
            print(f"Message name: {messageName}")
            message_dict = msg.to_dict()
            print(message_dict)
            mode_index = message_dict['mode_index']
            #print(f"mode index: {mode_index}")
            if mode_index not in self.modesByIndex:
                self.modesByIndex[mode_index] = message_dict
                self.modesByIndex[mode_index]['count']=1
            else:
                self.modesByIndex[mode_index]['count']=self.modesByIndex[mode_index]['count']+1
                self.duplicateAvailableModes = True
                #messageDict = self.modesByIndex[mode_index]



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