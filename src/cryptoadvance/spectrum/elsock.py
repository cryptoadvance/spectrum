import json
import logging
import random
import socket
import socks
import ssl
import sys
import threading
import time
from queue import Queue

from .util import FlaskThread, SpectrumInternalException, handle_exception

# TODO: normal handling of ctrl+C interrupt

logger = logging.getLogger(__name__)


class ElSockTimeoutException(Exception):
    """Called in different contexts where a timeout is relevant"""

    pass


class ElectrumSocket:
    """An Electrum protocol implementation based on threads
    Supports ssl, tor and uses callbacks for notification
    and a callback if the socket has been recreated.

    ### Implementation description

    This uses a _monitor_thread which is creating/controlling 4 other more technical threads:
    * the write and recv threads are reading from self._requests and writing to self._results
    ( and writing to self._notifications for new blocks and new states of scripts )
    * the notify thread is reading from self._notifications and callback for those
    * the ping-loop is uses the call-method to ping the electrum server. If it's failing for tries_threshold
    it'll exit

    All of those threads are background-threads.

    If any of the above threads exits (probably the ping-thread as some canary in the coalmine)
    the monitor-loop will detect that and recreate everything (simply spoken).


    """

    # fmt: off
    call_timeout        = 10    # the most relevant timeout as it affects business-methods (using the call-method)
    sleep_ping_loop     = 10    # every x seconds we test the ability to call (ping)
    tries_threshold     = 3     # how many tries the ping might fail before it's giving up (monitor-loop will reestablish connection then)

    sleep_recv_loop     = 0.01  # seconds , the shorter the better performance but 0.001 might be much worse
    sleep_write_loop    = 0.01  # seconds , the shorter the better performance but 0.001 might be much worse
    socket_timeout      = 10    # seconds for self._socket.recv(2048) (won't show up in the logs)
    # fmt: on

    def __init__(
        self,
        host="127.0.0.1",
        port=50001,
        use_ssl=False,
        callback=None,
        socket_recreation_callback=None,
        socket_timeout=None,
        call_timeout=None,
        proxy_url=None,
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
        logger.info(
            f"Initializing ElectrumSocket with {host}:{port} (ssl: {ssl}) (proxy: {proxy_url})"
        )
        self._host = host
        self._port = port
        self._use_ssl = use_ssl
        self.proxy_url = proxy_url
        assert type(self._host) == str
        assert type(self._port) == int
        assert type(self._use_ssl) == bool
        self.running = True
        self._callback = callback
        self._socket_timeout = (
            socket_timeout if socket_timeout else self.__class__.socket_timeout
        )
        self._call_timeout = (
            call_timeout if call_timeout else self.__class__.call_timeout
        )

        self._results = {}  # store results of the calls here
        self._requests = []
        self._notifications = []
        # The monitor-thread will create the other threads
        self._monitor_thread = create_and_start_bg_thread(self._monitor_loop)
        while not (self.status == "ok" or self.status.startswith("broken_")):
            time.sleep(0.2)
        # Preventing to execute that callback for the first time
        # as the spectrum can't use the connection (we're in the constructor),
        # therefore setting it at the very end:
        self._on_recreation_callback = socket_recreation_callback

    @property
    def status(self) -> str:
        """Check the _monitor_loop for valid stati"""
        if hasattr(self, "_status"):
            return self._status
        return "unknown"

    @status.setter
    def status(self, value: str):
        """Check the _monitor_loop for valid stati"""
        logger.info(f"ElectrumSocket Status changed from {self.status} to {value}")
        self._status = value

    @property
    def uses_tor(self) -> bool:
        """Whether the underlying socket is using tor"""
        if hasattr(self, "_uses_tor"):
            return self._uses_tor
        return False

    @uses_tor.setter
    def uses_tor(self, value: bool):
        self._uses_tor = value

    def _establish_socket(self) -> bool:
        """Establishes a new socket connection to the specified host and port.

        If a socket connection already exists, it will be closed before creating a new one.
        If SSL encryption is enabled, the socket will be wrapped with SSL.
        The socket_timeout is set to 5 seconds before connecting.
        Once connected, the socket timeout is set to self._socket_timeout, which means it
        is a non blocking socket.

        Returns:
            boolean if successfull
        """

        # Just to be sure, maybe close it upfront
        try:
            # close if open
            if hasattr(self, "_socket"):
                if not self.is_socket_closed():
                    self._socket.close()

            # maybe use tor
            if self.proxy_url:
                try:
                    ip, port = parse_proxy_url(self.proxy_url)
                    socks.set_default_proxy(socks.PROXY_TYPE_SOCKS5, ip, port, True)
                    self.uses_tor = True
                except SpectrumInternalException as e:
                    logger.error(f"Cannot use proxy_url : {e}")
                    self.uses_tor = False
                    self._socket.settimeout(5)
            else:
                self.uses_tor = False

            self._socket = (
                socks.socksocket(socket.AF_INET, socket.SOCK_STREAM)
                if self.uses_tor
                else socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            )
            self._socket.settimeout(20 if self.uses_tor else 5)
            self._call_timeout = (
                self._call_timeout * 4 if self.uses_tor else self._call_timeout
            )

            logger.debug(f"socket created  : {self._socket}")

            # maybe use ssl
            if self._use_ssl:
                self._socket = ssl.wrap_socket(self._socket)
                logger.debug(f"socket wrapped  : {self._socket}")

            try:
                logger.info(f"Connecting to {self._host}:{self._port}")
                self._socket.connect((self._host, int(self._port)))
            except socket.gaierror as e:
                logger.error(f"Internet connection might not be up: {e}")
                return False
            except socks.GeneralProxyError as e:
                logger.error(f"Tor issue: {e}")
                return False
            logger.debug(f"socket connected: {self._socket}")
            self._socket.settimeout(
                self._socket_timeout
            )  # That means it's a NON-BLOCKING socket
            logger.info(
                f"Successfully created Socket {self._socket} (ssl={self._use_ssl}/tor={self.uses_tor})"
            )
            return True
        except Exception as e:
            logger.exception(e)
            return False

    def _create_threads(self) -> bool:
        """
        Creates and starts the threads for:
        * receiving notifications
        * writing requests and reading results
        * sending pings

        Returns:
        boolean if successfull
        """
        try:
            self._recv_thread = create_and_start_bg_thread(self.recv_loop)
            self._write_thread = create_and_start_bg_thread(self._write_loop)
            self._ping_thread = create_and_start_bg_thread(self._ping_loop)
            self._notify_thread = create_and_start_bg_thread(self._notify_loop)
            return True
        except Exception as e:
            logger.exception()
            return False

    def is_socket_closed(self) -> bool:
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
        An endless loop function for monitoring the socket connection.
        If the ping thread is not alive, the socket connection and threads will be recreated via walking through
        this state-machine:

        [![](https://mermaid.ink/img/pako:eNqNkrFuwzAMRH_F4BjES0cPmdKxU7dGgcFITCJIFgOZKhoY_vcqVtoihWtUk8R7PAo4DqDZEDTQCwptLZ4idvX7kwpVPrvVvqrrTaUjodhwanvWjqSI7CbtENlRaJ31_kbIObOmL8i89rflr-Ij-OA8R96nzTrPa_8ZsPjpBZY-SCehNlKROU9H7w-oXelaACYDdrCGjmKH1uSAhluXAjlTRwqafDV0xORFgQpjRtPF5AifjRWO0BzR97QGTMKv16ChkZjoC7rn_E1dMLwx_7xpMnkpmzEtyPgJFpXCuw?type=png)](https://mermaid-js.github.io/mermaid-live-editor/edit#pako:eNqNkrFuwzAMRH_F4BjES0cPmdKxU7dGgcFITCJIFgOZKhoY_vcqVtoihWtUk8R7PAo4DqDZEDTQCwptLZ4idvX7kwpVPrvVvqrrTaUjodhwanvWjqSI7CbtENlRaJ31_kbIObOmL8i89rflr-Ij-OA8R96nzTrPa_8ZsPjpBZY-SCehNlKROU9H7w-oXelaACYDdrCGjmKH1uSAhluXAjlTRwqafDV0xORFgQpjRtPF5AifjRWO0BzR97QGTMKv16ChkZjoC7rn_E1dMLwx_7xpMnkpmzEtyPgJFpXCuw)

        The states are stored in the `ElectrumSocket.state` property. The Constructor of the `ElectrumSocket` is hardly doing more than just setting up the `_monitor_thread` which is an endless loop going through these states:
        * `creating_sockets` will create the sockets and pass to `creating_threads` or to `broken_creating_sockets` if that fails
        * `broken_creating_sockets` will try to create the socket and sleep for some time if that fails (and endlessly try to do that)
        * `creating_threads` will create the write/recv/ping/notify threads and start them
        * `execute_recreation_callback` will call that callback after setting the status to `ok`
        * the `ok` state will now simply check the other thready and if one of them is no longer alive (probably the ping-thread as he will exit if ping fails for 4 times) it will transition to `broken_killing_threads`
        * `broken_killing_threads` will set `self.running` to false and wait for the threads to terminate. Especially the `recv` thread might not terminate until he get internet connection (again). This might take forever. If all threads are terminated, it will transition to `creating_socket`

        """

        self.status = "creating_socket"
        while True:  # Endless loop
            try:
                time.sleep(1)
                if (
                    self.status == "creating_socket"
                    or self.status == "broken_creating_socket"
                ):
                    logger.info("(re-)creating socket ...")
                    if not self._establish_socket():
                        if self.status == "broken_creating_socket":
                            time.sleep(10)
                        else:
                            # don't sleep in order to speed up the boot time
                            self.status = "broken_creating_socket"
                        continue
                    self.status = "creating_threads"

                if self.status == "creating_threads":
                    if self.is_socket_closed():
                        logger.error("Detected broken socket while creating_threads")
                        self.status = "creating_socket"
                        continue
                    logger.info("(re-)creating threads ...")
                    if not self._create_threads():
                        time.sleep(10)
                        continue
                    self.status = "execute_recreation_callback"

                if self.status == "execute_recreation_callback":
                    # set the new status here before we call the callback
                    # otherwise the receiving code might be confused why called
                    self.status = "ok"
                    if (
                        hasattr(self, "_on_recreation_callback")
                        and self._on_recreation_callback is not None
                    ):
                        logger.debug(
                            f"calling self._on_recreation_callback {self._on_recreation_callback.__name__}"
                        )
                        try:
                            self._on_recreation_callback()
                        except Exception as e:
                            logger.error(
                                "_on_recreation_callback threw an exception {e}"
                            )
                            logger.exception(e)
                    else:
                        logger.debug("No reasonable _on_recreation_callback found")

                if self.status == "ok":
                    while self.thread_status[
                        "all_alive"
                    ]:  # most relevant is the ping_status
                        time.sleep(1)
                    self.status = "broken_killing_threads"
                    logger.info(
                        f"Issue with Electrum deteted, threads died: {','.join(self.thread_status['not_alive'])}"
                    )

                if self.status == "broken_killing_threads":
                    logger.info("trying to stop all threads ...")
                    self.running = False
                    # self._socket.setblocking(False)
                    counter = 0
                    log_frequency = 2
                    while self.thread_status["any_alive"]:
                        # Should we have a timeout? What to do then?
                        if counter % log_frequency == 0:
                            logger.info(
                                f"Waiting for those threads to exit: {' '.join(self.thread_status['alive'])} ({counter}/{log_frequency})"
                            )
                            if counter > 10:
                                log_frequency += 1
                        time.sleep(5)
                        counter += 1
                    self.status = "creating_socket"
                    self.running = True

            except Exception as e:
                logger.error(
                    "Monitoring Loop of Electrum-Socket got an Exception. This is critical if it's happening often!"
                )
                logger.exception(e)
                time.sleep(
                    3
                )  # to prevent high cpu load if this exception will occur endlessly

    @property
    def thread_status(self) -> dict:
        """Returning a handy dict containing all informations about the current
        thread_status.
        e.g.:
        {
            'alive': ['recv', 'write', 'ping', 'notify'],
            'not_alive': [],
            'all_alive': True, 'any_alive': True,
            'not_all_alive': False, 'not_any_alive': False,
            'notify': True, 'ping': True, 'recv': True, 'write': True}
        }
        """
        status_dict = {
            "recv": self._recv_thread.is_alive()
            if hasattr(self, "_recv_thread") and self._recv_thread
            else False,
            "write": self._write_thread.is_alive()
            if hasattr(self, "_write_thread") and self._write_thread
            else False,
            "ping": self._ping_thread.is_alive()
            if hasattr(self, "_ping_thread") and self._ping_thread
            else False,
            "notify": self._notify_thread.is_alive()
            if hasattr(self, "_notify_thread") and self._notify_thread
            else False,
        }
        any_alive = any(status_dict.values())
        all_alive = all(status_dict.values())
        alive_list = [key for key, value in status_dict.items() if value]
        not_alive_list = [key for key, value in status_dict.items() if not value]
        status_dict["alive"] = alive_list
        status_dict["not_alive"] = not_alive_list
        status_dict["any_alive"] = any_alive
        status_dict["not_any_alive"] = not any_alive
        status_dict["all_alive"] = all_alive
        status_dict["not_all_alive"] = not all_alive
        return status_dict

    def _write_loop(self):
        """
        The loop function for writing requests to the Electrum server.
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
        logger.info("Ended write-loop")

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
        read_counter = 0
        timeout_counter = 0
        while self.running:
            try:
                data = self._socket.recv(2048)
                read_counter += 1
            except TimeoutError:
                pass
                # This might happen quite often as we're using a non-blocking socket here.
                # And if no data is there to read from and the timeout is reached, we'll
                # get this error. However it's not a real error-condition (imho)

                # As i'm not 100% sure about that stuff, i'll keep that code around to uncomment any time:
                # timeout_counter += 1
                # logger.error(
                #     f"Timeout in recv-loop, happens in {timeout_counter}/{read_counter} * 100 = {timeout_counter/read_counter * 100 }% of all reads. "
                # )
                # logger.error(f"consider to increase socket_timeout which is currently {self._socket_timeout}")

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
            time.sleep(sleep)
        logger.info("Ended recv-loop")

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
                    f"Timeout in ping-loop ({tries}th time, next try in {self.sleep_ping_loop} seconds if threshold not met"
                )
                if tries > self.tries_threshold:
                    logger.error(
                        f"More than {self.tries_threshold} Ping failures for {self.tries_threshold * self.sleep_ping_loop} seconds, Giving up!"
                    )
                    return  # will end the thread

    def _notify_loop(self):
        while self.running:
            while self._notifications:
                data = self._notifications.pop()
                self.notify(data)
            time.sleep(0.02)
        logger.info("Ended notify-loop")

    def notify(self, data):
        if self._callback:
            try:
                self._callback(data)
            except Exception as e:
                logger.error(f"Error in callback: {e}")
                handle_exception(e)
        else:
            logger.debug("Notification:", data)

    def call(self, method, params=[]) -> dict:
        """
        Calls a method on the Electrum server and returns the response.

        Args:
        - method (str): The name of the method to call on the Electrum server.
        - *params: The parameters to pass to the method.


        Returns:
        dict: The response from the Electrum server.

        might raise a ElSockTimeoutException if self._call_timeout is over

        """
        uid = random.randint(0, 1 << 32)
        obj = {"jsonrpc": "2.0", "method": method, "params": params, "id": uid}
        self._requests.append(obj)
        start = time.time()

        while uid not in self._results:  # wait for response
            # time.sleep(1)
            time.sleep(0.01)
            if time.time() - start > self._call_timeout:
                raise ElSockTimeoutException(
                    f"Timeout in call ({self._call_timeout} seconds) waiting for {method} on {self._socket}"
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
        if hasattr(self, "_socket"):
            self._socket.close()


def create_and_start_bg_thread(func) -> FlaskThread:
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


def parse_proxy_url(proxy_url: str):
    """A proxy_url like socks5h://localhost:9050 will get parsed and returned into something like:
    [ "localhost", "9050"]
    the url HAS to start with socks5h
    """
    if not proxy_url.startswith("socks5h://"):
        raise SpectrumInternalException(f"Wrong schema for proxy_url: {proxy_url}")
    proxy_url = proxy_url.replace("socks5h://", "")
    arr = proxy_url.split(":")
    if len(arr) != 2:
        raise SpectrumInternalException(
            f"Wrong uri has more than one ':' : {proxy_url}"
        )
    return arr[0], int(arr[1])
