from binascii import hexlify, unhexlify
import io
import time

import mock
import pytest
from cryptoadvance.spectrum.elsock import ElectrumSocket, ElSockTimeoutException
import hashlib
import struct

from cryptoadvance.spectrum.util import SpectrumException


def test_elsock(config):
    with mock.patch("cryptoadvance.spectrum.elsock.socket.socket"):
        print(time.time())
        es = ElectrumSocket(
            host=config.ELECTRUM_HOST,
            port=config.ELECTRUM_PORT,
            socket_timeout=1,
            call_timeout=1,
        )
        with pytest.raises(ElSockTimeoutException):
            res = es.ping()


def test_elsock_thread_status():
    es = ElectrumSocket(host="notExisting", port=123)
    es.running = False
    write_mock = mock.MagicMock()
    write_mock.is_alive.return_value = False
    recv_mock = mock.MagicMock()
    recv_mock.is_alive.return_value = False
    ping_mock = mock.MagicMock()
    ping_mock.is_alive.return_value = False
    notify_mock = mock.MagicMock()
    notify_mock.is_alive.return_value = False
    es._write_thread = write_mock
    es._recv_thread = recv_mock
    es._ping_thread = ping_mock
    es._notify_thread = notify_mock
    es.thread_status
    assert es.thread_status["write"] == False
    assert es.thread_status["recv"] == False
    assert es.thread_status["ping"] == False
    assert es.thread_status["notify"] == False
    assert es.thread_status["any_alive"] == False
    assert es.thread_status["not_any_alive"] == True
    assert es.thread_status["all_alive"] == False
    assert es.thread_status["not_all_alive"] == True
    assert es.thread_status["alive"] == []
    assert es.thread_status["not_alive"] == ["recv", "write", "ping", "notify"]
    ping_mock.reset_mock()
    ping_mock.is_alive.return_value = True
    assert es.thread_status["recv"] == False
    assert es.thread_status["ping"] == True
    assert es.thread_status["any_alive"] == True
    assert es.thread_status["not_any_alive"] == False
    assert es.thread_status["all_alive"] == False
    assert es.thread_status["not_all_alive"] == True
    assert es.thread_status["alive"] == ["ping"]
    assert es.thread_status["not_alive"] == ["recv", "write", "notify"]
    write_mock.reset_mock()
    write_mock.is_alive.return_value = True
    recv_mock.reset_mock()
    recv_mock.is_alive.return_value = True
    notify_mock.reset_mock()
    notify_mock.is_alive.return_value = True
    assert es.thread_status["any_alive"] == True
    assert es.thread_status["not_any_alive"] == False
    assert es.thread_status["all_alive"] == True
    assert es.thread_status["not_all_alive"] == False
    assert es.thread_status["alive"] == ["recv", "write", "ping", "notify"]
    assert es.thread_status["not_alive"] == []
