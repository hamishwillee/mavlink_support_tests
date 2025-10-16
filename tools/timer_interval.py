import threading
import pprint


class IntervalTimer:
    def __init__(self, interval, func):
        """
        interval: time between calls, in seconds
        func: function to call on each interval
        """
        self.interval = interval
        self.func = func
        self._timer = None
        self._running = False
        self._lock = threading.Lock()

    def _run(self):
        with self._lock:
            if not self._running:
                return
            self.func()
            self._timer = threading.Timer(self.interval, self._run)
            self._timer.start()

    def start(self):
        # If running, return immediately without waiting for the lock.
        if self._running:
            return

        with self._lock:
            if not self._running:
                self._running = True
                self._timer = threading.Timer(self.interval, self._run)
                self._timer.start()

    def stop(self):
        with self._lock:
            self._running = False
            if self._timer:
                self._timer.cancel()
                self._timer = None
