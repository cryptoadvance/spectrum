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


logger = logging.getLogger("cryptoadvance")

number_of_txs = 10
keypoolrefill = number_of_txs


def test_elsock(caplog):

    caplog.set_level(logging.DEBUG)

    def callback(something):
        print(something)

    elsock = ElectrumSocket(
        host="electrum.emzy.de", port=50002, callback=callback, use_ssl=True
    )
    ts = elsock.ping()
    logger.info(f"First working ping in {ts} ms")
    print(elsock._socket)
    elsock._socket.close()
    logger.info(
        "--------------------------closed-----------------------------------------------------------"
    )

    time.sleep(120)
    print(elsock._socket)
    logger.info(
        "--------------------------ping-----------------------------------------------------------"
    )
    ts = elsock.ping()
    assert False
