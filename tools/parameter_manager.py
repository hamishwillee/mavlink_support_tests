"""
This is an object that allows use of the parameter protocol. UNDER CONSTRUCTION
https://mavlink.io/en/services/parameter.html

"""

import time
import pprint

import functools
import types

from .timer_resettable import ResettableTimer
from .timer_interval import IntervalTimer



class ParameterProtocolManager:
    def __init__(self, mav_component):
        self.mav_component = mav_component
        self.target_system_id = mav_component.target_system_id
        self.target_component_id = mav_component.target_component_id
        self.message_set = mav_component.message_set
        self.docs = mav_component.docs
        self.connection = self.mav_component.mav_connection.connection

        self._stateGettingAllParameters = False
        self._stateHaveAllParameters = False
        self._gotIndex = False
        self._param_count = None
        self._getAllParamTimer = ResettableTimer(2.0, self._checkRemainingParams) # 2s timer to wait for last param on get all

        # Method to track expected parameters

        self._stateRequestingHashParameter = False
        self.param_hash = None

        self._all_parameters = dict()  # Dictionary of all parameters read from the system
        self._special_parameters = dict() # Special params like HASH - anything with index more than count
        self._pendingParams = dict()  # Parameters we are waiting on.
        self._pendingParamsTimer = IntervalTimer(1.0, self._checkPendingParams) # 1s timer to cycle through waiting params and re-request if needed.


        # Method to track expected parameters


        # Set up tests
        if not hasattr(self.mav_component, "_report"):
            self.mav_component._report = {}
        if "parameter_protocol" not in self.mav_component._report:
            self.mav_component._report["parameter_protocol"] = {
                "min_index": None,
                "param_count": None,
                "_HASH_PARAM": None,
                "capabilities": {"bytewise": None, "c_cast": None},
                "PARAM_ERROR": { "supported": None }
            }

        # Could potentially have a system that added to a main callback thread.
        self.mav_component.mav_connection.add_threaded_message_callback(
            self._messageAccumulator
        )



    def _checkPendingParams(self):
        print("DEBUG: ParameterProtocolManager: _checkPendingParams(): Checking for remaining params ...")
        # Checks for pending parameters (for which we have no response)
        # Then re-requests any that have timed out.
        # Items may be removed from the pending list when we get a response, or will be removed here.

        if len(self._pendingParams) == 0:
            print("DEBUG: there are no pending params.")
            self._pendingParamsTimer.stop()
        print(f"DEBUG: pending params: {len(self._pendingParams)}")

        now = time.time()

        # Iterate over a *copy* since we may modify the original dict
        for param_id_or_index, param in list(self._pendingParams.items()):
            if now - param['timestamp'] > 2:
                if param['request'] >= 3:
                    print(f"Removing {param_id_or_index}: request limit reached ({param['request']})")
                    del self._pendingParams[param_id_or_index]
                else:
                    param['request'] += 1
                    param['timestamp'] = now
                    print(f"Retrying {param_id_or_index}: request={param['request']}")
                    # Start timer and then send message
                    self._pendingParamsTimer.start()
                    self.connection.send(param['msg'])




    def _checkRemainingParams(self):
        #print("DEBUG: ParameterProtocolManager: _checkRemainingParams(): Checking for missing parameters...")
        # Checks for emtpy index values, creates a list of them
        # Then requests each individually.
        # Run when we either think we have all params OR when timer expires indicating we waited too long for next timer.
        indices = [param["index"] for param in self._all_parameters.values()]

        if not indices:
            print("DEBUG: No parameters received yet.")
            return

        # Find the range
        min_index = min(indices)  # 0 indexed - TODO CHECK IN TESTS
        max_index = max(indices)  #
        # TESTS - We have these specials with incorrect index. These are not real maybe

        # Compute missing numbers
        missing = sorted(set(range(min_index, max_index + 1)) - set(indices))
        #print(f"DEBUG: Max/min indices: {min_index}/{max_index}, total received: {len(indices)}, expected: {self._param_count}")

        if missing:
            print(f"Fetching missing params: {len(missing)}")
            # Re-request any missing parameters
            for index in missing:
                print(f"DEBUG: Re-requesting parameter at index {index}")
                self.readOneParameter(id=None, index=index)

        # If no missing, we are done.
        else:
            print("All parameters received.")
            self._stateGettingAllParameters = False
            self._stateHaveAllParameters = True
            self._getAllParamTimer.cancel()  # Stop the timer
            if not self.mav_component._report["parameter_protocol"]["min_index"]:
                self.mav_component._report["parameter_protocol"]["min_index"] = min_index


    def readAllParameters(self):
        """
        Requests (all) parameters from the connected system.
        """
        #print("DEBUG: ParameterProtocolManager.requestParameters(): enter")

        if self._stateGettingAllParameters:
            # We're getting all parameters already.
            # Silently ignore
            return
        print("Reading all parameters ...")
        self._stateGettingAllParameters = True
        self._stateHaveAllParameters = False
        self._param_count = None
        self._all_parameters = dict() # Clear any existing parameters
        # TODO Clear any pending param request and timers.

        # Read hash param:
        # First check if we have the #HASH parameter and if it matches. We should store and cache this.
        # But note that not all systems support this.
        # Also either we will have to calculate it or request at the end to know if it changed?
        """
        if not self._stateRequestingHashParameter:
            self._stateRequestingHashParameter = True
            self.readOneParameter("_HASH_PARAM")
            #TODO Wait for response
        """

        # Re-read all parameters.
        msg = self.message_set.create("PARAM_REQUEST_LIST")
        msg['target_system'] = self.target_system_id
        msg['target_component'] = self.target_component_id

        self.connection.send(msg)
        #start wait timer for params to arrive
        # Gets reset on each message.
        # On expiry we check which params are missing and re-request them.
        self._getAllParamTimer.start()


        #TODO Look at returned PARAM_VALUE messages.
        # Tmeout indicates the end of list
        #Iterate the list to find any that are missing.



    def readOneParameter(self, id, index=-1, callback=None):
        """
        Requests one parameter from the connected system.
        """
        print("Debug: ParameterProtocolManager.readOneParameter(): enter")
        if self._stateGettingAllParameters and index==-1:
            print(f"WARNING: Index must be supplied when reading all parameters (ignoring): {index}")
            return
        if index==-1 and len(id) > 16:
            print(f"ERROR: Parameter id too long (max 16 chars): {id}")
            return
        if index==-1 and len(id) == 0:
            print(f"ERROR: Supply either id or index: {id}")
            return

        def default_callback(msg, read, success):
            action = "read" if read else "write"
            result = "successful" if success else "failed"
            print(f"Parameter {action} {result}: {msg.id}: {value}, {type}")



        msg = self.message_set.create("PARAM_REQUEST_READ")
        msg['target_system'] = self.target_system_id
        msg['target_component'] = self.target_component_id
        msg['param_index'] = index

        if index == -1:
            # Convert the byte string.
            # Assume it is not a byte string in id.
            # Ensure the string does not exceed 16 characters and is encoded as a byte string
            id_truncated = id[:16]
            # Encode the string to bytes
            byte_value = id_truncated.encode('utf-8')
            # Add a null terminator if the length is less than 16
            if len(byte_value) < 16:
                byte_value = byte_value + b'\0'
            msg['param_id'] = byte_value  # Must be 16 chars, null terminated
            # Assumption is that ids cannot/should not be numeric indexes.
            self._pendingParams[id] = { 'index': None, 'id': id, "msg": msg, 'timestamp': time.time(), "request": 1, "read": True, "callback": callback } # Track when we requested it.
        else:
            # Don't need this, but for clarity/safety:
            msg['param_id'] = b'\0' * 16
            # Add to the pending list
            self._pendingParams[index] = { 'index': index, 'id': None, "msg": msg, 'timestamp': time.time(), "request": 1, "read": True, "callback": callback } # Track when we requested it.

        # Start timer and then send message
        self._pendingParamsTimer.start()
        self.connection.send(msg)

    def setParameter(self, id, value, type='MAV_PARAM_TYPE_INT32', callback=None):
        """
        Sets parameter on the connected system.
        """
        print(f"ParameterProtocolManager.sendParameter(): enter: {id}: {value}, {type} ")

        def default_callback(msg, read, success):
            action = "read" if read else "write"
            result = "successful" if success else "failed"
            print(f"Parameter {action} {result}: {msg.id}: {value}, {type}")

        if self._stateGettingAllParameters:
            print(f"WARNING: {id} not sent (busy getting all parameters) Set called while getting all parameters (ignored: {id}).")
            return

        msg = self.message_set.create("PARAM_SET")
        msg['target_system'] = self.target_system_id
        msg['target_component'] = self.target_component_id
        msg['param_value'] = value # TODO need to do type packing here.

        # TODO Get value from retrieved parameters instead/as well as this.
        paramType = self.docs.getEnumEntries("MAV_PARAM_TYPE")[type]['value']
        msg['param_type'] = paramType

        # Ensure the string does not exceed 16 characters and is encoded as a null terminated byte string
        param_id = id[:16].encode('utf-8').ljust(16, b'\0')
        msg['param_id'] = param_id  # Must be 16 chars, null terminated

        #self._pendingParams[param_id] = { 'index': None, 'id': param_id, "msg": msg, 'timestamp': time.time(), "request": 1, "read": False, "callback": callback }
        self._pendingParams[id] = { 'index': None, 'id': param_id, "msg": msg, 'timestamp': time.time(), "request": 1, "read": False, "callback": callback } #

        self.connection.send(msg)


    def _messageAccumulator(self, msg):
        messageName = msg.name
        message_dict = msg.to_dict()
        self.mav_component.msgNotForComponent(message_dict)

        if messageName == "PARAM_VALUE":
            pprint.pprint(f"DEBUG: {message_dict}")
            #param_id = message_dict.param_id.decode('utf-8').rstrip('\0')  # Decode and strip null terminators
            param_id = message_dict["param_id"] #.decode('utf-8').rstrip('\0')  # Decode and strip null terminators TODO TODO!!!
            param_count = message_dict["param_count"]
            param_index = message_dict["param_index"]
            param_value = message_dict["param_value"] # TODO Need to do type conversion here
            param_type = message_dict["param_type"]
            this_param = {
                'value': param_value,  #NOTE TODO - needs to be converted to a number of type
                'type': param_type,  # MAV_PARAM_TYPE
                'index': param_index,
                }

            if self._param_count is None:
                self._param_count = param_count #? -1
            if not self.mav_component._report["parameter_protocol"]["param_count"]:
                self.mav_component._report["parameter_protocol"]["param_count"] = self._param_count

            if self._param_count is not None and self._param_count != param_count:
                print(f"WARNING: Parameter count changed from {self._param_count} to {param_count}") #Should not happen normally.

            # Update our (new) parameter
            if param_index > self._param_count:
                self._special_parameters[param_id] = this_param
                print(f"DEBUG: SPECIAL parameter: {param_id} = {this_param})")
            else:
                self._all_parameters[param_id] = this_param

            # Remove from self._pendingParams if we're waiting on it.
            self._updatePendingResponse(param_index, param_id, param_value, param_type) #TODO - should we send the message?
            if self._stateGettingAllParameters:
                # Check if we have received all parameters
                numParams = len(self._all_parameters)
                #print(f"DEBUG: Param: ind: {param_index},numP {numParams}, pc: {self._param_count} ")
                if param_index < self._param_count and (numParams -1) != param_index:
                    #print(f"DEBUG: WARNING Param: ind: {param_index}, numP (-1): {numParams - 1} ")
                    # This is a valid case - getting params out of order.
                    pass
                if numParams >= self._param_count:
                    #print("All parameters received.")
                    # Call this to do a final check on the index.
                    # It then cleans up and unsets the getting flag
                    self._checkRemainingParams()

                else:
                    self._getAllParamTimer.reset() # We just got a param so reset timer


        elif messageName == "PARAM_ERROR":
            #pprint.pprint(message_dict)
            param_index = message_dict["param_index"]
            param_id = message_dict["param_id"]
            error = message_dict["error"]
            #print(param_index) #DEBUG - assertion of this is that the param name I am adding to the index is not matching because is is the binary form.
            #print(param_id) #DEBUG - assertion of this is that the param name I am adding to the index is not matching because is is the binary form.

            self._updatePendingResponse(param_index, param_id, None, None, error=error)


            if self._stateGettingAllParameters:
                print(f"WARNING: Parameter error when getting all params: {message_dict}")
                # Remove from self._pendingParams if we're waiting on it.
            else:
                # Handle parameter error for individual parameters
                print(f"WARNING: Param error for requested param: {message_dict}")
                #pprint.pprint(self._pendingParams) # this causes and invalid hash due to the function call embedded.

        elif messageName.startswith("PARAM_"):
            print(
                f"WARNING: UNEXPECTED Param message: [{self.target_system_id}:{self.target_component_id}] {messageName} {message_dict}"
            )

    def _updatePendingResponse(self, index, id, value = None, value_type = None, error=None):
        print("ParameterProtocolManager._updatePendingResponse(): enter")

        if index in self._pendingParams:
            callback_response = self._pendingParams[index]["callback"]
            if callback_response:
                response_to_read = self._pendingParams[index]["read"]
                specIndex = True # Could actually check this in the pending params
                #sent_message = self._pendingParams[index]["msg"]
                callback_response(id, index, value, value_type, error, response_to_read, specIndex)
            print(f"DEBUG: deleting {index} from _pendingParams")
            del self._pendingParams[index]

        elif id in self._pendingParams:
            callback_response = self._pendingParams[id]["callback"]
            if callback_response:
                response_to_read = self._pendingParams[id]["read"]
                specIndex = False # Could actually check this in the pending params
                #sent_message = self._pendingParams[index]["msg"]
                callback_response(id, index, value, value_type, error, response_to_read, specIndex)
            print(f"DEBUG: deleting {id} from _pendingParams")
            del self._pendingParams[id]

    def test_callback(self, id, index, value, value_type, error, response_to_read, specIndex):
        print(f"DEBUG default_callback: {id}, {index} {value} {value_type} {error} {response_to_read} {specIndex}")
        action = "read" if response_to_read else "write"
        queryType = index if specIndex else id
        result = f"{id}: {value}, {value_type}" if value else f"ERROR: {error}" #If value is None is an error: TODO make a enum
        print(f"TEST: Parameter {action} of {queryType}: {result}")


    def tests(self):
        """
        Tests
        """
        print("Debug:ParameterProtocolManager.tests(): enter")
        if not self._stateHaveAllParameters:
            print("WARNING: Busy getting all parameters - cannot run tests.")
            return False # Not ready


        self.setParameter("ADSB_GPS_OFF_LAT", 2) # PX4 Valid param but might be invalid value. - need to do generic test
        time.sleep(1)
        self.setParameter("ADSB_GPS_OFF_LAT", 2, 'MAV_PARAM_TYPE_UINT8') # PX4 Valid param invalid type. - need to do generic test
        time.sleep(1)


        self.setParameter("INVALID_NAME", 2, 'MAV_PARAM_TYPE_UINT8', self.test_callback) # Invalid param name and value irrelevent.
        time.sleep(1)
        time.sleep(5)


        return True # Done


