import pytest
from cryptoadvance.specterext.spectrum.spectrum_node import SpectrumNode
from cryptoadvance.spectrum.util import SpectrumException

def test_SpectrumNode():
    sn = SpectrumNode("Some name")
    with pytest.raises(SpectrumException):
        assert sn.chain == "chain"