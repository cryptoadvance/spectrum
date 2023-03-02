from binascii import hexlify, unhexlify
import hashlib
import io
import logging
from threading import Thread
from decimal import Decimal

from embit import hashes
from flask import current_app as app

logger = logging.getLogger(__name__)


def get_blockhash(hex_header):
    return hashes.double_sha256(bytes.fromhex(hex_header))[::-1].hex()


def scripthash(script):
    """Calculates a scripthash for Electrum from address"""
    return hashes.sha256(script.data)[::-1].hex()


def sat_to_btc(sat):
    """Core is returning floats which is not good. We need to switch over to decimal at some point
    but this is not yet used yet.
    If we do it, also have a look at:
    https://github.com/relativisticelectron/specter-desktop/pull/3
    """
    sat = sat or 0  # if None is passed
    return round(sat * 1e-8, 8)


def btc_to_sat(btc):
    btc = btc or 0  # if None is passed
    return round(btc * 1e8)


class SpectrumException(Exception):
    pass


class SpectrumInternalException(Exception):
    pass


def handle_exception(exception):
    """prints the exception and most important the stacktrace"""
    logger.error(
        "----START-TRACEBACK-----------------------------------------------------------------"
    )
    logger.exception(exception)  # the exception instance
    logger.error(
        "----END---TRACEBACK-----------------------------------------------------------------"
    )


class FlaskThread(Thread):
    """A FlaskThread passes the applicationcontext to the new thread in order to make stuff working seamlessly in new threadsS
    copied from https://stackoverflow.com/questions/39476889/use-flask-current-app-logger-inside-threading"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.daemon = True
        try:
            self.app = app._get_current_object()
            self.flask_mode = True
        except RuntimeError as e:
            if str(e).startswith("Working outside of application context."):
                self.flask_mode = False

    def run(self):
        if self.flask_mode:
            with self.app.app_context():
                logger.debug(f"starting new FlaskThread: {self._target.__name__}")
                super().run()
        else:
            logger.debug(f"starting new Thread: {self._target.__name__}")
            super().run()


# inspired by Jimmy:
# https://github.com/jimmysong/programmingbitcoin/blob/3fba6b992ece443e4256df057595cfbe91edda75/code-ch09/answers.py#L109-L123


def _little_endian_to_int(b):
    """little_endian_to_int takes byte sequence as a little-endian number.
    Returns an integer"""
    return int.from_bytes(b, "little")


def parse_blockheader(s):
    """pass in a string, 80 bytes or"""
    if isinstance(s, str):
        s = unhexlify(s)
    if isinstance(s, bytes):
        assert len(s) == 80, f"a Blockheader is exactly 80 bytes but this has {len(s)}"
        mybytes = s
        blockhash_bytes = hashlib.sha256(hashlib.sha256(mybytes).digest()).digest()[
            ::-1
        ]
        blockhash_str = hexlify(blockhash_bytes).decode()
        s = io.BytesIO(s)
    version = _little_endian_to_int(s.read(4))
    prev_block = s.read(32)[::-1]
    merkle_root = s.read(32)[::-1]
    timestamp = _little_endian_to_int(s.read(4))
    bits = s.read(4)
    nonce = s.read(4)
    return {
        "version": version,
        "prev_block": prev_block,
        "merkle_root": merkle_root,
        "blocktime": timestamp,
        "bits": bits,
        "nonce": nonce,
        "blockhash": blockhash_str,
    }
