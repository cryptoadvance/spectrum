from binascii import hexlify, unhexlify
import io
import time

import mock
import pytest
from cryptoadvance.spectrum.elsock import ElectrumSocket
import hashlib
import struct

from cryptoadvance.spectrum.util import SpectrumException


def test_elsock(config):
    with mock.patch('cryptoadvance.spectrum.elsock.socket.socket'):
        print(time.time())
        es = ElectrumSocket(host=config.ELECTRUM_HOST, port=config.ELECTRUM_PORT, timeout=1)
        with pytest.raises(SpectrumException):
            res = es.ping()



