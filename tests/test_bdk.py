from binascii import hexlify
import json
import pytest

from embit.bip39 import mnemonic_to_seed
from embit.bip32 import HDKey, NETWORKS
from embit import script

from bdkpython import bdk

# Checkout:
# https://github.com/thunderbiscuit/bitcoindevkit-scripts/tree/aa601c93dfbe92f1812179f4441c002e091f2953/python
# In detail:
#


def test_bdk():

    mnemonic = 11 * "keen " + "join"

    mnemonic = bdk.Mnemonic.from_string(mnemonic)
    print(f"Keen Join seed: {mnemonic}")

    rootkey = bdk.DescriptorSecretKey(bdk.Network.REGTEST, mnemonic, "")
    print(f"Keen Join rootkey: {rootkey.as_string()}")

    acc0xprv_keen_join = rootkey.derive(bdk.DerivationPath("m/84h/1h/0h"))
    print(f"Keen Join acc0xprv: {acc0xprv_keen_join.as_string()}")

    xpub = acc0xprv_keen_join.as_public()
    print(f"Keen Join acc0xpub: {xpub.as_string()}")
    # tpubDCNx731HhXWZH7JigBeqN5F8T23pwrw7ny4v66b7XFajEF4Xwu1tHc4avQRVofghtzUs5BVNjYwRcqyfiBzftmfRFMKBWVCVdhQTWM1b7wM
