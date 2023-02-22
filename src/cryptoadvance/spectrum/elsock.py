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
    def __init__(
        self, host="127.0.0.1", port=50001, use_ssl=False, callback=None, timeout=10
    ):
        logger.info(f"Initializing ElectrumSocket with {host}:{port} (ssl: {ssl})")
        self._host = host
        self._port = port
        self.use_ssl = use_ssl
        assert type(self._host) == str
        assert type(self._port) == int
        assert type(use_ssl) == bool
        self.running = True
        self._callback = callback
        self._timeout = timeout
        self.establish_socket()
        self._results = {}  # store results of the calls here
        self._requests = []
        self._notifications = []
        self.create_threads()

        self._recv_thread = FlaskThread(target=self.monitor_loop)
        self._recv_thread.daemon = True
        self._recv_thread.start()

    def establish_socket(self):
        if hasattr(self, "_socket"):
            if not self.is_socket_closed():
                self._socket.close()
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        logger.debug(f"socket created  : {self._socket}")
        if self.use_ssl:
            self._socket = ssl.wrap_socket(self._socket)
        logger.debug(f"socket wrapped  : {self._socket}")
        self._socket.settimeout(5)

        self._socket.connect((self._host, self._port))
        logger.debug(f"socket connected: {self._socket}")
        self._socket.settimeout(None)

    def create_threads(self):
        logger.info("Starting ElectrumSocket Threads ...")
        self._recv_thread = FlaskThread(target=self.recv_loop)
        self._recv_thread.daemon = True
        self._recv_thread.start()
        self._write_thread = FlaskThread(target=self.write_loop)
        self._write_thread.daemon = True
        self._write_thread.start()
        self._ping_thread = FlaskThread(target=self.ping_loop)
        self._ping_thread.daemon = True
        self._ping_thread.start()
        self._notify_thread = FlaskThread(target=self.notify_loop)
        self._notify_thread.daemon = True
        self._notify_thread.start()
        logger.info("Finished starting ElectrumSocket Threads")

    def shutdown_threads(self):
        return
        self._recv_thread.stop
        self._write_thread
        self._ping_thread
        self._notify_thread

    def is_socket_closed(self):
        try:
            fd = self._socket.fileno()
        except ValueError:
            return True
        else:
            return False

    def monitor_loop(self):
        sleep = 1
        while self.running:
            while self._ping_thread.is_alive():
                time.sleep(sleep)
            logger.info("recreating socket and threads")
            self.establish_socket()
            self.create_threads()

    def write_loop(self):
        sleep = 0.1
        while self.running:
            while self._requests:
                try:
                    req = self._requests.pop()
                    self._socket.sendall(json.dumps(req).encode() + b"\n")
                    sleep = 0.1
                except Exception as e:
                    logger.error(f"Error in write: {e}")
                    # handle_exception(e)
                    sleep = 3
            time.sleep(sleep)

    def recv_loop(self):
        sleep = 0.1  # This probably heavily impacts the sync-time
        while self.running:
            try:
                self.recv()
                sleep = 0.1
            except Exception as e:
                logger.error(f"Error receiving data: {e}")
                # handle_exception(e)
                sleep = 3
            time.sleep(sleep)

    def ping_loop(self):
        sleep = 10
        tries = 0
        while self.running:
            time.sleep(sleep)

            try:
                self.ping()
                tries = 0
            except ElSockTimeoutException as e:
                tries = tries + 1
                logger.error(
                    f"Error in ping-loop ({tries}th time (requests #{len(self._requests)}, results #{len(self._results)})"
                )
                if tries > 3:
                    logger.error("Ping failure for 60 seconds, Giving up!")
                    return  # will end the thread

    def recv(self):
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

    def notify_loop(self):
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
