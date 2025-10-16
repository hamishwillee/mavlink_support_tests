"""
This is an object that allows use of the parameter protocol. UNDER CONSTRUCTION
https://mavlink.io/en/services/parameter.html

"""

import time
import pprint

import functools
import types

import struct  # For decoding/encoding values to/from float

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

        self.byteWiseEncoding = None  # Unknown initially

        self._stateGettingAllParameters = False
        self._stateHaveAllParameters = False
        self._gotIndex = False
        self._param_count = None
        self._getAllParamTimer = ResettableTimer(
            2.0, self._checkRemainingParams
        )  # 2s timer to wait for last param on get all

        # Method to track expected parameters

        self._stateRequestingHashParameter = False
        self.param_hash = None

        self._all_parameters = (
            dict()
        )  # Dictionary of all parameters read from the system
        self._special_parameters = (
            dict()
        )  # Special params like HASH - anything with index more than count
        self._pendingParams = dict()  # Parameters we are waiting on.
        self._pendingParamsTimer = IntervalTimer(
            1.0, self._checkPendingParams
        )  # 1s timer to cycle through waiting params and re-request if needed.

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
                "PARAM_ERROR": {"supported": None},
            }

        # Could potentially have a system that added to a main callback thread.
        self.mav_component.mav_connection.add_threaded_message_callback(
            self._messageAccumulator
        )

    def _checkEncoding(self):
        """
        Checks whether encoding is set.
        Either it has been fetched from msg_autopilot_version (or manually set with setEncoding() method).
        If not fetched or set yet returns False.
        """
        print(
            "DEBUG: ParameterProtocolManager: _checkEncoding(): see if encoding has been fetched yet"
        )
        if self.byteWiseEncoding is not None:
            return True  # Already set
        if self.mav_component.msg_autopilot_version is None:
            print("DEBUG: Protocol support not yet checked")
            return False

        # Protocol support fetched. Check capabilities.
        if self.mav_component.msg_autopilot_version["capabilities"] is not None:
            supports_c_cast = self.mav_component.msg_autopilot_version[
                "capabilities"
            ].get("MAV_PROTOCOL_CAPABILITY_PARAM_ENCODE_C_CAST", False)
            supports_bytewise = self.mav_component.msg_autopilot_version[
                "capabilities"
            ].get("MAV_PROTOCOL_CAPABILITY_PARAM_ENCODE_BYTEWISE", False)

            if supports_c_cast and supports_bytewise:
                print(
                    "ERROR: System indicates it supports both C-cast and byte-wise parameter encoding supported. Cannot continue."
                )
            elif not supports_c_cast and not supports_bytewise:
                print(
                    "ERROR: System indicates it supports neither C-cast nor byte-wise parameter encoding supported. Cannot continue."
                )
            elif supports_c_cast:
                self.byteWiseEncoding = False
            elif supports_bytewise:
                self.byteWiseEncoding = True

        return (
            False
            if self.mav_component.msg_autopilot_version["capabilities"] is None
            else True
        )

    def setEncoding(self, byteWise):
        """
        Sets whether to use byte-wise encoding (True) or C-cast encoding (False).
        This must match the capabilities of the connected system.
        This should be set from the autopilot_version message if available.
        But if not this can be manually set using this method
        """
        print("DEBUG: ParameterProtocolManager: setEncoding(): manually set encoding")
        self.byteWiseEncoding = byteWise

    def _checkPendingParams(self):
        print(
            "DEBUG: ParameterProtocolManager: _checkPendingParams(): Checking for remaining params ..."
        )
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
            if now - param["timestamp"] > 2:
                if param["request"] >= 3:
                    print(
                        f"Removing {param_id_or_index}: request limit reached ({param['request']})"
                    )
                    del self._pendingParams[param_id_or_index]
                else:
                    param["request"] += 1
                    param["timestamp"] = now
                    print(f"Retrying {param_id_or_index}: request={param['request']}")
                    # Start timer and then send message
                    self._pendingParamsTimer.start()
                    self.connection.send(param["msg"])

    def _checkRemainingParams(self):
        # print("DEBUG: ParameterProtocolManager: _checkRemainingParams(): Checking for missing parameters...")
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
        # print(f"DEBUG: Max/min indices: {min_index}/{max_index}, total received: {len(indices)}, expected: {self._param_count}")

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
                self.mav_component._report["parameter_protocol"]["min_index"] = (
                    min_index
                )

    def reset(self):
        """
        Clears all parameters that are cached.
        Returns false if currently getting all parameters and does not clear queue.
        This is because we want to make sure that we don't collect results from a previous update.
        What this means though is that this must be called before setting _stateGettingAllParameters to true.
        """
        # print("DEBUG: ParameterProtocolManager.requestParameters(): enter")
        if not self._stateGettingAllParameters:
            self._stateHaveAllParameters = False
            self._param_count = None
            self.param_hash = None
            self._all_parameters = dict()  # Clear any existing parameters
            # Clear the pending dicts too? TODO Probably.

            return True
        return False

    def readAllParameters(self, hash=None):
        """
        Requests (all) parameters from the connected system.
        #- TODO - check that all params were fetched. If we don't get some, report them at the end in a callback.


        """
        # print("DEBUG: ParameterProtocolManager.requestParameters(): enter")

        if self._stateGettingAllParameters:
            # We're getting all parameters already.
            # Silently ignore
            return

        if self.byteWiseEncoding is None:
            if not self._checkEncoding():
                print(
                    "ERROR: Cannot read parameters - encoding type unknown and cannot be determined."
                )
                return

        if self.param_hash is not None:  # Hash is supported
            # TODO ensure HASH only stored when we have all params and following a get all params.
            if hash == self.param_hash:  # match hash, no need to re-fetch.
                print("DEBUG: Parameters already loaded with matching hash.")
                pass
                return
            if hash is None:
                # No hash passed, but we have a stored hash, so we know hash is supported.
                # Request a new hash and call this metho again with hash supported
                # TODO
                print(
                    "DEBUG: TODO Request new hash to check if parameters are up to date."
                )
                print(
                    "DEBUG: HANDLE if request fails or is an error. Might call this again with a random hash so it doesn't match"
                )
                # Request new hash and call this method again in the callback.
                return  # because we don't want to fetch anything in this.

        # Here we want to fetch parameters.
        # We have verified that we arent' fetching all parameters already, and that either we don't have a hash stored or we do, but the hash does not match.

        print("Reading all parameters ...")
        # Reset state and clear existing parameters
        self._stateGettingAllParameters = True
        self._stateHaveAllParameters = False
        self._param_count = None
        self.param_hash = None  # set then only when getting all parameters
        self._all_parameters = dict()  # Clear any existing parameters
        # TODO Do we need to clear any pending params?

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
        msg["target_system"] = self.target_system_id
        msg["target_component"] = self.target_component_id

        self.connection.send(msg)
        # start wait timer for params to arrive
        # Gets reset on each message.
        # On expiry we check which params are missing and re-request them.
        self._getAllParamTimer.start()

        # TODO Look at returned PARAM_VALUE messages.
        # Tmeout indicates the end of list
        # Iterate the list to find any that are missing.

    def readParameterSync(self, id):
        """
        Requests one parameter from the cache of parameters.
        return the parameter None, if unknown, or the value
        """
        print(f"Debug: ParameterProtocolManager.readParameterSync(): {id}")
        if id in self._all_parameters:
            return self._all_parameters[id]["value"]
        return None

    def readOneParameter(self, id=None, index=-1, callback=None):
        """
        Requests one parameter from the connected system.
        """
        # print(f"Debug: ParameterProtocolManager.readOneParameter(): {id}, {index}")

        if index == -1 and len(id) > 16:
            print(f"ERROR: Parameter id too long (max 16 chars): {id}")
            return
        if index == -1 and (id is None or len(id) == 0):
            print(f"ERROR: Supply either id or index: {id}")
            return
        if not self._stateGettingAllParameters and index > -1:
            print(
                f"WARNING: Id preferred for reading parameters: {index}"  # not sent of getallparams workflow
            )
            # dont return

        # Check if we already have the parameter.
        if index == -1 and id in self._all_parameters:
            # print(f"DEBUG: Parameter {id} already available.")
            parameter = self._all_parameters[id]
            index = -1
            if callback:
                value = parameter["value"]
                value_type = parameter["type"]
                error = None
                response_to_read = True
                specIndex = False
                # sent_message = None
                callback(
                    id, index, value, value_type, error, response_to_read, specIndex
                )
            else:
                pass  # Do nothing if we have no callback.
            return
        if index > -1:  # Check if id is present
            pass
            # If they are searching by index, always request

        # At this point we're just requesting our parameter we don't have.
        # TODO Should we check if it is pending already too? Maybe.
        msg = self.message_set.create("PARAM_REQUEST_READ")
        msg["target_system"] = self.target_system_id
        msg["target_component"] = self.target_component_id
        msg["param_index"] = index

        if index == -1:
            # Convert the byte string.
            # Assume it is not a byte string in id.
            # Ensure the string does not exceed 16 characters and is encoded as a byte string
            id_truncated = id[:16]
            # Encode the string to bytes
            byte_value = id_truncated.encode("utf-8")
            # Add a null terminator if the length is less than 16
            if len(byte_value) < 16:
                byte_value = byte_value + b"\0"
            msg["param_id"] = byte_value  # Must be 16 chars, null terminated
            # Assumption is that ids cannot/should not be numeric indexes.
            self._pendingParams[id] = {
                "index": None,
                "id": id,
                "msg": msg,
                "timestamp": time.time(),
                "request": 1,
                "read": True,
                "callback": callback,
            }  # Track when we requested it.
        else:
            # Don't need this, but for clarity/safety:
            msg["param_id"] = b"\0" * 16
            # Add to the pending list
            self._pendingParams[index] = {
                "index": index,
                "id": None,
                "msg": msg,
                "timestamp": time.time(),
                "request": 1,
                "read": True,
                "callback": callback,
            }  # Track when we requested it.
        # Start timer and then send message
        self._pendingParamsTimer.start()
        self.connection.send(msg)

    def setParameter(self, id, value, param_type=None, callback=None):
        """
        Sets parameter on the connected system.

        Note the param_type is a string - the enum value name
        """
        print(
            f"DEBUG: ParameterProtocolManager.sendParameter(): enter: {id}: {value}, {param_type} "
        )

        if value is None:
            print("ERROR: Set parameter requires a value).")
            return

        if self.byteWiseEncoding is None:
            if not self._checkEncoding():
                print(
                    "ERROR: Cannot set parameters as encoding not known (you can set manually with setEncoding() )."
                )
                return

        if self._stateGettingAllParameters:
            print(
                f"WARNING: {id} not sent (busy getting all parameters) Set called while getting all parameters (ignored: {id})."
            )
            return

        msg = self.message_set.create("PARAM_SET")
        msg["target_system"] = self.target_system_id
        msg["target_component"] = self.target_component_id

        # Get param_type from retrieved parameters if defined and passed value if not
        # Report error if retrieved param overrides passed value
        # Report error if no type known.

        use_param_type = None
        param_type_from_mav = None
        if id in self._all_parameters:
            param_type_from_mav = self._all_parameters[id]["type"]
        elif id in self._special_parameters:
            param_type_from_mav = self._special_parameters[id]["type"]
        if param_type is None and param_type_from_mav is None:
            print(
                f"ERROR: setParameter(): No param_type known for {id}. Fetch param first or pass as argument."
            )
            return

        if param_type_from_mav is not None:
            print(
                f"DEBUG: Use param_type from MAV: {self.docs.getEnumEntryNameFromId('MAV_PARAM_TYPE', param_type_from_mav)}"
            )
            if id in self._all_parameters:
                print(
                    f"DEBUG: the whole info about param from mav: {self._all_parameters[id]}"
                )
            if id in self._special_parameters:
                print(
                    f"DEBUG: the whole info about param from mav: {self._special_parameters[id]}"
                )
            use_param_type = param_type_from_mav
            if param_type is not None and param_type_value != param_type_from_mav:
                print(
                    f"WARNING: param_type {param_type} overridden by type from MAV {self.docs.getEnumEntryNameFromId('MAV_PARAM_TYPE', param_type_from_mav)}"
                )

        else:
            use_param_type = self.docs.getEnumEntryIdFromName("MAV_PARAM_TYPE", param_type)

        msg["param_type"] = use_param_type

        # Convert the value to a float based on the type: From MAVParmDict:mavset() in pymavlink
        # Using byteWiseEncoding True, false, or None to determine which encoding to use
        paramTypeEntries = self.docs.getEnumEntries("MAV_PARAM_TYPE")

        if (
            use_param_type is not None
            and use_param_type != paramTypeEntries["MAV_PARAM_TYPE_REAL32"]["value"]
        ):
            # need to encode as a float for sending
            if use_param_type == paramTypeEntries["MAV_PARAM_TYPE_UINT8"]["value"]:
                vstr = struct.pack(">xxxB", int(value))
            elif use_param_type == paramTypeEntries["MAV_PARAM_TYPE_INT8"]["value"]:
                vstr = struct.pack(">xxxb", int(value))
            elif use_param_type == paramTypeEntries["MAV_PARAM_TYPE_UINT16"]["value"]:
                vstr = struct.pack(">xxH", int(value))
            elif use_param_type == paramTypeEntries["MAV_PARAM_TYPE_INT16"]["value"]:
                vstr = struct.pack(">xxh", int(value))
            elif use_param_type == paramTypeEntries["MAV_PARAM_TYPE_UINT32"]["value"]:
                vstr = struct.pack(">I", int(value))
            elif use_param_type == paramTypeEntries["MAV_PARAM_TYPE_INT32"]["value"]:
                vstr = struct.pack(">i", int(value))
            else:
                print("can't send %s of type %u" % (name, use_param_type))
                return False
            (numeric_value,) = struct.unpack(">f", vstr)
        else:
            if isinstance(value, str) and value.lower().startswith("0x"):
                numeric_value = int(value[2:], 16)
            else:
                numeric_value = float(value)

        msg["param_value"] = numeric_value
        print(f"DEBUG: param_value converted : {value} -> {numeric_value}")

        # Ensure the string does not exceed 16 characters and is encoded as a null terminated byte string
        param_id = id[:16].encode("utf-8").ljust(16, b"\0")
        msg["param_id"] = param_id  # Must be 16 chars, null terminated

        self._pendingParams[id] = {
            "index": None,
            "id": param_id,
            "msg": msg,
            "timestamp": time.time(),
            "request": 1,
            "read": False,
            "callback": callback,
        }

        if id in self._all_parameters:
            # delete the parameter in case it is requested while we wait
            # TODO perhaps instead just mark it as unreadable - might get error back saying it is fine.
            # Not sure - we should get updated value either way. THink current way might be better.
            print(f"DEBUG: deleting {id} from _all_parameters on send")
            del self._all_parameters[id]

        # We should also set timer for expecting return.
        # Perhaps better to invalidate the param rather than delete it, in case we get an error back?
        self.connection.send(msg)

    def _messageAccumulator(self, msg):
        messageName = msg.name
        message_dict = msg.to_dict()
        self.mav_component.msgNotForComponent(message_dict)

        if self.byteWiseEncoding is not None and messageName == "PARAM_VALUE":
            # pprint.pprint(f"DEBUG: message_dict: {message_dict}")
            # param_id = message_dict.param_id.decode('utf-8').rstrip('\0')  # Decode and strip null terminators
            param_id = message_dict[
                "param_id"
            ]  # .decode('utf-8').rstrip('\0')  # Decode and strip null terminators TODO TODO!!!
            param_count = message_dict["param_count"]
            param_index = message_dict["param_index"]
            param_value = message_dict[
                "param_value"
            ]  # TODO Need to do type conversion here
            # Use self.byteWiseEncoding to determine how to convert this value to the correct type.

            print(
                f"TODO URGENT - start saving the proper values - need to do conversion of types."
            )
            param_type = message_dict["param_type"]
            this_param = {
                "value": param_value,  # NOTE TODO - needs to be converted to a number of type
                "type": param_type,  # MAV_PARAM_TYPE
                "index": param_index,
            }

            if self._param_count is None:
                self._param_count = param_count  # ? -1
            if not self.mav_component._report["parameter_protocol"]["param_count"]:
                self.mav_component._report["parameter_protocol"]["param_count"] = (
                    self._param_count
                )

            if self._param_count is not None and self._param_count != param_count:
                print(
                    f"WARNING: Parameter count changed from {self._param_count} to {param_count}"
                )  # Should not happen normally.

            # Update our (new) parameter
            # TODO might need to look at this - report them perhaps.
            if param_index > self._param_count:
                self._special_parameters[param_id] = this_param
                print(f"DEBUG: SPECIAL parameter: {param_id} = {this_param})")
            else:
                self._all_parameters[param_id] = this_param

            # Remove from self._pendingParams if we're waiting on it.
            self._updatePendingResponse(
                param_index, param_id, param_value, param_type
            )  # TODO - should we send the message?
            if self._stateGettingAllParameters:
                # Save the hash parameter if we get it as part of this set.
                if param_id == "_HASH_CHECK":
                    self.param_hash = param_value
                    print(
                        f"DEBUG: Parameter hash received (_HASH_CHECK): {self.param_hash}"
                    )
                    self.mav_component._report["parameter_protocol"]["_HASH_CHECK"] = (
                        self.param_hash
                    )
                # Check if we have received all parameters
                numParams = len(self._all_parameters)
                # print(f"DEBUG: Param: ind: {param_index},numP {numParams}, pc: {self._param_count} ")
                if param_index < self._param_count and (numParams - 1) != param_index:
                    # print(f"DEBUG: WARNING Param: ind: {param_index}, numP (-1): {numParams - 1} ")
                    # This is a valid case - getting params out of order.
                    pass
                if numParams >= self._param_count:
                    # print("All parameters received.")
                    # Call this to do a final check on the index.
                    # It then cleans up and unsets the getting flag
                    # Note that at this point it will fetch all the params individually
                    self._checkRemainingParams()

                else:
                    self._getAllParamTimer.reset()  # We just got a param so reset timer

        elif messageName == "PARAM_ERROR":
            # pprint.pprint(message_dict)
            param_index = message_dict["param_index"]
            param_id = message_dict["param_id"]
            error = message_dict["error"]
            # print(param_index) #DEBUG - assertion of this is that the param name I am adding to the index is not matching because is is the binary form.
            # print(param_id) #DEBUG - assertion of this is that the param name I am adding to the index is not matching because is is the binary form.

            self._updatePendingResponse(param_index, param_id, None, None, error=error)

            if self._stateGettingAllParameters:
                print(
                    f"WARNING: Parameter error when getting all params: {message_dict}"
                )
                # Remove from self._pendingParams if we're waiting on it.
            else:
                # Handle parameter error for individual parameters
                print(f"WARNING: Param error for requested param: {message_dict}")
                # pprint.pprint(self._pendingParams) # this causes and invalid hash due to the function call embedded.

        elif messageName.startswith("PARAM_"):
            print(
                f"WARNING: UNEXPECTED Param message: [{self.target_system_id}:{self.target_component_id}] {messageName} {message_dict}"
            )

    def _updatePendingResponse(
        self, index, id, value=None, value_type=None, error=None
    ):
        # print("ParameterProtocolManager._updatePendingResponse(): enter")

        if index in self._pendingParams:
            callback_response = self._pendingParams[index]["callback"]
            if callback_response:
                response_to_read = self._pendingParams[index]["read"]
                specIndex = True  # Could actually check this in the pending params
                # sent_message = self._pendingParams[index]["msg"]
                callback_response(
                    id, index, value, value_type, error, response_to_read, specIndex
                )
            # print(f"DEBUG: deleting {index} from _pendingParams")
            del self._pendingParams[index]

        elif id in self._pendingParams:
            callback_response = self._pendingParams[id]["callback"]
            if callback_response:
                response_to_read = self._pendingParams[id]["read"]
                specIndex = False  # Could actually check this in the pending params
                # sent_message = self._pendingParams[index]["msg"]
                callback_response(
                    id, index, value, value_type, error, response_to_read, specIndex
                )
            # print(f"DEBUG: deleting {id} from _pendingParams")
            del self._pendingParams[id]

    def test_callback(
        self, id, index, value, value_type, error, response_to_read, specIndex
    ):
        print(
            f"DEBUG:test_callback: {id}, {index} {value} {value_type} {error} {response_to_read} {specIndex}"
        )
        action = "read" if response_to_read else "write"
        queryType = index if specIndex else id
        result = (
            f"{id}: {value}, {value_type}" if error is None else f"ERROR: {error}"
        )  # If value is None is an error: TODO make a enum
        print(f"TEST: Parameter {action} of {queryType}: {result}")

    def tests(self):
        """
        Tests
        """
        print("Debug:ParameterProtocolManager.tests(): enter")

        time.sleep(5)

        self.setParameter(
            "ADSB_GPS_OFF_LAT", 2, "MAV_PARAM_TYPE_UINT8", self.test_callback
        )  # PX4 Valid param invalid type. - need to do generic test
        time.sleep(1)

        self.setParameter(
            "INVALID_NAME", 2, "MAV_PARAM_TYPE_UINT8", self.test_callback
        )  # Invalid param name and value irrelevent.
        time.sleep(1)

        self.setParameter(
            "BAT1_V_EMPTY", 0, None, self.test_callback
        )  # PX4 Valid param but might be invalid value. - need to do generic test

        self.readAllParameters()

        time.sleep(10)
        self.setParameter(
            "_HASH_CHECK", 2, None, self.test_callback
        )  # Is valid-ish but should return read only on PX4 and probably not supported on ArduPilot.

        """
        self.setParameter(
            "ADSB_GPS_OFF_LAT", 2
        )  # Is valid-ish but should return read only on PX4 and probably not supported on ArduPilot.



        if self._stateGettingAllParameters:
            print("WARNING: Busy getting all parameters - cannot run tests.")
            return False  # Not ready

        self.setParameter(
            "ADSB_GPS_OFF_LAT", 1
        )  # PX4 Valid param but might be invalid value. - need to do generic test

        print("Debug:ParameterProtocolManager - setparam")


        print("TEST: Reading a few ids in order")
        self.readOneParameter(id=None, index=5, callback=self.test_callback)
        time.sleep(1)

        self.readOneParameter(id=None, index=6, callback=self.test_callback)
        time.sleep(1)

        self.readOneParameter(id=None, index=7, callback=self.test_callback)
        time.sleep(2)


        self.readOneParameter(id="BAT1_V_EMPTY", index=-1, callback=self.test_callback)
        time.sleep(2)

        self.readOneParameter("WV_GAIN", -1, self.test_callback)
        time.sleep(1)

        self.readOneParameter("DOES_NOT_EXIST", -1, self.test_callback)
        time.sleep(1)

        self.readOneParameter("DOES_NOT_EXIS2", -1, self.test_callback)
        time.sleep(1)

        self.readOneParameter("ADSB_GPS_OFF_LON", -1, self.test_callback)
        time.sleep(1)

        self.setParameter(
            "ADSB_GPS_OFF_LAT", 2
        )  # PX4 Valid param but might be invalid value. - need to do generic test
        time.sleep(1)

        """

        time.sleep(5)

        return True  # Done

    """
    ARCHITECTURE TODO
    - The new message callback is called in a separate thread. Would be good to allow it to be called in a master thread.
    BUT to allow this it can't ever return - as this would exit the master thread, exiting all other message handlers.
    Need to work out a way to test that it always returns.
    Also perhaps run it in that thread belonging to the mav component by default.


    """
