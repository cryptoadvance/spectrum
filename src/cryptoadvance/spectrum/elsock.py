import logging
import socket
import ssl
import json
import random
import time
import threading
import sys
from .util import SpectrumException, handle_exception

# TODO: normal handling of ctrl+C interrupt

logger = logging.getLogger(__name__)

class ElectrumSocket:
    def __init__(self, host="127.0.0.1", port=50001, use_ssl=False, callback=None, timeout=10):
        logger.info(f"Initializing ElectrumSocket with {host}:{port} (ssl: {ssl})")
        self._host = host
        self._port = port
        assert type(self._host) == str
        assert type(self._port) == int
        assert type(use_ssl) == bool
        self.running = True
        self._callback = callback
        self._timeout = timeout
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        if use_ssl:
            self._socket = ssl.wrap_socket(self._socket)
        self._socket.settimeout(5)
        self._socket.connect((host, port))
        self._socket.settimeout(None)
        self._results = {}  # store results of the calls here
        self._requests = []
        self._notifications = []
        logger.info("Starting ElectrumSocket Threads ...")
        self._recv_thread = threading.Thread(target=self.recv_loop)
        self._recv_thread.daemon = True
        self._recv_thread.start()
        self._write_thread = threading.Thread(target=self.write_loop)
        self._write_thread.daemon = True
        self._write_thread.start()
        self._ping_thread = threading.Thread(target=self.ping_loop)
        self._ping_thread.daemon = True
        self._ping_thread.start()
        self._notify_thread = threading.Thread(target=self.notify_loop)
        self._notify_thread.daemon = True
        self._notify_thread.start()
        logger.info("Finished starting ElectrumSocket Threads")
        self._waiting = False

    def write_loop(self):
        while self.running:
            while self._requests:
                try:
                    req = self._requests.pop()
                    self._socket.sendall(json.dumps(req).encode() + b"\n")
                except Exception as e:
                    logger.error("Error in write", e)
                    handle_exception(e)
            time.sleep(0.01)

    def ping_loop(self):
        while self.running:
            time.sleep(10)
            tries = 0
            try:
                self.ping()
                tries = 0
            except Exception as e:
                tries = tries + 1
                logger.error("Error in ping", e)
                if tries > 10:
                    logger.fatal("Ping failure. I guess we lost the connection. What to do now?!")
                handle_exception(e)

    def recv_loop(self):
        while self.running:
            try:
                self.recv()
            except Exception as e:
                logger.error(f"Error receiving data: {e}")
                handle_exception(e)
            time.sleep(0.1)

    def recv(self):
        while self.running:
            data = self._socket.recv(2048)
            while not data.endswith(b"\n"): # b"\n" is the end of the message
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
        self._waiting = False  # any notification resets waiting
        if self._callback:
            try:
                self._callback(data)
            except Exception as e:
                logger.error("Error in callback:", e)
                handle_exception(e)
        else:
            logger.debug("Notification:", data)

    def call(self, method, params=[]):
        uid = random.randint(0, 1 << 32)
        obj = {"jsonrpc": "2.0", "method": method, "params": params, "id": uid}
        self._requests.append(obj)
        start = time.time()
        
        while uid not in self._results:  # wait for response
            #time.sleep(1)
            time.sleep(0.01)
            if time.time() - start > self._timeout:
                raise SpectrumException(f"Timeout ({self._timeout} seconds) waiting for {method} on {self._socket}")
        res = self._results.pop(uid)
        if "error" in res:
            raise ValueError(res["error"])
        if "result" in res:
            return res["result"]
        

    def wait(self):
        self._waiting = True
        while self._waiting:
            time.sleep(0.01)

    def ping(self):
        start = time.time()
        self.call("server.ping") # result None
        return time.time() - start


    def __del__(self):
        logger.info("Closing socket ...")
        self._socket.close()


