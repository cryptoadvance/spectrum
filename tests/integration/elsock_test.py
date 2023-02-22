from distutils import core
import logging
import shutil
import sys
import pytest
from decimal import Decimal, getcontext
from random import random
import time
from unittest.mock import MagicMock
from embit.bip32 import NETWORKS, HDKey
from mock import patch
from embit.descriptor.checksum import add_checksum
from cryptoadvance.spectrum.elsock import ElectrumSocket
from datetime import datetime

logger = logging.getLogger("cryptoadvance")

number_of_txs = 10
keypoolrefill = number_of_txs


def test_elsock(caplog):

    caplog.set_level(logging.DEBUG)

    def callback(something):
        print(something)

    # Speed up the test ...
    ElectrumSocket.tries_threshold = 1
    ElectrumSocket.sleep_ping_loop = 1
    logger.info(f"{datetime.now()} Testing ElectrumSocket")
    elsock = ElectrumSocket(
        host="electrum.emzy.de", port=50002, callback=callback, use_ssl=True, timeout=1
    )
    ts = elsock.ping()
    logger.info(f"First working ping in {ts} ms")
    logger.info(elsock._socket)
    elsock._socket.close()
    logger.info(
        f"{datetime.now()} ----------------NOW the socket was intentionally closed-----------------------------------------------------------"
    )
    logger.info(f"{datetime.now()} Let's sleep for 5 seconds")
    time.sleep(5)
    logger.info(f"{datetime.now()} Let's sleep for 5 seconds")
    time.sleep(5)
    logger.info(
        f"{datetime.now()}--------------The socket connection should now work properly again-------------------------------------------------"
    )
    logger.info(elsock._socket)
    ts = elsock.ping()
    logger.info(f"second working ping in {ts} ms")
    assert ts < 1
