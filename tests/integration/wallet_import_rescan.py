#!/usr/bin/env python3
""" Tests an import of a wallet with lots of TXs

This sets up a node and funds a default-wallet w0
This wallet will then create lots of TXs to a wallet w1 which got created
and imported a descriptor.

After that, a SpecterWallet with the same descriptor get created + rescan.
At the end the txlist should be very similiar with the TXs of w1.


"""

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

# Test is green in local dev
def test_import_nigiri_core(
    caplog,
    empty_data_folder,
    # acc0xprv_hold_accident,
    # acc0key_hold_accident,
    rootkey_hold_accident,
):
    """Test is using a rpc connecting to nigiri's core"""
    caplog.set_level(logging.INFO)
    rpc: BitcoinRPC = BitcoinRPC(
        user="admin1", password="123", host="localhost", port="18443"
    )
    # runtest_import_via(
    #     rpc,
    #     rpc,
    #     number_of_txs,
    #     keypoolrefill,
    #     caplog,
    #     empty_data_folder,
    #     #acc0key_hold_accident,
    #     rootkey_hold_accident,
    # )


# Skipping for now
# It would make more sense to setup a Spectrum and a Spectrum node here and check whether an import of wallet "w1" results in the same balace
# Definitely makes no sense to do to the sending from w0 to w1 twice.
@pytest.mark.skip
def test_import_spectrum_nigiri_electrs_core(
    caplog,
    app_nigiri,
    empty_data_folder,
    acc0xprv_keen_join,
    # acc0key_keen_join,
    # rootkey_keen_join,
):
    """Test is using a rpc connecting to spectrum which is connected via nigiri's electrs to nigiri's core"""
    caplog.set_level(logging.INFO)
    # Can't be right here!
    spectrum_rpc: BitcoinRPC = BitcoinRPC(
        user="", password="", host="localhost", port="8081"
    )

    btc_rpc: BitcoinRPC = BitcoinRPC(
        user="admin1", password="123", host="localhost", port="18443"
    )
    runtest_import_via(
        spectrum_rpc,
        btc_rpc,
        number_of_txs,
        keypoolrefill,
        caplog,
        empty_data_folder,
        acc0key_keen_join,
        rootkey_keen_join,
    )


def runtest_import_via(
    spectrum_rpc,
    btc_rpc,
    number_of_txs,
    keypoolrefill,
    caplog,
    empty_data_folder,
    acc0key,
    rootkey,
):

    # caplog.set_level(logging.DEBUG)
    # durations = {}
    # for i in range(1,2,1):
    # for i in range(7000, 8000, 1000):
    #     shutil.rmtree(empty_data_folder)
    #     tg = TrafficGen()
    #     tg.number_of_txs = i
    #     tg.keypoolrefill = i
    #     tg.rootkey = rootkey
    #     tg.acc0key = acc0key

    #     tg.empty_data_folder = empty_data_folder
    #     durations[i] = tg.main()

    logger.info(f"Setup wallets, planning for {number_of_txs}")
    logger.info(f"btc_rpc = {btc_rpc}")
    logger.info(f"spectrum_rpc = {spectrum_rpc}")
    # w0 is a wallet with coinbase rewards

    w0_walletname = "w0" + str(int(time.time()))
    w1_walletname = "w1" + str(int(time.time()))
    if w0_walletname not in btc_rpc.listwallets():
        btc_rpc.createwallet(w0_walletname)
    w0 = btc_rpc.wallet(w0_walletname)
    logger.info(
        f"result of getbalances (w0 / mine / trusted ): {w0.getbalances()['mine']['trusted']}"
    )
    btc_rpc.generatetoaddress(110, w0.getnewaddress())
    logger.info(
        f"result of getbalances (w0 / mine / trusted ): {w0.getbalances()['mine']['trusted']}"
    )

    # w1 contains the private keys acc0xprv
    if w1_walletname not in btc_rpc.listwallets():
        btc_rpc.createwallet(w1_walletname, blank=True, descriptors=True)
    w1 = btc_rpc.wallet(w1_walletname)
    tpriv = rootkey.to_base58(version=NETWORKS["regtest"]["xprv"])

    result = w1.importdescriptors(
        [
            {
                "desc": add_checksum("wpkh(" + tpriv + "/84'/1'/0'/0/*)"),
                "timestamp": "now",
                "range": [0, 100],
                "active": True,
            },
            {
                "desc": add_checksum("wpkh(" + tpriv + "/84'/1'/1'/1/*)"),
                "timestamp": "now",
                "range": [0, 100],
                "active": True,
                "internal": True,
            },
        ]
    )

    logger.info(f"result of importdescriptors: {result}")
    zero_address = btc_rpc.deriveaddresses(
        add_checksum("wpkh(" + tpriv + "/84'/1'/0'/0/*)"), [0, 0]
    )[0]
    # zero_address = w1.getnewaddress()
    print(f"muh: {zero_address}")
    logger.info(f"result of addressinfo(w1)) {w1.getaddressinfo(zero_address)}")
    w1.keypoolrefill(199)

    # Create some TXs towards w1
    logger.info(f"blockheight: {btc_rpc.getblockchaininfo()['blocks']} ")
    logger.info(f"result of getbalances (before): {w1.getbalances()}")
    for i in range(0, number_of_txs):
        w0.sendtoaddress(w1.getnewaddress(), round(0.001 + random() / 100, 8))
        if i % 10 and random() > 0.8:
            btc_rpc.generatetoaddress(1, w0.getnewaddress())

    # be sure that all the TXs are in the chain
    btc_rpc.generatetoaddress(1, w0.getnewaddress())
    logger.info(f"blockheight: {btc_rpc.getblockchaininfo()['blocks']} ")
    logger.info(f"result of getbalances (after): {w1.getbalances()}")

    # Create the specter-wallet
    wm = WalletManager(
        empty_data_folder,
        spectrum_rpc,
        "regtest",
        None,
        allow_threading_for_testing=False,
    )
    wallet: Wallet = wm.create_wallet(
        "hold_accident", 1, "wpkh", [acc0key], MagicMock()
    )
    hold_accident = spectrum_rpc.wallet("specter/hold_accident")
    ha_zero_address = wallet.get_address(0)  # the defaultwallet is already used
    # logger.info(f"result of addressinfo(hold_accident)) {hold_accident.getaddressinfo(ha_zero_address)}")

    # Be sure that the addresses of w1 and the specter-wallet matches
    assert ha_zero_address == zero_address

    if spectrum_rpc == btc_rpc:
        # There is no keypoolrefill in spectrum
        hold_accident.keypoolrefill(number_of_txs + 10)
    wallet.update()

    # Do a rescan
    delete_file(wallet._transactions.path)
    # wallet.fetch_transactions()
    # This rpc call does not seem to return a result; use no_wait to ignore timeout errors
    result = wallet.rpc.rescanblockchain(0)
    print(wallet.rpc.getwalletinfo())
    logger.info(f"Result of rescanblockchain: {result}")
    time.sleep(15)
    # both balances are the same
    assert (
        wallet.rpc.getbalances()["mine"]["trusted"]
        == w1.getbalances()["mine"]["trusted"]
    )

    # Check the number of TXs
    txlist = wallet.txlist(validate_merkle_proofs=False)
    print(f"result of hold_accident.getbalances: {hold_accident.getbalances()}")
    if keypoolrefill < number_of_txs:
        assert len(txlist) == keypoolrefill
    else:
        assert len(txlist) == number_of_txs
