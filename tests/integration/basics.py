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
from cryptoadvance.spectrum.util_specter import BitcoinRPC


logger = logging.getLogger("cryptoadvance")

number_of_txs = 10
keypoolrefill = number_of_txs


def test_getblockchaininfo(caplog):
    """Test is using a rpc connecting to nigiri's core"""
    caplog.set_level(logging.INFO)
    rpc: BitcoinRPC = BitcoinRPC(
        user="admin1", password="123", host="localhost", port="18443"
    )
    result = rpc.getblockchaininfo()
    assert result["blocks"] == 101
    assert result["chain"] == "regtest"
    assert result["chainwork"].startswith("000000000")
