from binascii import hexlify, unhexlify
import io
from cryptoadvance.spectrum.util import parse_blockheader


def test_blockchain_block_header(config):
    
    # We'll skip here the part where the blockheader is obtained via electrum:
    # This will only work in mainnet, run like this: 
    # pytest tests/test_elsock.py::test_blockchain_block_header --config cryptoadvance.spectrum.config.EmzyElectrumLiteConfig
    #es = ElectrumSocket(host=config.ELECTRUM_HOST, port=config.ELECTRUM_PORT, use_ssl=config.ELECTRUM_USES_SSL)
    # height=744133
    #block_header = es.call("blockchain.block.header", [height])
    # print(f"\nblockchain.block.header (height {height}) :")
    block_header = "04004020a59f49990cdd728a8e84d23719eae32287ace2bd5bef05000000000000000000aa5fa0d2d87a22f5251a3b4420b14dc6eeaabef6db78971863172dbead9213b7e108c862afa709173d8ad115"
    print(block_header)
    block_header = unhexlify(block_header)
    assert len(block_header) == 80 # A block_header is 80 byte long
    p_block_header = parse_blockheader(block_header)
    assert p_block_header["version"] == 541065220 # i don't understand this value, does not look like a proper version
    assert p_block_header["blocktime"] == 1657276641
    
    assert p_block_header["blockhash"] == "0000000000000000000993b3cdc6c0f66c0f2ab210d2ac250db90874e826b646"
    assert isinstance(p_block_header["blockhash"], str)