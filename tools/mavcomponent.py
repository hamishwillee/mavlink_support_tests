from .command_sender import CommandSender
#import time
#import threading
import pprint

class MAVComponent:
    def __init__(self, mav_connection, target_system_id, target_component_id, mav_type, autopilot):
        """
        Initialize a MAVComponent object that represents a component of a MAVLink system.
        Data is the connection it is on (a parent MAVConnection object) and identity information
        from the HEARTBEAT message.

        Args:
            mav_connection (MAVConnection): The connection object that this component communicates through
            target_system_id (int): _description_
            target_component_id (int): _description_
            mav_type (str): System type, e.g. 'MAV_TYPE_GCS'
            autopilot (str): Flight controller stack type, e.g. 'MAV_AUTOPILOT_PX4'
        """

        self.mav_connection = mav_connection
        # TODO check type of connection object. Leave if is wrong type.
        # System ID of drone this object is a proxy for (i.e. it is the target system ID for commands)
        self.target_system_id = target_system_id

        # Component ID of drone this object is a proxy for (i.e. it is the target system ID for commands)
        self.target_component_id = target_component_id
        self.mav_type = mav_type
        self.autopilot = autopilot
        self.msg_autopilot_version = None

        self.commander = CommandSender(mav_connection=self.mav_connection)
        print(
            f"Debug: MAVComponent: Created commander with system_id={self.commander.own_system_id} component_id={self.commander.own_component_id}")

        self.mav_connection.add_threaded_message_callback(self._messageArrived)
        self._request_autopilot_version()

    def _request_autopilot_version(self):
        """
        Request the AUTOPILOT_VERSION from this component by sending MAV_CMD_REQUEST_MESSAGE.
        """
        print("Debug: Requesting AUTOPILOT_VERSION from MAVLink system...")
        request_message_id = self.mav_connection.message_set.id_for_message(
            'AUTOPILOT_VERSION')
        self.commander.sendCommandRequestMessageNonBlocking(
            target_system=self.target_system_id, target_component=self.target_component_id, request_message_id=request_message_id)

    def isCapabilitySupported(self, capability):
        # TODO: NOT DONE YET
        """
        Check if the component supports a specific capability.

        Args:
            capability (str): The capability to check, e.g. 'MAV_PROTOCOL_CAPABILITY_MISSION_FLOAT'

        Returns:
            bool: True if the capability is supported, False otherwise.
        """
        if self.msg_autopilot_version and 'capabilities' in self.msg_autopilot_version:
            print(f"Debug: Checking capability '{capability}'")
            caps = self.mav_connection.docs.getEnumEntriesId(
                'MAV_PROTOCOL_CAPABILITY')
            pprint.pprint(caps)
            capability
            return (self.msg_autopilot_version['capabilities'] & capability) != 0
        return None  # Not supported


    def _handle_autopilot_version(self, message_dict):
        """
        Request the AUTOPILOT_VERSION from this component by sending MAV_CMD_REQUEST_MESSAGE.
        """
        pprint.pprint(message_dict)
        if not self.msg_autopilot_version:
            self.msg_autopilot_version = dict()

        # TODO Need to go do all of these and extract info
        self.msg_autopilot_version['capabilities'] = message_dict['capabilities']
        # self.isCapabilitySupported('MAV_PROTOCOL_CAPABILITY_COMMAND_INT')

        self.msg_autopilot_version['flight_sw_version'] = message_dict['flight_sw_version']
        major_version = (
            message_dict['middleware_sw_version'] >> (8 * 3)) & 0xFF
        minor_version = (
            message_dict['middleware_sw_version'] >> (8 * 2)) & 0xFF
        patch_version = (
            message_dict['middleware_sw_version'] >> (8 * 1)) & 0xF
        # Done
        self.msg_autopilot_version[
            'middleware_sw_version'] = f"{major_version}.{minor_version}.{patch_version}"
        self.msg_autopilot_version['flight_custom_version'] = message_dict['flight_custom_version']
        self.msg_autopilot_version['middleware_custom_version'] = message_dict['middleware_custom_version']
        self.msg_autopilot_version['os_custom_version'] = message_dict['os_custom_version']
        self.msg_autopilot_version['os_sw_version'] = message_dict['os_sw_version']
        # comes from https://github.com/PX4/PX4-Bootloader/blob/main/board_types.txt and Ardupilot's board_version.txt
        self.msg_autopilot_version['board_version'] = message_dict['board_version']
        self.msg_autopilot_version['vendor_id'] = message_dict['vendor_id']
        self.msg_autopilot_version['product_id'] = message_dict['product_id']
        self.msg_autopilot_version['uid'] = message_dict['uid']
        self.msg_autopilot_version['uid2'] = message_dict['uid2']

        pprint.pprint(self.msg_autopilot_version)

        # TODO store the other values in AUTOPILOT_VERSION message

    def msgNotForComponent(self, msg_dict):
        # print(f"Debug: MAVComponent: filterForComponent: {msg}")

        if not isinstance(msg_dict, dict):
            print(f"WARNING: MAVComponent: filterForComponent: Not a dict: {msg}")
            exit()

        # Reject any messages intended for other systems (not broadcast and has non-matching id)
        target_system = msg_dict.get('target_system', 0)
        if target_system != 0 and target_system != self.target_system_id:
            print(f"not matching system: {target_system}, {self.target_system_id} ")
            return True
        return False


    def _messageArrived(self, msg):
        # print(f"Debug: MAVComponent: messageArrived: {msg.name}")
        message_dict = msg.to_dict()

        # Reject any messages intended for other systems (not broadcast and has non-matching id)
        if self.msgNotForComponent(message_dict):
            return

        #self.messageAccumulator(msg.name)  # Log the message

        if 'AUTOPILOT_VERSION' in msg.name:
            print(f"Debug: MAVComponent: messageArrived: {msg.name}")
            self._handle_autopilot_version(message_dict)
