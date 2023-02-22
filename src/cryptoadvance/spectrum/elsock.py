import json
import logging
import random
import socket
import ssl
import sys
import threading
import time
from queue import Queue

from .util import FlaskThread, SpectrumException, handle_exception

# TODO: normal handling of ctrl+C interrupt

logger = logging.getLogger(__name__)


class ElSockTimeoutException(Exception):
    pass


class ElectrumSocket:

    tries_threshold = 3  # how many tries the ping might fail before it's giving up
    sleep_ping_loop = 10  # seconds
    sleep_recv_loop = 0.01  # seconds
    sleep_write_loop = 0.01
    timeout = 10  # seconds for the call method

    def __init__(
        self,
        host="127.0.0.1",
        port=50001,
        use_ssl=False,
        callback=None,
        socket_recreation_callback=None,
        timeout=None,
    ):
        """
        Initializes a new instance of the ElectrumSocket class.

        Args:
        - host (str): The hostname of the Electrum server. Default is "127.0.0.1".
        - port (int): The port number of the Electrum server. Default is 50001.
        - use_ssl (bool): Specifies whether to use SSL encryption for the socket connection. Default is False.
        - callback (function): The callback function to call when receiving notifications from the Electrum server. Default is None.
        - timeout (float): The timeout for the socket connection. Default is 10 seconds.

        Returns:
        None
        """
        logger.info(f"Initializing ElectrumSocket with {host}:{port} (ssl: {ssl})")
        self._host = host
        self._port = port
        self._use_ssl = use_ssl
        assert type(self._host) == str
        assert type(self._port) == int
        assert type(self._use_ssl) == bool
        self.running = True
        self._callback = callback
        self._on_recreation_callback = socket_recreation_callback
        self._timeout = timeout if timeout else self.__class__.timeout
        self._establish_socket()
        self._results = {}  # store results of the calls here
        self._requests = []
        self._notifications = []
        self._create_threads()

        # The monitor-thread get extra as it is calling create_threads itself
        self._monitor_thread = create_and_start_bg_thread(self._monitor_loop)

    def _establish_socket(self):
        """Establishes a new socket connection to the specified host and port.

        If a socket connection already exists, it will be closed before creating a new one.
        If SSL encryption is enabled, the socket will be wrapped with SSL.
        The socket timeout is set to 5 seconds before connecting.
        Once connected, the socket timeout is set to None, which means it is a blocking socket.

        Returns:
            None
        """

        # Just to be sure, maybe close it upfront
        if hasattr(self, "_socket"):
            if not self.is_socket_closed():
                self._socket.close()
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        logger.debug(f"socket created  : {self._socket}")
        if self._use_ssl:
            self._socket = ssl.wrap_socket(self._socket)
        logger.debug(f"socket wrapped  : {self._socket}")
        self._socket.settimeout(5)

        self._socket.connect((self._host, self._port))
        logger.debug(f"socket connected: {self._socket}")
        self._socket.settimeout(None)  # That means it's a BLOCKING socket

    def _create_threads(self):
        """
        Creates and starts the threads for:
        * receiving notifications
        * writing requests and reading results
        * sending pings

        Returns:
        None
        """
        self._recv_thread = create_and_start_bg_thread(self.recv_loop)
        self._write_thread = create_and_start_bg_thread(self._write_loop)
        self._ping_thread = create_and_start_bg_thread(self._ping_loop)
        self._notify_thread = create_and_start_bg_thread(self._notify_loop)

    def is_socket_closed(self):
        """Checks whether the socket connection is closed or not.

        Returns:
            True if the socket is closed, False otherwise.
        """
        try:
            fd = self._socket.fileno()
        except ValueError:
            return True
        else:
            return False

    def _monitor_loop(self):
        """
        The loop function for monitoring the socket connection.
        If the ping thread is not alive, the socket connection and threads will be recreated.

        Returns:
        None
        """
        sleep = 1
        while self.running:
            while self._ping_thread.is_alive():
                time.sleep(sleep)
            logger.info("recreating socket and threads")
            self._establish_socket()
            self._create_threads()
            assert not self.is_socket_closed()
            if (
                hasattr(self, "_on_recreation_callback")
                and self._on_recreation_callback is not None
            ):
                logger.debug(
                    f"calling self._on_recreation_callback {self._on_recreation_callback.__name__}"
                )
                self._on_recreation_callback()
            else:
                logger.debug("No reasonable _on_recreation_callback found")

    def _write_loop(self):
        """
        The loop function for writing requests to the Electrum server.

        Returns:
        None
        """
        sleep = self.sleep_write_loop
        while self.running:
            while self._requests:
                try:
                    req = self._requests.pop()
                    self._socket.sendall(json.dumps(req).encode() + b"\n")
                    sleep = self.sleep_write_loop
                except Exception as e:
                    logger.error(f"Error in write: {e.__class__}")
                    # handle_exception(e)
                    sleep = 3
            time.sleep(sleep)

    def recv_loop(self):
        """
        The loop function for receiving data from the Electrum server.

        If the socket breaks, this thread is probably stuck as the thread
        is a blocking thread. So in that case the monitor-loop will simply
        recreate the corresponding thread.

        Returns:
        None
        """
        sleep = self.sleep_recv_loop  # This probably heavily impacts the sync-time
        while self.running:
            try:
                self.recv()
                sleep = self.sleep_recv_loop
            except Exception as e:
                logger.error(f"Error receiving data: {e}")
                sleep = 3
            time.sleep(sleep)

    def _ping_loop(self):
        """
        The loop function for sending ping requests to the Electrum server.

        If the ping fails for tries_threshold, it'll return which will end the
        thread and cause the monitor thread to recreate all other threads.

        Returns:
        None
        """
        tries = 0
        ts = self.ping()
        while self.running:
            time.sleep(self.sleep_ping_loop)
            try:
                self.ping()
                tries = 0
            except ElSockTimeoutException as e:
                tries = tries + 1
                logger.error(
                    f"Error in ping-loop ({tries}th time, next try in {self.sleep_ping_loop} seconds if threshold not met"
                )
                if tries > self.tries_threshold:
                    logger.error(
                        "More than {self.tries_threshold} Ping failures for 60 seconds, Giving up!"
                    )
                    return  # will end the thread

    def recv(self):
        """
        Receives and processes the data from the Electrum server.

        Returns:
        None
        """
        while self.running:
            data = self._socket.recv(2048)
            while not data.endswith(b"\n"):  # b"\n" is the end of the message
                data += self._socket.recv(2048)
            # data looks like this:
            # b'{"jsonrpc": "2.0", "result": {"hex": "...", "height": 761086}, "id": 2210736436}\n'
            arr = [json.loads(d.decode()) for d in data.strip().split(b"\n") if d]
            # arr looks like this
            # [{'jsonrpc': '2.0', 'result': {'hex': '...', 'height': 761086}, 'id': 2210736436}]
            for response in arr:
                if "method" in response:  # notification
                    self._notifications.append(response)
                if "id" in response:  # request
                    self._results[response["id"]] = response

    def _notify_loop(self):
        while self.running:
            while self._notifications:
                data = self._notifications.pop()
                self.notify(data)
            time.sleep(0.02)

    def notify(self, data):
        if self._callback:
            try:
                self._callback(data)
            except Exception as e:
                logger.error(f"Error in callback: {e}")
                handle_exception(e)
        else:
            logger.debug("Notification:", data)

    def call(self, method, params=[]):
        """
        Calls a method on the Electrum server and returns the response.

        Args:
        - method (str): The name of the method to call on the Electrum server.
        - *params: The parameters to pass to the method.
        - timeout (float): The timeout for the request. If not specified, the default timeout of the ElectrumSocket instance will be used.

        Returns:
        dict: The response from the Electrum server.
        """
        uid = random.randint(0, 1 << 32)
        obj = {"jsonrpc": "2.0", "method": method, "params": params, "id": uid}
        self._requests.append(obj)
        start = time.time()

        while uid not in self._results:  # wait for response
            # time.sleep(1)
            time.sleep(0.01)
            if time.time() - start > self._timeout:
                raise ElSockTimeoutException(
                    f"Timeout ({self._timeout} seconds) waiting for {method} on {self._socket}"
                )
        res = self._results.pop(uid)
        if "error" in res:
            raise ValueError(res["error"])
        if "result" in res:
            return res["result"]

    def ping(self):
        start = time.time()
        self.call("server.ping")  # result None
        return time.time() - start

    def __del__(self):
        logger.info("Closing socket ...")
        self._socket.close()


def create_and_start_bg_thread(func):
    """Creates and starts a new background thread that executes the given function.

    The thread is started as a daemon thread, which means it will automatically terminate
    when the main thread exits. The function is executed in the new thread.

    Args:
        func: The function to execute in the background thread.

    Returns:
        None
    """
    thread = FlaskThread(target=func)
    thread.daemon = True
    thread.start()
    logger.info(f"Started bg thread for {func.__name__}")
    return thread
