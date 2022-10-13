import logging
from cryptoadvance.specter.persistence import BusinessObject
from cryptoadvance.specterext.spectrum.bridge_rpc import BridgeRPC
from cryptoadvance.specter.helpers import deep_update
from cryptoadvance.specter.node import AbstractNode
from cryptoadvance.spectrum.spectrum import Spectrum

logger = logging.getLogger(__name__)

class SpectrumNode(AbstractNode):
    ''' A Node implementation which returns a bridge_rpc class to connect to a spectrum '''

    def __init__(self, name = "Spectrum Node", alias = "spectrum_node", spectrum=None):
        self._spectrum = spectrum
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
            raise Exception("SpectrumNode does not have a spectrum Reference yet")
        if self._rpc is None:
            logger.info("Creating BridgeRPC ...")
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

    def rendering_table(self):
        return '''
        <h1>Spectrum Node</h1>
        <table>
        <tr> <td style="text-align: left;">{{ _("Network") }}:</td> <td style="text-align: right;" id="node-info-specter-chain">{{specter.chain}}</td> </tr>
        <tr> <td style="text-align: left; width: 35%;">{{ _("Bitcoin Core Version") }}:</td> <td style="text-align: right;">v{{specter.bitcoin_core_version}} <span class="note">({{specter.network_info['version']}})</span></td> </tr>
        <tr> <td style="text-align: left;">{{ _("Connections count") }}:</td> <td style="text-align: right;">{{specter.network_info['connections']}}</td> </tr>
        <tr> <td style="text-align: left;">{{ _("Difficulty") }}:</td> <td style="text-align: right;">{{specter.info.get('difficulty', 0) | int}}</td> </tr>
        <tr> <td style="text-align: left;">{{ _("Size on disk") }}:</td> <td style="text-align: right;">{{specter.info['size_on_disk']|bytessize }}</td> </tr>
        <tr> <td style="text-align: left;">{{ _("Blocks count") }}:</td> <td style="text-align: right;">{{specter.info['blocks']}}</td> </tr>
        <tr> <td style="text-align: left;">{{ _("Last block hash") }}:</td> <td style="text-align: right"><code style="word-break: break-word;">{{specter.info['bestblockhash']}}</code></td> </tr>
        <tr> <td style="text-align: left;">{{ _("Node uptime") }}:</td> <td style="text-align: right;">~ {{(specter.node.uptime / 60 // 60) | int }} {{ _("Hours") }}</td> </tr>
        {% if specter.info['pruned'] %}
            <tr> <td style="text-align: left;">{{ _("Automatic pruning") }}:</td> <td style="text-align: right;">{{specter.info['automatic_pruning']}}</td> </tr>
            <tr> <td style="text-align: left;">{{ _("Prune height") }}:</td> <td style="text-align: right;">{{specter.info['pruneheight']}}</td> </tr>
            <tr> <td style="text-align: left;">{{ _("Prune target size") }}:</td> <td style="text-align: right;">{{specter.info['prune_target_size']}}</td> </tr>
        {% endif %}
        </table>
        '''