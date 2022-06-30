#!/usr/bin/env python3
""" Tests an import of a wallet with lots of TXs

This sets up a node and funds a default-wallet w0
This wallet will then create lots of TXs to a wallet w1 which got created
and imported a descriptor.

After that, a SpecterWallet with the same descriptor get created + rescan.
At the end the txlist should be very similiar with the TXs of w1.


"""

import logging
import shutil
import sys
from decimal import Decimal, getcontext
from random import random
import time
from unittest.mock import MagicMock
from cryptoadvance.specter.managers.wallet_manager import WalletManager
from cryptoadvance.specter.persistence import delete_file
from cryptoadvance.specter.rpc import BitcoinRPC, autodetect_rpc_confs
from cryptoadvance.specter.wallet import Wallet
from embit.bip32 import NETWORKS, HDKey
from mock import patch
from cryptoadvance.specter.key import Key
from embit.descriptor.checksum import add_checksum


logger = logging.getLogger(__name__)

def test_TrafficGen(
    caplog,
    empty_data_folder,
    acc0xprv_hold_accident,
    acc0key_hold_accident,
    rootkey_hold_accident,
):
    caplog.set_level(logging.INFO)
    number_of_txs = 10
    keypoolrefill = number_of_txs
    # caplog.set_level(logging.DEBUG)
    # durations = {}
    # for i in range(1,2,1):
    # for i in range(7000, 8000, 1000):
    #     shutil.rmtree(empty_data_folder)
    #     tg = TrafficGen()
    #     tg.number_of_txs = i
    #     tg.keypoolrefill = i
    #     tg.rootkey_hold_accident = rootkey_hold_accident
    #     tg.acc0key_hold_accident = acc0key_hold_accident

    #     tg.empty_data_folder = empty_data_folder
    #     durations[i] = tg.main()

    logger.info(f"Setup wallets, planning for {number_of_txs} TXs")
    # w0 is a wallet with coinbase rewards
    rpc: BitcoinRPC = BitcoinRPC(user="admin1", password="123", host="localhost", port="18443")
    if "" not in rpc.listwallets():
        rpc.createwallet("")
    w0 = rpc.wallet("")
    rpc.generatetoaddress(110, w0.getnewaddress())

    # w1 contains the private keys acc0xprv_hold_accident
    if "w1" not in rpc.listwallets():
        rpc.createwallet("w1", blank=True, descriptors=True)
    w1 = rpc.wallet("w1")
    tpriv = rootkey_hold_accident.to_base58(
        version=NETWORKS["regtest"]["xprv"]
    )

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
    zero_address = rpc.deriveaddresses(add_checksum("wpkh(" + tpriv + "/84'/1'/0'/0/*)"),[0,0])[0]
    #zero_address = w1.getnewaddress()
    print(f"muh: {zero_address}")
    logger.info(f"result of addressinfo(w1)) {w1.getaddressinfo(zero_address)}")
    w1.keypoolrefill(199)

    # Create some TXs towards w1
    logger.info(f"blockheight: {rpc.getblockchaininfo()['blocks']} ")
    logger.info(f"result of getbalances (before): {w1.getbalances()}")
    for i in range(0, number_of_txs):
        w0.sendtoaddress(w1.getnewaddress(), 0.1)
        if i % 10 and random() > 0.8:
            rpc.generatetoaddress(1, w0.getnewaddress())

    # be sure that all the TXs are in the chain
    rpc.generatetoaddress(1, w0.getnewaddress())
    logger.info(f"blockheight: {rpc.getblockchaininfo()['blocks']} ")
    logger.info(f"result of getbalances (after): {w1.getbalances()}")

    # Create the specter-wallet
    wm = WalletManager(
        None,
        empty_data_folder,
        rpc,
        "regtest",
        None,
        allow_threading=False,
    )
    wallet: Wallet = wm.create_wallet(
        "hold_accident", 1, "wpkh", [acc0key_hold_accident], MagicMock()
    )
    hold_accident = rpc.wallet("specter/hold_accident")
    ha_zero_address = wallet.get_address(0) # the defaultwallet is already used
    logger.info(f"result of addressinfo(hold_accident)) {hold_accident.getaddressinfo(ha_zero_address)}")

    # Be sure that the addresses of w1 and the specter-wallet matches
    assert ha_zero_address == zero_address

    hold_accident.keypoolrefill(number_of_txs + 10)
    wallet.update()

    # Do a rescan
    delete_file(wallet._transactions.path)
    # wallet.fetch_transactions()
    # This rpc call does not seem to return a result; use no_wait to ignore timeout errors
    result = wallet.rpc.rescanblockchain(0)
    print(wallet.rpc.getwalletinfo())
    logger.info(f"Result of rescanblockchain: {result}")

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
















