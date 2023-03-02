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
        host="electrum.emzy.de",
        port=50002,
        callback=callback,
        use_ssl=True,
        call_timeout=1,
    )
    ts = elsock.ping()
    logger.info(f"First working ping in {ts} ms")
    logger.info(elsock._socket)
    assert (
        caplog.text.count(
            "ElectrumSocket Status changed from unknown to creating_socket"
        )
        == 1
    )
    assert (
        caplog.text.count(
            "ElectrumSocket Status changed from creating_socket to creating_threads"
        )
        == 1
    )
    assert (
        caplog.text.count(
            "ElectrumSocket Status changed from creating_threads to execute_recreation_callback"
        )
        == 1
    )
    assert (
        caplog.text.count(
            "ElectrumSocket Status changed from execute_recreation_callback to ok"
        )
        == 1
    )
    elsock._socket.close()
    logger.info(
        f"{datetime.now()} =======================NOW the socket was intentionally closed==============================================="
    )
    # Should recover within 8 seconds ( 2 seconds buffer)
    for i in range(0, 10):
        logger.info(
            f"...................................... timer: {i} seconds passed (elsock.is_socket_closed() returns {elsock.is_socket_closed()})"
        )
        time.sleep(1)
    logger.info(
        f"{datetime.now()}========================The socket connection should now work properly again================================"
    )
    logger.info(elsock._socket)
    ts = elsock.ping()
    logger.info(f"second working ping in {ts} ms")
    assert ts < 1
    assert caplog.text.count("ElectrumSocket Status changed") == 9

    assert (
        caplog.text.count(
            "ElectrumSocket Status changed from ok to broken_killing_threads"
        )
        == 1
    )
    assert (
        caplog.text.count(
            "ElectrumSocket Status changed from broken_killing_threads to creating_socket"
        )
        == 1
    )
    assert (
        caplog.text.count(
            "ElectrumSocket Status changed from creating_socket to creating_threads"
        )
        == 2
    )
    assert (
        caplog.text.count(
            "ElectrumSocket Status changed from creating_threads to execute_recreation_callback"
        )
        == 2
    )
    assert (
        caplog.text.count(
            "ElectrumSocket Status changed from execute_recreation_callback to ok"
        )
        == 2
    )
