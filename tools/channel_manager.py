"""
Run ,,,.
"""

#import libmav
#import time
import pprint
#from collections import deque
#import numpy as np
import threading
import time

# Library for sending commands
from tools import command_sender


KUseLibMAV = True
if KUseLibMAV:
    import libmav


own_mavlink_ids = {
                "system_id": 250, # Some GCS unallocated id
                "component_id": 194 # MAV_COMP_ID_ONBOARD_COMPUTER4 - could be anything
                }


mav_ids_autopilots = [0,1,2,3,5,8,9,10,11,12,13,14,15,16,17,19,20,21,22,23,24,28,29,35,43]
mav_name_autopilots = ['MAV_TYPE_GENERIC', 'MAV_TYPE_FIXED_WING', 'MAV_TYPE_QUADROTOR', 'MAV_TYPE_COAXIAL', 'MAV_TYPE_HELICOPTER', 'MAV_TYPE_AIRSHIP', 'MAV_TYPE_FREE_BALLOON', 'MAV_TYPE_ROCKET', 'MAV_TYPE_GROUND_ROVER', 'MAV_TYPE_SURFACE_BOAT', 'MAV_TYPE_SUBMARINE', 'MAV_TYPE_HEXAROTOR', 'MAV_TYPE_OCTOROTOR', 'MAV_TYPE_TRICOPTER', 'MAV_TYPE_FLAPPING_WING', 'MAV_TYPE_KITE', 'MAV_TYPE_VTOL_TAILSITTER_DUOROTOR', 'MAV_TYPE_VTOL_TAILSITTER_QUADROTOR', 'MAV_TYPE_VTOL_TILTROTOR', 'MAV_TYPE_VTOL_FIXEDROTOR', 'MAV_TYPE_VTOL_TAILSITTER', 'MAV_TYPE_VTOL_TILTWING', 'MAV_TYPE_PARAFOIL', 'MAV_TYPE_DODECAROTOR', 'MAV_TYPE_DECAROTOR', 'MAV_TYPE_GENERIC_MULTIROTOR',  ]


def inspect_object(object):
    print(f"Public API: {type(object).__name__}")
    for attr in dir(object):
        if not attr.startswith('__'):
            value = getattr(object, attr)
            print(f"  {attr} (Value: {value}) (type: {type(value)})")


class ChannelManager:
    """
    A channel is a single connection to a remote system or network,
    which might have multiple MAVLink systems/networks on it.
    The channel is supposed to forward messages between interfaces, if appropriate.
    Given a channel it looks for MAV component heartbeats, and creates mav component objects that you can monitor.

    """
    def __init__(self, connection, mavlinkDocs, libmav_message_set, own_system_id, own_component_id):
        self.channels = None
        #self.connection = connection
        self.docs = mavlinkDocs
        self.message_set = libmav_message_set
        #self.own_system_id = own_system_id # The system ID of this system running the tests/sending commands
        #self.own_component_id = own_component_id  # The component ID of this system running the tests/sending commands

        #self._command_ack_callback_handle = self.connection.add_message_callback(self.ackArrived)

        #dict of command acks we are waiting on + the time when sent
        #self.ackWaiting = dict()
        # Variable to keep track of the timer
        #self.timer = None

    def add_channel(self, mavlinkDocs, libmav_message_set, address=None, port=None, client=True, string=None, library='libmav'):
        #print('debug: add_connection() called')
        channel = Channel(ma)
        connection_port = 14540 # Onboard, data rate: 4000000 B/s on udp port 14580 remote port 14540
        conn_physical = libmav.UDPServer(connection_port)
        pass



