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
from cryptoadvance.spectrum.spectrum import Spectrum
from cryptoadvance.spectrum.elsock import ElectrumSocket
from datetime import datetime
from cryptoadvance.spectrum.db import Descriptor, Script, Wallet
from conftest import spectrum_app_with_config

logger = logging.getLogger("cryptoadvance")

number_of_txs = 10
keypoolrefill = number_of_txs


def fill_spectrum(
    spectrum,
    rootkey_hold_accident,
):
    spectrum = spectrum.spectrum
    # calculate the descriptor
    tpriv = rootkey_hold_accident.to_base58(version=NETWORKS["regtest"]["xprv"])
    desc = add_checksum("wpkh(" + tpriv + "/84'/1'/0'/0/*)")
    desc = desc.replace("'", "h")
    spectrum.createwallet(
        "bob_the_wallet", disable_private_keys=True
    )  # not a hotwallet!
    wallet: Wallet = Wallet.query.filter_by(name="bob_the_wallet").first()
    logger.info("TEST: Import descriptor")
    spectrum.importdescriptor(wallet, desc)
    descriptor: Descriptor = Descriptor.query.filter_by(
        wallet=wallet
    ).all()  # could use first() but let's assert!
    assert len(descriptor) == 1
    descriptor = descriptor[0]


