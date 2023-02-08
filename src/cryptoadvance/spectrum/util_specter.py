""" Contains stuff which is copy and pasted from specter
    in order to avoid dependency issues which are already severe enough.
"""
import logging
import os
from http.client import HTTPConnection
import requests
from urllib3.exceptions import NewConnectionError
from requests.exceptions import ConnectionError
import datetime
import urllib3
import json

logger = logging.getLogger(__name__)


def snake_case2camelcase(word):
    return "".join(x.capitalize() or "_" for x in word.split("_"))


def setup_logging(debug=False, tracerpc=False, tracerequests=False):
    """This code sets up logging for a Python application. It sets the logging level to DEBUG if the tracerpc
    or tracerequests flags are set, and INFO otherwise. It also sets up the formatter for the log messages,
    which can be customized with an environment variable. Finally, it adds a StreamHandler to the root
    logger and removes any existing handlers.
    """
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    if tracerpc or tracerequests:
        if tracerpc:
            debug = True  # otherwise this won't work
            logging.getLogger("cryptoadvance.specter.rpc").setLevel(logging.DEBUG)
        if tracerequests:
            # from here: https://stackoverflow.com/questions/16337511/log-all-requests-from-the-python-requests-module
            HTTPConnection.debuglevel = 1
            requests_log = logging.getLogger("requests.packages.urllib3")
            requests_log.setLevel(logging.DEBUG)
            requests_log.propagate = True
    else:
        logging.getLogger("cryptoadvance.specter.rpc").setLevel(logging.INFO)

    if debug:
        # No need for timestamps while developing
        formatter = logging.Formatter("[%(levelname)7s] in %(module)15s: %(message)s")
        logging.getLogger("cryptoadvance").setLevel(logging.DEBUG)
        # but not that chatty connectionpool
        logging.getLogger("urllib3.connectionpool").setLevel(logging.INFO)
    else:
        formatter = logging.Formatter(
            # Too early to format that via the flask-config, so let's copy it from there:
            os.getenv(
                "SPECTER_LOGFORMAT",
                "[%(asctime)s] %(levelname)s in %(module)s: %(message)s",
            )
        )
        logging.getLogger("cryptoadvance").setLevel(logging.INFO)
    ch.setFormatter(formatter)
    logging.getLogger().handlers = []
    logging.getLogger().addHandler(ch)


def _get_bool_env_var(varname, default=None):

    value = os.environ.get(varname, default)

    if value is None:
        return False
    elif isinstance(value, str) and value.lower() == "false":
        return False
    elif bool(value) is False:
        return False
    else:
        return bool(value)


