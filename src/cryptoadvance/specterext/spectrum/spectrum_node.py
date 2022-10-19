import logging
from cryptoadvance.specter.persistence import BusinessObject
from cryptoadvance.specterext.spectrum.bridge_rpc import BridgeRPC
from cryptoadvance.specter.helpers import deep_update
from cryptoadvance.specter.node import AbstractNode
from cryptoadvance.spectrum.error import SpectrumException
from cryptoadvance.spectrum.spectrum import Spectrum

logger = logging.getLogger(__name__)

class SpectrumNode(AbstractNode):
    ''' A Node implementation which returns a bridge_rpc class to connect to a spectrum '''

    def __init__(self, name = "Spectrum Node", alias = "spectrum_node", spectrum=None):
        self.spectrum = spectrum
        self.name = "Spectrum Node"
        self.alias = "spectrum_node" # used for the file: nodes/spectrum_node.json
        
        # ToDo: Should not be necessary
        self.external_node = True
        self._rpc = None

    @classmethod
    def from_json(cls, node_dict, *args, **kwargs):
        """Create a Node from json"""
        name = node_dict.get("name", "")
        alias = node_dict.get("alias", "")

        return cls(
            name, alias
        )

    @property
    def json(self):
        """Get a json-representation of this Node"""
        node_json = super().json
        return deep_update(
            node_json,
            {
                "name": self.name,
                "alias": self.alias,
            },
        )


    def check_blockheight(self):
        ''' This naive implementation always returns True: Claiming that new blocks have arrived, we're forcing 
            the caller to always recalculate everything. 
            That's possible because calling those rpc-calls on spectrum's side is cheap. 
            It might not be cheap on Specter's side but that's for Specter to optimize!
        '''
        return True

    @property
    def host(self):
        return self.spectrum.host

    @property
    def port(self):
        return self.spectrum.port


    @property
    def rpc(self):
        if self.spectrum == None:
            raise SpectrumException("SpectrumNode does not have a spectrum Reference yet")
        if self._rpc is None:
            logger.info("Creating BridgeRPC ...")
            self._rpc = BridgeRPC(self._spectrum)
        return self._rpc

    def get_rpc(self):
        """
        return ta BridgeRPC
        """
        return self.rpc

    def update_rpc(self):
        ''' No need to do anything '''
        pass

    def node_info_template(self):
        return "spectrum/components/spectrum_info.jinja"