def test_spectrum_resilience(caplog, empty_data_folder, rootkey_hold_accident):
    """
            Should test the behaviour of the system if the socket gets broken.
            We're doing it intentionally here by spectrum_app.spectrum.sock._socket.close()

            In that case the monitor-thread of ElectrumSocket should detect that, recreate
            the socket and the threads and call the callback which will cause a new sync on the spectrum side

            Here is how the successfull Logging of that would look like:

            [   INFO] in        conftest: Deleting ./data
    [   INFO] in          server: config: <class 'conftest.tempClass'>
    [   INFO] in          server: -------------------------CONFIGURATION-OVERVIEW------------
    [   INFO] in          server: Config from empty
    [   INFO] in          server: APPLICATION_ROOT = /
    [   INFO] in          server: DATABASE = /home/kim/src/spectrum/data/wallets.sqlite
    [   INFO] in          server: DEBUG = False
    [   INFO] in          server: ELECTRUM_HOST = electrum.emzy.de
    [   INFO] in          server: ELECTRUM_PORT = 50002
    [   INFO] in          server: ELECTRUM_USES_SSL = True
    [...]
    [   INFO] in          server: USERNAME = admin
    [   INFO] in          server: USE_X_SENDFILE = False
    [   INFO] in          server: -----------------------------------------------------------
    [   INFO] in          server: Creating Spectrum Object ...
    [   INFO] in        spectrum: Creating txdir data/txs
    [   INFO] in        spectrum: Creating ElectrumSocket electrum.emzy.de:50002 (ssl=True)
    [   INFO] in          elsock: Initializing ElectrumSocket with electrum.emzy.de:50002 (ssl: <module 'ssl' from '/home/kim/.pyenv/versions/3.10.4/lib/python3.10/ssl.py'>)
    [  DEBUG] in          elsock: socket created  : <socket.socket fd=11, family=AddressFamily.AF_INET, type=SocketKind.SOCK_STREAM, proto=0, laddr=('0.0.0.0', 0)>
    [  DEBUG] in          elsock: socket wrapped  : <ssl.SSLSocket fd=11, family=AddressFamily.AF_INET, type=SocketKind.SOCK_STREAM, proto=0, laddr=('0.0.0.0', 0)>
    [  DEBUG] in          elsock: socket connected: <ssl.SSLSocket fd=11, family=AddressFamily.AF_INET, type=SocketKind.SOCK_STREAM, proto=0, laddr=('192.168.178.104', 34934), raddr=('135.181.215.237', 50002)>
    [  DEBUG] in            util: starting new FlaskThread: recv_loop
    [   INFO] in          elsock: Started bg thread for recv_loop
    [  DEBUG] in            util: starting new FlaskThread: _write_loop
    [   INFO] in          elsock: Started bg thread for _write_loop
    [  DEBUG] in            util: starting new FlaskThread: _ping_loop
    [   INFO] in          elsock: Started bg thread for _ping_loop
    [  DEBUG] in            util: starting new FlaskThread: _notify_loop
    [   INFO] in          elsock: Started bg thread for _notify_loop
    [  DEBUG] in            util: starting new FlaskThread: _monitor_loop
    [   INFO] in          elsock: Started bg thread for _monitor_loop
    [   INFO] in        spectrum: Pinged electrum in 0.050364017486572266
    [   INFO] in        spectrum: subscribe to block headers
    [   INFO] in        spectrum: detect chain from header
    [   INFO] in        spectrum: Set roothash
    [  DEBUG] in            util: starting new FlaskThread: _sync
    [   INFO] in        spectrum: Syncing ... <cryptoadvance.spectrum.elsock.ElectrumSocket object at 0x7ff786dc4850>
    [   INFO] in   spectrum_test: TEST: Import descriptor
    [   INFO] in        spectrum: Importing descriptor wpkh(tprv8ZgxMBicQKsPeu959EyVrwNtMj8xK64oGgSjTCxexEnFu1y6B56bannxXuL4Vcbn9JRzcjyyKdBQaq6cgQcsTNcpP34Jo45vGifxtuf9VGZ/84h/1h/0h/0/*)#d9a3mju9
    [   INFO] in        spectrum: Creating 300 scriptpubkeys for wallet <Wallet 1>
    [  DEBUG] in            util: starting new FlaskThread: _subcribe_scripts
    [   INFO] in   spectrum_test: 2023-02-22 15:52:23.974127 Let's sleep for 20 seconds (that's what it takes to completely sync)
    [   INFO] in        spectrum: subscribed to 300 scripts for descriptor wpkh(tprv8ZgxMBicQKsPeu959EyVr... where 0 got synced
    [   INFO] in   spectrum_test: 2023-02-22 15:52:43.993239 --------------------------closed-----------------------------------------------------------
    [   INFO] in   spectrum_test: 2023-02-22 15:52:43.993468 Let's sleep for 5 seconds
    [  ERROR] in          elsock: Error in write: <class 'OSError'>
    [  ERROR] in          elsock: Error in ping-loop (1th time, next try in 1 seconds if threshold not met
    [  ERROR] in          elsock: Error in ping-loop (2th time, next try in 1 seconds if threshold not met
    [  ERROR] in          elsock: More than {self.tries_threshold} Ping failures for 60 seconds, Giving up!
    [  ERROR] in          elsock: Error in write: <class 'OSError'>
    [   INFO] in          elsock: recreating socket and threads
    [  DEBUG] in          elsock: socket created  : <socket.socket fd=11, family=AddressFamily.AF_INET, type=SocketKind.SOCK_STREAM, proto=0, laddr=('0.0.0.0', 0)>
    [  DEBUG] in          elsock: socket wrapped  : <ssl.SSLSocket fd=11, family=AddressFamily.AF_INET, type=SocketKind.SOCK_STREAM, proto=0, laddr=('0.0.0.0', 0)>
    [  DEBUG] in          elsock: socket connected: <ssl.SSLSocket fd=11, family=AddressFamily.AF_INET, type=SocketKind.SOCK_STREAM, proto=0, laddr=('192.168.178.104', 43436), raddr=('135.181.215.237', 50002)>
    [  DEBUG] in            util: starting new FlaskThread: recv_loop
    [   INFO] in          elsock: Started bg thread for recv_loop
    [  DEBUG] in            util: starting new FlaskThread: _write_loop
    [   INFO] in          elsock: Started bg thread for _write_loop
    [  DEBUG] in            util: starting new FlaskThread: _ping_loop
    [   INFO] in          elsock: Started bg thread for _ping_loop
    [  DEBUG] in            util: starting new FlaskThread: _notify_loop
    [   INFO] in          elsock: Started bg thread for _notify_loop
    [  DEBUG] in          elsock: calling self._on_recreation_callback _sync
    [   INFO] in        spectrum: Syncing ... <cryptoadvance.spectrum.elsock.ElectrumSocket object at 0x7ff786dc4850>
    [   INFO] in   spectrum_test: 2023-02-22 15:52:48.997232 Let's sleep for 5 seconds
    [   INFO] in        spectrum: Now subscribed to 100 scripthashes (33%)


    """
    caplog.set_level(logging.DEBUG)

    # Speed up the test ...
    ElectrumSocket.tries_threshold = 1
    ElectrumSocket.sleep_ping_loop = 1
    ElectrumSocket.timeout = 1
    spectrum_app = spectrum_app_with_config(
        config={
            "ELECTRUM_HOST": "electrum.emzy.de",
            "ELECTRUM_PORT": 50002,
            "ELECTRUM_USES_SSL": True,
        }
    )
    with spectrum_app.app_context():

        fill_spectrum(spectrum_app, rootkey_hold_accident)

        logger.info(
            f"{datetime.now()} Let's sleep for 20 seconds (that's what it takes to completely sync)"
        )
        time.sleep(20)
        # How mean we are ...
        spectrum_app.spectrum.sock._socket.close()
        logger.info(
            f"{datetime.now()} --------------------------closed-----------------------------------------------------------"
        )

        logger.info(f"{datetime.now()} Let's sleep for 5 seconds")
        time.sleep(5)
        logger.info(f"{datetime.now()} Let's sleep for 5 seconds")
        time.sleep(5)
        assert not spectrum_app.spectrum.sock.is_socket_closed()
