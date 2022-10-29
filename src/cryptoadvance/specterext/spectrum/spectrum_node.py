import logging
from cryptoadvance.specterext.spectrum.bridge_rpc import BridgeRPC
from cryptoadvance.specter.helpers import deep_update
from cryptoadvance.specter.node import AbstractNode
from cryptoadvance.specter.specter_error import BrokenCoreConnectionException
from cryptoadvance.spectrum.spectrum import Spectrum

logger = logging.getLogger(__name__)

class SpectrumNode(AbstractNode):
    ''' A Node implementation which returns a bridge_rpc class to connect to a spectrum '''
    external_node=True

    def __init__(self, name = "Spectrum Node", alias = "spectrum_node", spectrum=None, host=None, port=None, ssl=None):
        self._spectrum = spectrum
        self.name = "Spectrum Node"
        self.alias = "spectrum_node" # used for the file: nodes/spectrum_node.json
        self._host = host
        self._port = port
        self._ssl = ssl
        
        # ToDo: Should not be necessary
        self._rpc = None

    def start_spectrum(self, app, datadir):
        if self._host is None or self._port is None or self._ssl is None:
            raise BrokenCoreConnectionException(f"Cannot start spectrum without host ({self._host}), port ({self._port}) or ssl ({self._ssl})")
        try:
            self.spectrum = Spectrum(
                self._host,
                self._port,
                self._ssl,
                datadir=datadir,
                app=app,
            )
        except Exception as e:
            logger.exception(e)

    def stop_spectrum(self):
        if self.spectrum:
            self.spectrum.stop()
            self.spectrum = None

    def update_electrum(self, host, port, ssl, app, datadir):
        if host is None or port is None or ssl is None:
            raise BrokenCoreConnectionException(f"Cannot start spectrum without host ({host}), port ({port}) or ssl ({ssl})")
        self._host = host
        self._port = port
        self._ssl = ssl
        self.stop_spectrum()
        self.start_spectrum(app, datadir)


    @classmethod
    def from_json(cls, node_dict, *args, **kwargs):
        """Create a Node from json"""
        logger.debug(f"Instantiating spectrum_node with node_dict {node_dict} args ({args}) and kwargs {kwargs}")
        name = node_dict.get("name", "")
        alias = node_dict.get("alias", "")
        host = node_dict.get("host", None)
        port = node_dict.get("port", None)
        ssl = node_dict.get("ssl", None)

        return cls(
            name, alias, host=host, port=port, ssl=ssl
        )

    @property
    def json(self):
        """Get a json-representation of this Node"""
        node_json = super().json
        return deep_update(
            node_json,
            {
                "name":     self.name,
                "alias":    self.alias,
                "host":     self.host,
                "port":     self.port,
                "ssl":      self.ssl
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
    def spectrum(self):
        return self._spectrum

    @spectrum.setter
    def spectrum(self, value):
        self._spectrum = value
        if self._spectrum is not None:
            self._rpc = BridgeRPC(self.spectrum)
        else:
            self._rpc = None

    @property
    def host(self):
        if self.spectrum:
            return self.spectrum.host
        return self._host

    @property
    def port(self):
        if self.spectrum:
            return self.spectrum.port
        return self._port

    @property
    def ssl(self):
        if self.spectrum:
            return self.spectrum.ssl
        return self._ssl


    @property
    def rpc(self):
        if self._rpc is None:
            self._rpc = BridgeRPC(self.spectrum)
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
