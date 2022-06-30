import json
import sys
from binascii import hexlify
import tempfile

import pytest
from cryptoadvance.spectrum.config import TestConfig
from cryptoadvance.spectrum.server import create_app
from cryptoadvance.specter.key import Key
from embit import script
from embit.bip32 import NETWORKS, HDKey
from embit.bip39 import mnemonic_to_seed
from flask import Flask


def spectrum_app_with_config(config={}, specter=None):
    """helper-function to create SpectrumFlasks"""
    if isinstance(config, dict):
        tempClass = type("tempClass", (TestConfig,), {})
        for key, value in config.items():
            setattr(tempClass, key, value)
        # service_manager will expect the class to be defined as a direct property of the module:
        if hasattr(sys.modules[__name__], "tempClass"):
            delattr(sys.modules[__name__], "tempClass")
        assert not hasattr(sys.modules[__name__], "tempClass")
        setattr(sys.modules[__name__], "tempClass", tempClass)
        assert hasattr(sys.modules[__name__], "tempClass")
        assert getattr(sys.modules[__name__], "tempClass") == tempClass
        config = tempClass
    app = create_app(config=config)
    with app.app_context():
        app.config["TESTING"] = True
        app.testing = True
        #init_app(app, specter=specter)
        return app

@pytest.fixture
def app() -> Flask:
    """the Flask-App, but uninitialized"""
    return spectrum_app_with_config(config="cryptoadvance.spectrum.config.TestConfig")

@pytest.fixture
def client(app):
    """a test_client from an initialized Flask-App"""
    return app.test_client()

@pytest.fixture
def empty_data_folder():
    # Make sure that this folder never ever gets a reasonable non-testing use-case
    with tempfile.TemporaryDirectory(prefix="specter_home_tmp_") as data_folder:
        yield data_folder

# -------------------------------------------------------

@pytest.fixture
def mnemonic_hold_accident():
    return 11 * "hold " + "accident"


@pytest.fixture
def seed_hold_accident(mnemonic_hold_accident):
    seed = mnemonic_to_seed(mnemonic_hold_accident)
    print(f"Hold Accident seed: {hexlify(seed)}")
    return mnemonic_to_seed(mnemonic_hold_accident)


@pytest.fixture
def rootkey_hold_accident(seed_hold_accident):
    rootkey = HDKey.from_seed(seed_hold_accident)
    print(f"Hold Accident rootkey (xprv): {rootkey.to_base58()}")
    # xprv9s21ZrQH143K45uYUg7zhHku3bik5a2nw8XcanYCUGHn7RE1Bhkr53RWcjAQVFDTmruDceNDAGbc7yYsZCGveKMDrPr18hMsMcvYTGJ4Mae
    print(
        f"Hold Accident rootkey (tprv): {rootkey.to_base58(version=NETWORKS['test']['xprv'])}"
    )
    # tprv8ZgxMBicQKsPeu959EyVrwNtMj8xK64oGgSjTCxexEnFu1y6B56bannxXuL4Vcbn9JRzcjyyKdBQaq6cgQcsTNcpP34Jo45vGifxtuf9VGZ
    print(f"Hold Accident rootkey fp: {hexlify(rootkey.my_fingerprint)}")
    return rootkey


@pytest.fixture
def acc0xprv_hold_accident(rootkey_hold_accident: HDKey):
    xprv = rootkey_hold_accident.derive("m/84h/1h/0h")
    print(f"Hold Accident acc0xprv: {xprv.to_base58(version=NETWORKS['test']['xprv'])}")
    # tprv8g6WHqYgjvGrEU6eEdJxXzNUqN8DvLFb3iv3yUVomNRcNqT5JSKpTVNBzBD3qTDmmhRHPLcjE5fxFcGmU3FqU5u9zHm9W6sGX2isPMZAKq2

    return xprv


@pytest.fixture
def acc0xpub_hold_accident(acc0xprv_hold_accident: HDKey):
    xpub = acc0xprv_hold_accident.to_public()
    print(f"Hold Accident acc0xpub: {xpub.to_base58(version=NETWORKS['test']['xpub'])}")
    # vpub5YkPJgRQsev79YZM1NRDKJWDjLFcD2xSFAt6LehC5iiMMqQgMHyCFQzwsu16Rx9rBpXZVXPjWAxybuCpsayaw8qCDZtjwH9vifJ7WiQkHwu
    return xpub


@pytest.fixture
def acc0key0pubkey_hold_accident(acc0xpub_hold_accident: HDKey):
    pubkey = acc0xpub_hold_accident.derive("m/0/0")
    print("------------")
    print(pubkey.key)
    # 03584dc8282f626ce5570633018be0760baae68f1ecd6e801192c466ada55f5f31
    print(hexlify(pubkey.sec()))
    # b'03584dc8282f626ce5570633018be0760baae68f1ecd6e801192c466ada55f5f31'
    return pubkey


@pytest.fixture
def acc0key0addr_hold_accident(acc0key0pubkey_hold_accident):
    sc = script.p2wpkh(acc0key0pubkey_hold_accident)
    address = sc.address(NETWORKS["test"])
    print(address)  # m/84'/1'/0'/0/0
    # tb1qnwc84tkupy5v0tzgt27zkd3uxex3nmyr6vfhdd
    return address


@pytest.fixture
def key_hold_accident(acc0key0pubkey_hold_accident):
    sc = script.p2wpkh(acc0key0pubkey_hold_accident)
    address = sc.address(NETWORKS["test"])
    print(address)  # m/84'/1'/0'/0/0
    # tb1qnwc84tkupy5v0tzgt27zkd3uxex3nmyr6vfhdd
    return address


@pytest.fixture
def acc0key_hold_accident(acc0xpub_hold_accident, rootkey_hold_accident: HDKey):

    key: Key = Key(
        acc0xpub_hold_accident.to_base58(
            version=NETWORKS["test"]["xpub"]
        ),  # original (ToDo: better original)
        hexlify(rootkey_hold_accident.my_fingerprint).decode("utf-8"),  # fingerprint
        "m/84h/1h/0h",  # derivation
        "wpkh",  # key_type
        "Muuh",  # purpose
        acc0xpub_hold_accident.to_base58(version=NETWORKS["test"]["xpub"]),  # xpub
    )
    mydict = key.json
    print(json.dumps(mydict))

    return key