class BitcoinRPC:
    """A slim version of the Specter BitcoinRPC"""

    counter = 0

    # These are used for tracing the calls without too many duplicates
    last_call_hash = None
    last_call_hash_counter = 0

    # https://docs.python-requests.org/en/master/user/quickstart/#timeouts
    # None means until connection closes. It's specified in seconds
    default_timeout = None  # seconds

    def __init__(
        self,
        user="bitcoin",
        password="secret",
        host="127.0.0.1",
        port=8332,
        protocol="http",
        path="",
        timeout=None,
        session=None,
        proxy_url="socks5h://localhost:9050",
        only_tor=False,
        **kwargs,
    ):
        path = path.replace("//", "/")  # just in case
        self.user = user
        self._password = password
        self.port = port
        self.protocol = protocol
        self.host = host
        self.path = path
        self.timeout = timeout or self.__class__.default_timeout
        self.proxy_url = proxy_url
        self.only_tor = only_tor
        self.r = None
        self.last_call_hash = None
        self.last_call_hash_counter = 0
        # session reuse speeds up requests
        if session is None:
            self._create_session()
        else:
            self.session = session

    def _create_session(self):
        session = requests.Session()
        session.auth = (self.user, self.password)
        self.session = session

    def wallet(self, name=""):
        """Return new instance connected to a specific wallet"""
        return type(self)(
            user=self.user,
            password=self.password,
            port=self.port,
            protocol=self.protocol,
            host=self.host,
            path="{}/wallet/{}".format(self.path, name),
            timeout=self.timeout,
            session=self.session,
            proxy_url=self.proxy_url,
            only_tor=self.only_tor,
        )

    @property
    def url(self):
        return "{s.protocol}://{s.host}:{s.port}{s.path}".format(s=self)

    @property
    def password(self):
        return self._password

    @password.setter
    def password(self, value):
        self._password = value
        self._create_session()

    def test_connection(self):
        """returns a boolean depending on whether getblockchaininfo() succeeds"""
        try:
            self.getblockchaininfo()
            return True
        except:
            return False

    def clone(self):
        """
        Returns a clone of self.
        Useful if you want to mess with the properties
        """
        return BitcoinRPC(
            self.user,
            self.password,
            self.host,
            self.port,
            self.protocol,
            self.path,
            self.timeout,
            self.session,
            self.proxy_url,
            self.only_tor,
        )

    def multi(self, calls: list, **kwargs):
        """Makes batch request to Core"""
        type(self).counter += len(calls)
        # some debug info for optimizations
        # methods = " ".join(list(dict.fromkeys([call[0] for call in calls])))
        # wallet = self.path.split("/")[-1]
        # print(f"{self.counter}: +{len(calls)} {wallet} {methods}")
        headers = {"content-type": "application/json"}
        payload = [
            {
                "method": method,
                "params": args if args != [None] else [],
                "jsonrpc": "2.0",
                "id": i,
            }
            for i, (method, *args) in enumerate(calls)
        ]
        timeout = self.timeout
        if "timeout" in kwargs:
            timeout = kwargs["timeout"]

        if kwargs.get("no_wait"):
            # Zero is treated like None, i.e. infinite wait
            timeout = 0.001

        url = self.url
        if "wallet" in kwargs:
            url = url + "/wallet/{}".format(kwargs["wallet"])
        ts = self.trace_call_before(url, payload)
        try:
            r = self.session.post(
                url, data=json.dumps(payload), headers=headers, timeout=timeout
            )
        except (ConnectionError, NewConnectionError, ConnectionRefusedError) as ce:
            raise Exception(ce)

        except (requests.exceptions.Timeout, urllib3.exceptions.ReadTimeoutError) as to:
            # Timeout is effectively one of the two:
            # ConnectTimeout: The request timed out while trying to connect to the remote server
            # ReadTimeout: The server did not send any data in the allotted amount of time.
            # ReadTimeoutError: Raised when a socket timeout occurs while receiving data from a server
            if kwargs.get("no_wait"):
                # Used for rpc calls that don't immediately return (e.g. rescanblockchain) so we don't
                # expect any data back anyway. __getattr__ expects a list of formatted json.
                self.trace_call_after(url, payload, timeout)
                return [{"error": None, "result": None}]

            logger.error(
                "Timeout after {} secs while {} call({: <28}) payload:{} Exception: {}".format(
                    timeout,
                    self.__class__.__name__,
                    "/".join(url.split("/")[3:]),
                    payload,
                    to,
                )
            )
            logger.exception(to)
            raise Exception(
                "Timeout after {} secs while {} call({: <28}). Check the logs for more details.".format(
                    timeout,
                    self.__class__.__name__,
                    "/".join(url.split("/")[3:]),
                    payload,
                )
            )
        self.trace_call_after(url, payload, ts)
        self.r = r
        if r.status_code != 200:
            logger.debug(f"last call FAILED: {r.text}")
            if r.text.startswith("Work queue depth exceeded"):
                raise Exception(
                    "Your Bitcoind is running hot (Work queue depth exceeded)! Bitcoind gets more requests than it can process. Please refrain from doing anything for some minutes."
                )
            raise Exception(
                "Server responded with error code %d: %s" % (r.status_code, r.text), r
            )
        r = r.json()
        return r

    @classmethod
    def trace_call_before(cls, url, payload):
        """get a timestamp if needed in order to measure how long the call takes"""
        if logger.level == logging.DEBUG:
            return datetime.datetime.now()

    @classmethod
    def trace_call_after(cls, url, payload, timestamp):
        """logs out the call and its payload (if necessary), reduces noise by suppressing repeated calls"""
        if logger.level == logging.DEBUG:
            timediff_ms = int(
                (datetime.datetime.now() - timestamp).total_seconds() * 1000
            )
            current_hash = hash(
                json.dumps({"url": url, "payload": payload}, sort_keys=True)
            )
            if cls.last_call_hash == None:
                cls.last_call_hash = current_hash
                cls.last_call_hash_counter = 0
            elif cls.last_call_hash == current_hash:
                cls.last_call_hash_counter = cls.last_call_hash_counter + 1
                return
            else:
                if cls.last_call_hash_counter > 0:
                    logger.debug(f"call repeated {cls.last_call_hash_counter} times")
                    cls.last_call_hash_counter = 0
                    cls.last_call_hash = current_hash
                else:
                    cls.last_call_hash = current_hash
            logger.debug(
                "call({: <28})({: >5}ms)  payload:{}".format(
                    "/".join(url.split("/")[3:]), timediff_ms, payload
                )
            )

    def __getattr__(self, method):
        def fn(*args, **kwargs):
            r = self.multi([(method, *args)], **kwargs)[0]
            if r["error"] is not None:
                raise Exception(
                    f"Request error for method {method}{args}: {r['error']['message']}",
                    r,
                )
            return r["result"]

        return fn

    def __repr__(self) -> str:
        return f"<BitcoinRpc {self.url}>"
