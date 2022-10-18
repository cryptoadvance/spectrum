import logging

from cryptoadvance.specter.managers.node_manager import NodeManager
from cryptoadvance.specter.services.service import Service, devstatus_alpha, devstatus_prod, devstatus_beta
# A SpecterError can be raised and will be shown to the user as a red banner
from cryptoadvance.specter.specter_error import SpecterError
from flask import current_app as app
from flask_apscheduler import APScheduler
from cryptoadvance.specterext.spectrum.spectrum_node import SpectrumNode
from cryptoadvance.spectrum.server import init_app

logger = logging.getLogger(__name__)

class SpectrumService(Service):
    id = "spectrum"
    name = "Spectrum Service"
    icon = "spectrum/img/ghost.png"
    logo = "spectrum/img/logo.jpeg"
    desc = "Where a spectrum grows bigger."
    has_blueprint = True
    blueprint_modules = { 
        "default":  "cryptoadvance.specterext.spectrum.server_endpoints.ui"
    }
    devstatus = devstatus_alpha
    isolated_client = False

    # TODO: As more Services are integrated, we'll want more robust categorization and sorting logic
    sort_priority = 2

    def callback_after_serverpy_init_app(self, scheduler: APScheduler):
        # This will create app.spectrum
        init_app(app, datadir=self.data_folder, standalone=False)
        
        
        for node in app.specter.node_manager.nodes.values():
            if node.fqcn == "cryptoadvance.specterext.spectrum.spectrum_node.SpectrumNode":
                node.spectrum = app.spectrum
                return
        
        # No SpectrumNode yet created. Let's do that.
        app.specter.node_manager.save_node(SpectrumNode(app.spectrum))


    def callback_initial_node_contribution(self, node_manager:NodeManager):
        logger.info("Creating SpectrumNode")
        return [ SpectrumNode(app.spectrum) ]

    def create_nodes(self, node_dicts):
        ''' Gets a huge dict with node-descriptions and returns nodes it can create Nodes-objects from '''
        print(node_dicts)
        pass
