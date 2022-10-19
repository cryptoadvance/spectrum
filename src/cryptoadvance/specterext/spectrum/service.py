import logging
import os

from cryptoadvance.specter.managers.node_manager import NodeManager
from cryptoadvance.specter.services.service import Service, devstatus_alpha, devstatus_prod, devstatus_beta
# A SpecterError can be raised and will be shown to the user as a red banner
from cryptoadvance.specter.specter_error import SpecterError
from flask import current_app as app
from flask_apscheduler import APScheduler
from cryptoadvance.specterext.spectrum.spectrum_node import SpectrumNode
from cryptoadvance.spectrum.server import init_app, Spectrum
from cryptoadvance.spectrum.db import db

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
        datadir = app.config["DATADIR"]
        if not os.path.exists(datadir):
            os.makedirs(datadir)
        db.init_app(app)
        db.create_all()
        logger.info("Creating Spectrum Object ...")
        self.spectrum = Spectrum(
            app.config["ELECTRUM_HOST"],
            app.config["ELECTRUM_PORT"],
            datadir=self.data_folder,
            app=app,
            ssl=app.config["ELECTRUM_USES_SSL"]
        )
        self.spectrum.sync()
        
        has_spectrum_node = False
        for node in app.specter.node_manager.nodes.values():
            if node.fqcn == "cryptoadvance.specterext.spectrum.spectrum_node.SpectrumNode":
                node.spectrum = self.spectrum
                has_spectrum_node=True
        
        if not has_spectrum_node:                
            # No SpectrumNode yet created. Let's do that.
            spectrum_node = SpectrumNode(self.spectrum)
            app.specter.node_manager.nodes["spectrum_node"] = spectrum_node
            app.specter.node_manager.save_node(spectrum_node)


    def callback_initial_node_contribution(self, node_manager:NodeManager):
        logger.info("Creating SpectrumNode")
        return [ SpectrumNode(app.spectrum) ]

    def create_nodes(self, node_dicts):
        ''' Gets a huge dict with node-descriptions and returns nodes it can create Nodes-objects from '''
        print(node_dicts)
        pass