class Channel:
    """
    A channel is a single connection to a remote system or network,
    which might have multiple MAVLink systems/networks on it.
    The channel is supposed to forward messages between interfaces, if appropriate.
    Given a channel it looks for MAV component heartbeats, and creates mav component objects that you can monitor.
    """
    def __init__(self, mavlinkDocs, libmav_message_set, address=None, port=None, udp_client=True, string=None, newMavCallback=None, library='libmav'):
        self.docs = mavlinkDocs
        self.libmav_message_set = libmav_message_set
        self.string = string
        self.address= address
        self.port = int(port)
        self.library=library
        self.client = udp_client #client or server
        self.mavComponents = dict() # All components, keyed by sysid
        self.newMavCallback=newMavCallback

        ## Libmav properties
        self.conn_physical = None
        self.conn_runtime = None
        self._all_messages_callback_handle = None
        self.connection = None ## This is the important one - the connected thingy

        # TODO code to check if url string, and use that.

        if 'libmav' == library:
            if udp_client:
                #self.message_set = libmav_message_set
                self.message_set = libmav.MessageSet('./mavlink/message_definitions/v1.0/development.xml') # make settable with some default

                #Create a heartbeat message
                heartbeat_message = self.message_set.create('HEARTBEAT')
                heartbeat_dict = {
                    "type": self.message_set.enum("MAV_TYPE_GCS"),
                    "autopilot": self.message_set.enum("MAV_AUTOPILOT_INVALID"),
                    "base_mode": 0,
                    "custom_mode": 0,
                    "system_status": self.message_set.enum("MAV_STATE_ACTIVE"),
                    "mavlink_version": 2,
                }

                heartbeat_message.set_from_dict(heartbeat_dict)
                self.conn_physical = libmav.UDPServer(self.port)

                pass
            else:
                raise ValueError("Wrong client ")

            self.conn_runtime = libmav.NetworkRuntime(libmav.Identifier(own_mavlink_ids["system_id"], own_mavlink_ids["component_id"]), self.message_set, heartbeat_message, self.conn_physical)
            print("waiting for connection")
            self.connection = self.conn_runtime.await_connection(5000)
            self._all_messages_callback_handle = self.connection.add_message_callback(self.messageInLibmav)
            print("got connection")
            # connection = conn_runtime.await_connection(-1) - waits forever and you get stuck until is a connection
            # connection = conn_runtime.await_connection(0) - "RuntimeError: Timeout while waiting for first connection


        else:
            print("Only libmav supported at moment")
            raise ValueError("Only libmav supported a connection library")



        # Check what is connected
        self.connection_thread = threading.Thread(target=self.check_connections, daemon=True) #thread dies when main thread dies
        self.connection_thread.start()

    def check_connections(self):
        """
        Check all connections on channel in a separate thread
        """

        while True:
            #print("evalthingy")
            current_time = time.monotonic()
            anyConnections = False
            for key, mavcomp in self.mavComponents.items():
                time_since_last_heartbeat = current_time - mavcomp._last_heartbeat
                #print(f"time_since_last_heartbeat: {time_since_last_heartbeat}, connected? {mavcomp.connected}")
                if time_since_last_heartbeat > 5 and mavcomp.connected == True:
                    mavcomp.connectionChanged(False)
                    mavcomp.connected = False
                print(f"connected {mavcomp.connected}, anyConnections {anyConnections}")
                if mavcomp.connected == True:
                    # At least one connection
                    anyConnections = True
                    print(f"2anyConnections {anyConnections}")
            """
            # Don't need this for now, because making this a daemon thread that dies on start.
            if not threading.main_thread().is_alive():
                # I think this stops everything if
                #self.should_run = False
                #self.connection_thread.do_run = False
                self.connection_thread.cancel()
                #break
            """


            time.sleep(1)

        print("exiting check_connections")

    def messageInLibmav(self, msg):
        """Callback for libmav whenever a new message arrives on channel.

        This converts the message into a generic dict that we might use with any underlying engine.
        The new message has fields: _name, _id, _header for the message identity.

        Args:
            msg (libmav.Message): This is a message from libmav engine.
        """
        #print(f"Debug: Channel:messageInLibmav(): msg - {msg.name}")
        # TODO: HERE would do any forwarding required.

        #Convert payload to generic message format of a dict()
        msg_as_dict = msg.to_dict()
        header_as_dict = {attr: getattr(msg.header, attr) for attr in dir(msg.header) if not attr.startswith('_')}
        msg_as_dict["_header"] = header_as_dict
        #pprint.pprint(msg_as_dict)

        # TODO ignore messages with source as self

        self.messageInGeneric(msg_as_dict)


    def messageInGeneric(self, msg):
        """Generic message handler called with dict.

        This is where we start creating components and forwarding them messages.

        Args:
            msg (dict): This is a message from mavlink as a Python dicts
        """
        #print(f"Debug: channel:messageInGeneric: msg - {msg['_name']}")
        #pprint.pprint(msg)

        # TODO
        #1. Look for heartbeats or high latency2, and create a component for them
        # Set the type of object returned based on its type - i.e. for an autopilot, make sure it is a mavcompautopilot thingy.

        ## Discard messages that aren't intended for this us, this GCS/component
        # - i.e. if sent say by our friend component but to some other target
        target_system = msg.get('target_system', 0)
        target_component = msg.get('target_component', 0)

        if target_system==0 and target_component == 0:
            pass # broadcast for everyone
        elif target_system==0 and target_component == own_mavlink_ids["component_id"]:
            pass # broadcast for our component in any system.
        elif target_system==own_mavlink_ids["system_id"] and target_component == 0:
            pass # broadcast for our system - any component.
        elif target_system==own_mavlink_ids["system_id"] and target_component == own_mavlink_ids["component_id"]:
            pass # specifically for our component.
        else:
            printf("message not for our system in generic handler")
            #TODO route to target system and broadcast. MAYBE not here. THink about it.
            return


        msg_sys_id = msg['_header']['system_id']
        msg_comp_id = msg['_header']['component_id']

        # TODO Look for heartbeats and high latency 2 in order to identify new mav systems.
        if msg['_name']=="HEARTBEAT" or msg['_name']=="HIGH_LATENCY2":
            #pprint.pprint(msg)

            mavid=f"{msg_sys_id}_{msg_comp_id}"
            #print(mavid)
            if mavid in self.mavComponents:
                pass
                #print(f"dup: {mavid}")
            else:
                print(f"new: {mavid}")
                mav_type=msg['type']
                #print(mav_type)
                if mav_type in mav_ids_autopilots or msg['_name']=="HIGH_LATENCY2":
                    self.mavComponents[mavid]=MAVAutopilotComponent(channel = self, system_id=msg_sys_id, component_id=msg_comp_id )
                else:
                    self.mavComponents[mavid]=MAVComponent(channel = self, system_id=msg_sys_id, component_id=msg_comp_id )

                # TODO Here callback a thing than wants to know about a new mav_component.
                if self.newMavCallback:
                    self.newMavCallback(self.mavComponents[mavid])


        #Send the messages from a particular mav to be handled
        # by its corresponding mavcomponent object
        for key, mav_component in self.mavComponents.items():
            if mav_component.system_id == msg_sys_id and mav_component.component_id == msg_comp_id:
                mav_component.messageInComponent(msg)


        # Look for heartbeats and high latency 2 in order to identify new mav systems.


