from embit import hashes
from embit.script import address_to_scriptpubkey


def get_blockhash(hex_header):
    return hashes.double_sha256(bytes.fromhex(hex_header))[::-1].hex()


def scripthash(script):
    """Calculates a scripthash for Electrum from address"""
    return hashes.sha256(script.data)[::-1].hex()


def sat_to_btc(sat):
    sat = sat or 0  # if None is passed
    return round(sat * 1e-8, 8)


def btc_to_sat(btc):
    btc = btc or 0  # if None is passed
    return round(btc * 1e8)
