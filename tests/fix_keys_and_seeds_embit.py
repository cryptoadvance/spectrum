from binascii import hexlify
import json
import pytest

from embit.bip39 import mnemonic_to_seed
from embit.bip32 import HDKey, NETWORKS
from embit import script

from bdkpython import bdk
import bdkpython as bdk

mnemonic_ghost_machine = (
    "ghost ghost ghost ghost ghost ghost ghost ghost ghost ghost ghost machine"
)


seed = bdk.Mnemonic.from_string(mnemonic_ghost_machine)


@pytest.fixture
def mnemonic_keen_join():
    return 11 * "keen " + "join"


@pytest.fixture
def seed_keen_join(mnemonic_keen_join):
    seed = bdk.Mnemonic.from_string(mnemonic_ghost_machine)
    print(f"Keen Join seed: {hexlify(seed)}")
    return mnemonic_to_seed(mnemonic_keen_join)


@pytest.fixture
def rootkey_keen_join(seed_keen_join):
    rootkey = HDKey.from_seed(seed_keen_join)
    print(f"Keen Join rootkey: {rootkey.to_base58()}")
    # xprv9s21ZrQH143K3LEXAFcSsTmDGYrgbRs62sNyv1GMwFFwxQDVC3hQZK7LRDUBknzKnN8iT6RxRt9zSibY3qLrnrfTRTw1LtmBSdZJwfLAgK1
    print(f"Keen Join rootkey fp: {hexlify(rootkey.my_fingerprint)}")  # dcbf0caf
    return rootkey


@pytest.fixture
def acc0xprv_keen_join(rootkey_keen_join: HDKey):
    xprv = rootkey_keen_join.derive("m/84h/1h/0h")
    print(f"Keen Join acc0xprv: {xprv.to_base58(version=NETWORKS['test']['xprv'])}")
    # tprv8fguxcy3Z9ptPeGvnXzExfb1szXtnXkDDfU8oaYp6ynLPkomKWCJ77SikGXt1Gf4zkJaagBJSQFt8UvY2HviJyAKPej7cWn8oD3bkpV2CVQ

    return xprv


@pytest.fixture
def acc0xpub_keen_join(acc0xprv_keen_join: HDKey):
    xpub = acc0xprv_keen_join.to_public()
    print(f"Keen Join acc0xpub: {xpub.to_base58(version=NETWORKS['test']['xpub'])}")
    # tpubDCNx731HhXWZH7JigBeqN5F8T23pwrw7ny4v66b7XFajEF4Xwu1tHc4avQRVofghtzUs5BVNjYwRcqyfiBzftmfRFMKBWVCVdhQTWM1b7wM
    return xpub


@pytest.fixture
def acc0key0pubkey_keen_join(acc0xpub_keen_join: HDKey):
    pubkey = acc0xpub_keen_join.derive("m/0/0")
    print(f"Keen Join {pubkey.key}")
    print(f"Keen Join hexlify(pubkey.sec()) : {hexlify(pubkey.sec())}")
    print(hexlify(pubkey.sec()))
    return pubkey


@pytest.fixture
def acc0key0addr_keen_join(acc0key0pubkey_keen_join):
    sc = script.p2wpkh(acc0key0pubkey_keen_join)
    address = sc.address(NETWORKS["test"])
    print(f"Keen Join {address}")  # m/84'/1'/0'/0/0
    return address


@pytest.fixture
def key_keen_join(acc0key0pubkey_keen_join):
    sc = script.p2wpkh(acc0key0pubkey_keen_join)
    address = sc.address(NETWORKS["test"])
    return address


@pytest.fixture
def acc0key_keen_join(acc0xpub_keen_join, rootkey_keen_join: HDKey):

    key: Key = Key(
        acc0xpub_keen_join.to_base58(
            version=NETWORKS["test"]["xpub"]
        ),  # original (ToDo: better original)
        hexlify(rootkey_keen_join.my_fingerprint).decode("utf-8"),  # fingerprint
        "m/84h/1h/0h",  # derivation
        "wpkh",  # key_type
        "Muuh",  # purpose
        acc0xpub_keen_join.to_base58(version=NETWORKS["test"]["xpub"]),  # xpub
    )
    mydict = key.json
    print(json.dumps(mydict))

    return key


# hold hold hold hold hold hold hold hold hold hold hold accident
# This is a formal creation of all major bitcoin artifacts from the
# hold accident mnemonic


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
    print(f"Hold Accident rootkey: {rootkey.to_base58()}")
    # xprv9s21ZrQH143K45uYUg7zhHku3bik5a2nw8XcanYCUGHn7RE1Bhkr53RWcjAQVFDTmruDceNDAGbc7yYsZCGveKMDrPr18hMsMcvYTGJ4Mae
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