class MAVComponent:
    """
    A channel is a single connection to a remote system or network,
    which might have multiple MAVLink systems/networks on it.
    The channel is supposed to forward messages between interfaces, if appropriate.
    Given a channel it looks for MAV component heartbeats, and creates mav component objects that you can monitor.

    """
    def __init__(self, channel, system_id, component_id):
        self.channel = channel
        self.system_id = system_id
        self.component_id = component_id

        # Connection stuff
        self.connected=False
        self._last_heartbeat = None
        self.callback = None

        ## Command sender. Not at all generic.
        self.command_sender = command_sender.CommandSender(connection=self.channel.connection, mavlinkDocs=self.channel.docs, libmav_message_set = self.channel.libmav_message_set, own_system_id=own_mavlink_ids["system_id"], own_component_id=own_mavlink_ids["component_id"])

        # Test code
        request_message_id =  self.channel.libmav_message_set.id_for_message('AUTOPILOT_VERSION') # this could be from docs - that is generic.
        printf(f"request_message_id: {request_message_id}")
        self.command_sender.sendCommandRequestMessageNonBlocking(target_system=self.system_id, target_component=self.component_id, request_message_id=request_message_id)


    def messageInComponent(self, msg):
        """Callback that might be relevant to this particular MAVLink component

        Args:
            msg (dict): This is a message from the channel.
        """
        print(f"Debug: MAVComponent:messageInComponent(): msg - {msg['_name']}")

        if msg['_name']=="HEARTBEAT":
            # Record last heartbeat
            # print("NEW HEARTBEAT")
            self._last_heartbeat=time.monotonic()
            if self.connected == False:
                self.connectionChanged(True)
                self.connected=True

        ## TODO ADD HANDLER TO GET INFO ABOUT TYPE OF VEHICLE

        ## TODO ADD handler to register your own code to handle messages.

    def connectionChanged(self, connecting):
        """Callback for libmav whenever a new message arrives on channel.
        TODO: This should be something we allow to replace
        """
        if connecting == True:
            print(f"Connected: sys: {self.system_id}, comp: {self.component_id}")
        else:
            print(f"Disconnected: sys: {self.system_id}, comp: {self.component_id}")
        if self.callback:
            callback(connecting)

    def addConnectionCallback(self, callback):
        """All users to add a callback for connection changes
        """
        self.callback = callback



class MAVAutopilotComponent(MAVComponent):
    # Additional attributes and methods specific to MAVAutopilotComponent
    def __init__(self, channel, system_id, component_id):
        super().__init__(channel, system_id, component_id)  # Call the parent class's constructor
        # Whatever is specific to one of these.

        #self.requestAutopilotVersion()  # Currently broken

    def requestAutopilotVersion(self):
        """Request autopilot version
        """
        print("debug: MAVComponent: requestAutopilotVersion")
        request_message_id = libmav_message_set.id_for_message('AUTOPILOT_VERSION') # this could be from docs - that is generic.
        self.command_sender.sendCommandRequestMessageNonBlocking(target_system=self.system_id, target_component=self.component_id, request_message_id=request_message_id)

        """
        targetSystem = 1
        targetComponent = message_set.enum("MAV_COMP_ID_AUTOPILOT1") # TODO We should get from our connection.
        request_message_id = message_set.id_for_message('AUTOPILOT_VERSION')
        commander = command_sender.CommandSender(connection=connection, mavlinkDocs=mavlinkDocs, libmav_message_set = message_set, own_system_id=own_mavlink_ids["system_id"], own_component_id=own_mavlink_ids["component_id"])
        commander.sendCommandRequestMessageNonBlocking(target_system=targetSystem, target_component=targetComponent, request_message_id=request_message_id)
        """

    def messageInComponent(self, msg):
        """Callback that might be relevant to this particular MAVLink component

        Args:
            msg (dict): This is a message from the channel.
        """
        print(f"Debug: MAVAutopilotComponent:messageInComponent(): msg - {msg['_name']}")
        super().messageInComponent(msg)  # Call the parent class's constructor


