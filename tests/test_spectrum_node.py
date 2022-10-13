from cryptoadvance.specterext.spectrum.spectrum_node import SpectrumNode

def test_SpectrumNode():
    sn = SpectrumNode("Some name")
    assert sn.chain == "chain"