# from tools import command_sender
from mavdocs import XMLDialectInfo
import libmav
import time
import threading

from .mavcomponent import MAVComponent
# import pprint
# from collections import deque
# import numpy as np


def inspect_object(object):
    print(f"Public API: {type(object).__name__}")
    for attr in dir(object):
        if not attr.startswith('__'):
            value = getattr(object, attr)
            print(f"  {attr} (Value: {value}) (type: {type(value)})")


class MAVConnection:
    def __init__(self, connection_type='px4wsl2_companion_udp_server', own_system_id=250, own_component_id=194, dialect='development'):
        """Initialize a connection with the desired component IDS of the SDK

        Args:
            own_system_id (_type_, optional): SDK system ID (outbound messages). 250 if not specified.
            own_component_id (_type_, optional): SDK component id (outbound messages). 195 if not specified
            dialect (str, optional): The mavlink dialect to use. Defaults to 'development'.
        """
        # self.connection = connection
        self.own_system_id = own_system_id
        self.own_component_id = own_component_id
        self.dialect = dialect
        self.connection_type = connection_type
        self.connection_thread = None
        self.components = dict()  # Components we know about

        # Create a mavlink docs object for the dialect
        self.docs = XMLDialectInfo(dialect=self.dialect)

        # Create a message set from a mavlink xml file
        self.message_set = libmav.MessageSet(
            f"./mavlink/message_definitions/v1.0/{self.dialect}.xml")

        # Create a heartbeat message for this component on this connection.
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



        # TODO: Convert all of these into a connection string rather than taking from
        if self.connection_type == 'px4wsl2_companion_udp_client':
            connection_address = '172.19.48.140'
            # Onboard, data rate: 4000000 B/s on udp port 14580 remote port 14540
            connection_port = 14580
            conn_physical = libmav.UDPClient(
                connection_address, connection_port)

        # TODO: Convert all of these into a connection string rather than taking from
        if self.connection_type == 'px4wsl2_companion_udp_client':
            connection_address = '172.19.48.140'
            # Onboard, data rate: 4000000 B/s on udp port 14580 remote port 14540
            connection_port = 14580
            conn_physical = libmav.UDPClient(
                connection_address, connection_port)

        # Normal, data rate: 4000000 B/s on udp port 18570 remote port 14550
        if self.connection_type == 'px4wsl2_normal_udp_client':
            connection_address = '172.19.48.140'
            connection_port = 18570  # 18570
            conn_physical = libmav.UDPClient(
                connection_address, connection_port)

        # Normal, data rate: 4000000 B/s on udp port 18570 remote port 14550
        if self.connection_type == 'px4wsl2_normal_udp_server':
            # connection_address = '172.19.48.140'
            connection_port = 14550  # 18570
            conn_physical = libmav.UDPServer(connection_port)

        # Normal, data rate: 4000000 B/s on udp port 18570 remote port 14550
        if self.connection_type == 'px4wsl2_companion_udp_server':
            # connection_address = '172.19.48.140'
            # Onboard, data rate: 4000000 B/s on udp port 14580 remote port 14540
            connection_port = 14540
            conn_physical = libmav.UDPServer(connection_port)

        # Normal, data rate: 4000000 B/s on udp port 18570 remote port 14550
        if self.connection_type == 'ardupilot_wsl2_companion_udp_server':
            connection_address = '127.0.0.1'
            # Onboard, data rate: 4000000 B/s on udp port 14580 remote port 14540
            connection_port = 14540
            conn_physical = libmav.UDPClient(
                connection_address, connection_port)

        # Normal, data rate: 4000000 B/s on udp port 18570 remote port 14550
        if self.connection_type == 'ardupilot_wsl2_companion_tcp_server':
            connection_address = '127.0.0.1'
            # Onboard, data rate: 4000000 B/s on udp port 14580 remote port 14540
            connection_port = 5760
            conn_physical = libmav.TCPClient(         connection_address, connection_port)


        self.conn_runtime = libmav.NetworkRuntime(libmav.Identifier(
            self.own_system_id, self.own_component_id), self.message_set, heartbeat_message, conn_physical)

        # self.connection = conn_runtime.await_connection(5000)

        self.connection = None
        self.running = False  # Flag for the main connection loop
        self.connection_thread = None

        # Dictionary to store active callback threads and their associated data
        # Structure: {unique_callback_id: {'thread': thread_obj, 'stop_event': event_obj, 'mav_callback_id': libmav_id}}
        self._threaded_callbacks = {}
        self._callback_id_counter = 0  # To generate unique IDs for _our_ system

        # Initialize _messageArrived if it's still needed as a default handler
        # If you only want to use add_threaded_message_callback, you can remove this.
        # self._messageArrived = None # Or provide a default empty function

        self.start()
        self.add_threaded_message_callback(self._messageArrived)

    def start(self):
        """Starts the main MAVLink connection in a separate background thread."""
        if self.connection_thread and self.connection_thread.is_alive():
            print("Warning: Main connection thread already started.")
            return

        self.running = True
        self.connection_thread = threading.Thread(
            target=self._run_connection_loop, daemon=True)
        self.connection_thread.start()
        print("MAVConnection: Main connection thread launched.")

    def stop(self):
        """Signals the main background thread and all callback threads to stop and waits for their termination."""
        if not self.running and not self._threaded_callbacks:
            print("MAVConnection: No connections or callbacks are running.")
            return

        print("MAVConnection: Signalling all threads to stop...")

        # Stop the main connection thread
        if self.running:
            self.running = False
            if self.connection_thread and self.connection_thread.is_alive():
                self.connection_thread.join(timeout=5)
                if self.connection_thread.is_alive():
                    print(
                        "Warning: Main MAVConnection thread did not terminate cleanly within timeout.")

        # Stop all individual callback threads
        for callback_wrapper_id in list(self._threaded_callbacks.keys()):
            # This will handle stopping and joining
            self.remove_threaded_message_callback(callback_wrapper_id)

        print("MAVConnection: All threads stopped.")

    def _run_connection_loop(self):
        """
        This method runs in a separate thread. It establishes the MAVLink connection
        and keeps the connection alive. It does NOT register _messageArrived here anymore.
        Callbacks are now handled by add_threaded_message_callback.
        """
        print("Debug: Main connection thread started. Setting up libmav objects...")
        self.connection = self.conn_runtime.await_connection(5000)
        try:
            if self.connection:
                print("Debug: MAVLink connection established!")
                # The main loop simply keeps the connection alive.
                # Message processing for individual callbacks happens in their own threads.
                print("Debug: Entering continuous connection keep-alive loop.")

                while self.running and self.connection.alive():
                    time.sleep(0.05)
                print("Debug: Exiting continuous connection keep-alive loop.")
            else:
                print("Debug: No MAVLink connection established within timeout.")

        except Exception as e:
            print(f"CRITICAL ERROR in main connection thread: {e}")
        finally:
            print("Debug: Main connection thread cleanup.")
            # Ensure the running flag is reset on exit
            self.running = False
            # If libmav requires explicit connection shutdown, do it here.
            # self.connection.close() # if such a method exists

    def _threaded_callback_wrapper(self, callback_func, stop_event):
        """
        A wrapper function to run in a separate thread for each callback.
        This function registers the actual callback with libmav and then
        loops, waiting for the stop_event.
        """
        if not self.connection:
            print(
                f"Error: Cannot register callback {callback_func.__name__} - MAVLink connection not established.")
            return

        try:
            # Register the user's callback with libmav
            mav_callback_handle = self.connection.add_message_callback(
                callback_func)
            print(
                f"Debug: Callback '{callback_func.__name__}' registered with MAVLink handle: {mav_callback_handle}")

            # Store the libmav handle for removal later
            # This requires getting the unique_callback_id for this thread.
            # We'll retrieve it from the dict after starting the thread.
            for wrapper_id, data in self._threaded_callbacks.items():
                if data['thread'] == threading.current_thread():
                    data['mav_callback_id'] = mav_callback_handle
                    break
            else:
                print(
                    "Warning: Could not find current thread in _threaded_callbacks dictionary.")
                return  # Should not happen

            # Keep this thread alive until the stop event is set
            while not stop_event.is_set():
                time.sleep(0.01)  # Small sleep to prevent busy-waiting

            print(
                f"Debug: Callback thread for '{callback_func.__name__}' received stop signal.")

        except Exception as e:
            print(
                f"ERROR in callback thread for {callback_func.__name__}: {e}")
        finally:
            print(
                f"Debug: Callback thread for '{callback_func.__name__}' cleaning up.")
            if self.connection and mav_callback_handle is not None:
                try:
                    self.connection.remove_message_callback(
                        mav_callback_handle)
                    print(
                        f"Debug: MAVLink callback {mav_callback_handle} removed for '{callback_func.__name__}'.")
                except Exception as e:
                    print(
                        f"Error removing MAVLink callback {mav_callback_handle}: {e}")

    def add_threaded_message_callback(self, callBackFunc):
        """
        Adds a new MAVLink message callback that runs in its own separate thread.
        Returns a unique ID for this threaded callback, which can be used to remove it.
        """
        if not self.connection:
            print(
                "Error: MAVLink connection not established. Cannot add threaded callback.")
            return None

        unique_callback_id = self._callback_id_counter
        self._callback_id_counter += 1

        stop_event = threading.Event()
        thread = threading.Thread(
            target=self._threaded_callback_wrapper,
            args=(callBackFunc, stop_event),
            daemon=True
        )

        self._threaded_callbacks[unique_callback_id] = {
            'thread': thread,
            'stop_event': stop_event,
            'mav_callback_id': None  # This will be set inside _threaded_callback_wrapper
        }

        thread.start()
        print(
            f"MAVConnection: Added new threaded callback '{callBackFunc.__name__}' with ID: {unique_callback_id}")
        return unique_callback_id

    def remove_threaded_message_callback(self, callback_id):
        """
        Removes a previously added threaded MAVLink message callback.
        Signals its thread to stop and waits for its termination.
        """
        if callback_id not in self._threaded_callbacks:
            print(
                f"Warning: No threaded callback found with ID: {callback_id}")
            return False

        print(
            f"MAVConnection: Signalling threaded callback {callback_id} to stop...")
        callback_data = self._threaded_callbacks[callback_id]

        stop_event = callback_data['stop_event']
        thread = callback_data['thread']

        stop_event.set()  # Signal the thread to stop

        if thread.is_alive():
            thread.join(timeout=2)  # Give the thread some time to clean up
            if thread.is_alive():
                print(
                    f"Warning: Threaded callback {callback_id} did not terminate cleanly.")

        del self._threaded_callbacks[callback_id]
        print(f"MAVConnection: Threaded callback {callback_id} removed.")
        return True

    def _messageArrived(self, msg):
        # print(f'Debug: mavCon: msg: {msg.name}')
        # TODO: Do we need to think about sequence numbers?
        if msg.name != 'HEARTBEAT':
            return
        message_dict = msg.to_dict()
        sys_id = msg.header.system_id
        comp_id = msg.header.component_id
        comp_autopilot = self.docs.getEnumEntryNameFromId(
            'MAV_AUTOPILOT', message_dict['autopilot'])
        comp_type = self.docs.getEnumEntryNameFromId(
            'MAV_TYPE', message_dict['type'])
        componentKey = f"{sys_id}_{comp_id}"
        if componentKey in self.components:
            comp = self.components[componentKey]
            if comp.mav_type != comp_type or comp.autopilot != comp_autopilot:
                print(
                    f"REMOVING CHANGED MAV Component (Component type or autopilot changed for {componentKey}. Old type: {comp.mav_type}, new type: {comp_type}. Old autopilot: {comp.autopilot}, new autopilot: {comp_autopilot}.")
                del self.components[componentKey]  # Remove component

        if componentKey not in self.components:
            print(f"Debug: mavCon: New component]")
            self.components[componentKey] = MAVComponent(
                mav_connection=self,
                target_system_id=sys_id,
                target_component_id=comp_id,
                mav_type=comp_type,
                autopilot=comp_autopilot
            )
            print(
                f"Debug: mavCon: New component: [sys:{sys_id}/comp{comp_id} - {comp_autopilot}, {comp_type}]")
