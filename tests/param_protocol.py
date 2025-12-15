"""
Test script for parameter protocol. IN PROGRESS
"""

import time
import pprint

class ParameterProtocolTest:
    def __init__(self, mav_component):
        # super().__init__(mav_component)
        self.mav_component = mav_component
        self.target_system_id = mav_component.target_system_id
        self.target_component_id = mav_component.target_component_id
        self.message_set = mav_component.message_set
        self.docs = mav_component.docs
        self.connection = self.mav_component.mav_connection.connection
        # self._accumulator = dict()

    def _messageAccumulator(self, msg):
        messageName = msg.name
        message_dict = msg.to_dict()

        if messageName.startswith("PAR"):

            print(
                f"Param message: [{self.target_system_id}:{self.target_component_id}] {messageName} {message_dict}"
            )


        self.mav_component.msgNotForComponent(message_dict)
        # Log messages as they are recieved


    def test_invalid_param(self):
        # Starts the test
        self.mav_component.mav_connection.add_threaded_message_callback(
            self._messageAccumulator
        )
        time.sleep(1)

        param_set = self.message_set.create("PARAM_SET")
        #pprint.pprint(param_set.to_dict())
        param_set['target_system'] = self.target_system_id
        param_set['target_component'] = self.target_component_id
        #param_set['param_id'] = b"SYSID_THISMAV"  # Must be 16 chars, null terminated
        param_set['param_value'] = 2.0
        paramType32 = self.docs.getEnumEntries("MAV_PARAM_TYPE")['MAV_PARAM_TYPE_INT32']['value']
        param_set['param_type'] = paramType32
        #pprint.pprint(param_set.to_dict())
        #self.connection.send(param_set)
        param_set['param_id'] = b"ADSB_GPS_OFF_LAT"  # Must be 16 chars, null terminated - VALID name for PX4
        self.connection.send(param_set)
        param_set['param_id'] = b"INVALID_NAME"  # Must be 16 chars, null terminated - INVALID name for PX4
        self.connection.send(param_set)


    def runTest(self):
        # Starts the test

        self.test_invalid_param()




        time.sleep(20)


    def __report(self):
        pass
