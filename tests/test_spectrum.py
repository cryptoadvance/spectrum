import logging
import time
from unittest.mock import MagicMock

from flask import Flask
from cryptoadvance.spectrum.db import Descriptor, Script, Wallet
from cryptoadvance.spectrum.spectrum import Spectrum
from embit.descriptor.checksum import add_checksum
from embit.bip32 import NETWORKS

logger = logging.getLogger("cryptoadvance")

def test_importdescriptor(app: Flask, rootkey_hold_accident, acc0key0addr_hold_accident):
    ''' THis does:
        * Creating a wallet
        * importing a descriptor
        * load the script with index 0 
        * compare the address with the expected one
    '''
    spectrum: Spectrum = app.spectrum
    # calculate the descriptor
    tpriv = rootkey_hold_accident.to_base58(
        version=NETWORKS["regtest"]["xprv"]
    )
    desc = add_checksum("wpkh(" + tpriv + "/84'/1'/0'/0/*)")
    desc = desc.replace("'","h")
    logger.info(f"TEST: created desc: {desc}")
    logger.info(f"TEST: expecting address: {acc0key0addr_hold_accident}")
    # Now let's derive the first address from this.


    with app.test_request_context():
        # Create a wallet
        spectrum.createwallet("bob_the_wallet", disable_private_keys=True) # not a hotwallet!
        wallet: Wallet = Wallet.query.filter_by(name="bob_the_wallet").first()
        logger.info("TEST: Import descriptor")
        spectrum.importdescriptor(wallet, desc)
        descriptor: Descriptor = Descriptor.query.filter_by(wallet=wallet).all() # could use first() but let's assert!
        assert len(descriptor) == 1
        descriptor = descriptor[0]
        logger.info(f"TEST: descriptor {descriptor}")
        assert spectrum.getbalances(wallet) == {'mine': {'immature': 0.0, 'trusted': 0.0, 'untrusted_pending': 0.0}, 'watchonly': {'immature': 0.0, 'trusted': 0.0, 'untrusted_pending': 0.0}}
        # Load the script with index 0
        script: Script = Script.query.filter_by(wallet=wallet, index=0).all() # could use first() but let's assert!
        assert len(script) == 1
        script = script[0]
        logger.info(f"TEST: scripthash {script.scripthash} ")
        logger.info(f"TEST: script address {script.address(network=NETWORKS['test'])}")
        # compare the address with the expected one
        assert acc0key0addr_hold_accident == script.address(network=NETWORKS['test'])
        # Depending on the state of electrs, it might take 5 seconds for the sync-thread to finish
        # It does not change anything on the result of the test, though
    
    spectrum.stop()
    del spectrum

