import threading
import pprint


class ResettableTimer:
    """
    A timer that can be reset. When reset, the timer restarts its countdown.
    If the timer is not reset within the specified interval, the callback function is executed.
    """

    def __init__(self, interval, callback_function, *args, **kwargs):
        """
        Initializes the ResettableTimer.

        Args:
            interval (float): The time in seconds after which the callback_function will be called.
            callback_function (callable): The function to be called when the timer expires.
            *args: Positional arguments to pass to the callback_function.
            **kwargs: Keyword arguments to pass to the callback_function.
        """
        self.interval = interval
        self.callback_function = callback_function
        self.args = args
        self.kwargs = kwargs
        self.timer = None
        self.is_running = False
        # print(f"Timer initialized with interval: {self.interval} seconds.")

    def _start_new_timer(self):
        """
        Internal method to create and start a new threading.Timer.
        """
        # Create a new threading.Timer instance
        self.timer = threading.Timer(self.interval, self._execute_callback)
        # Start the timer in a separate thread
        self.timer.start()
        self.is_running = True
        # print(f"Timer started for {self.interval} seconds.")

    def _execute_callback(self):
        """
        Internal method that is called when the timer expires.
        It executes the user-defined callback function.
        """
        self.is_running = False
        # print("Timer expired! Executing callback function...")
        self.callback_function(*self.args, **self.kwargs)

    def start(self):
        """
        Starts the timer. If it's already running, it will be reset.
        """
        self.reset()

    def reset(self):
        """
        Resets the timer. If the timer is currently running, it cancels the
        existing timer and starts a new one from scratch.
        """
        if self.timer and self.timer.is_alive():
            self.timer.cancel()
            #print("Existing timer cancelled. Resetting...")
        self._start_new_timer()

    def cancel(self):
        """
        Cancels the timer. The callback function will not be executed.
        """
        if self.timer and self.timer.is_alive():
            self.timer.cancel()
            self.is_running = False
            # print("Timer explicitly cancelled.")
        else:
            # print("Timer is not running or already cancelled.")
            pass