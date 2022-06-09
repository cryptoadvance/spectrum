import logging
import socket
import ssl
import json
import random
import time
import threading
import sys

# TODO: normal handling of ctrl+C interrupt

logger = logging.getLogger(__name__)

class ElectrumSocket:
    def __init__(self, host="127.0.0.1", port=50001, use_ssl=False, callback=None):
        self._host = host
        self._port = port
        self.running = True
        self._callback = callback
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        if use_ssl:
            self._socket = ssl.wrap_socket(self._socket)
        self._socket.connect((host, port))
        self._results = {}  # store results of the calls here
        self._requests = []
        self._notifications = []
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
        self._waiting = False

    def write_loop(self):
        while self.running:
            while self._requests:
                try:
                    req = self._requests.pop()
                    self._socket.sendall(json.dumps(req).encode() + b"\n")
                except Exception as e:
                    print("Error in write", e)
            time.sleep(0.01)

    def ping_loop(self):
        while self.running:
            time.sleep(10)
            try:
                self.ping()
            except Exception as e:
                print("Error in ping", e)

    def recv_loop(self):
        while self.running:
            try:
                self.recv()
            except Exception as e:
                print("Error receiving data:", e)
            time.sleep(0.1)

    def recv(self):
        while self.running:
            data = self._socket.recv(2048)
            while not data.endswith(b"\n"):
                data += self._socket.recv(2048)
            arr = [json.loads(d.decode()) for d in data.strip().split(b"\n") if d]
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
                print("Error in callback:", e)
        else:
            print("Notification:", data)

    def call(self, method, params=[]):
        uid = random.randint(0, 1 << 32)
        obj = {"jsonrpc": "2.0", "method": method, "params": params, "id": uid}
        self._requests.append(obj)
        while uid not in self._results:  # wait for response
            time.sleep(0.01)
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
        return self.call("server.ping")

    def __del__(self):
        self._socket.close()


def main():
    es = ElectrumSocket()
    res = es.call("blockchain.headers.subscribe")
    print(res)
    es.wait()  # wait for any notification
    res = es.ping()
    print(res)
    while True:
        time.sleep(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
