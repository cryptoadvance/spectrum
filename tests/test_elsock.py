from binascii import hexlify, unhexlify
import io
import time
from cryptoadvance.spectrum.elsock import ElectrumSocket
import hashlib
import struct


def test_elsock(config):
    es = ElectrumSocket(host=config.ELECTRUM_HOST, port=config.ELECTRUM_PORT)
    res = es.ping()
    print(f"ping took {res} seconds")
    
    res = es.call("server.version", [0])
    print("\nserver.version:")
    print(res)

    res = es.call("blockchain.headers.subscribe")
    print("\nblockchain.headers.subscribe :")
    print(res)



