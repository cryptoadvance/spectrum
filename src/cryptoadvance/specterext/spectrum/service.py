import logging
import os

from cryptoadvance.specter.managers.node_manager import NodeManager
from cryptoadvance.specter.services.service import Service, devstatus_alpha, devstatus_prod, devstatus_beta
# A SpecterError can be raised and will be shown to the user as a red banner
from cryptoadvance.specter.specter_error import SpecterError
from flask import current_app as app
from flask import url_for
from flask_apscheduler import APScheduler
from cryptoadvance.specterext.spectrum.spectrum_node import SpectrumNode
from cryptoadvance.spectrum.server import init_app, Spectrum
from cryptoadvance.spectrum.db import db
from cryptoadvance.specter.server_endpoints.welcome.welcome_vm import WelcomeVm

logger = logging.getLogger(__name__)

spectrum_node_alias = "spectrum_node"

class SpectrumService(Service):
    id = "spectrum"
    name = "Spectrum Service"
    icon = "spectrum/img/logo.svg"
    logo = "spectrum/img/logo.svg"
    desc = "An electrum hidden behind a core API"
    has_blueprint = True
    blueprint_modules = { 
        "default":  "cryptoadvance.specterext.spectrum.server_endpoints.ui"
    }
    devstatus = devstatus_alpha
    isolated_client = False

    # TODO: As more Services are integrated, we'll want more robust categorization and sorting logic
    sort_priority = 2

    @property
    def spectrum_node(self):
        ''' Iterates all nodes and returns the spectrum Node or None if it doesn't exist '''
        for node in app.specter.node_manager.nodes.values():
            if node.fqcn == "cryptoadvance.specterext.spectrum.spectrum_node.SpectrumNode":
                return node
        return None
    
    @property
    def is_spectrum_enabled(self):
        ''' Whether there is a spectrum Node available (activated or not) '''
        return not self.spectrum_node is None


    def callback_after_serverpy_init_app(self, scheduler: APScheduler):
        if not os.path.exists(app.config["SPECTRUM_DATADIR"]):
            os.makedirs(app.config["SPECTRUM_DATADIR"])
        logger.info(f"Intitializing Database in {app.config['SQLALCHEMY_DATABASE_URI']}")
        db.init_app(app)
        db.create_all()
        if self.is_spectrum_enabled:
            self.start_spectrum()
            self.spectrum_node.spectrum = self.spectrum
            self.activate_spectrum_node()
            logger.info("-------------------------")
            logger.info(f"Activated node: {self.spectrum_node} + {self.spectrum_node.rpc}")

    def enable_spectrum(self):
        ''' * starts spectrum 
            * inject it into the node (or create/save the node if not existing)
            * activate this node
        '''
        self.start_spectrum()
        has_spectrum_node = False
        if self.is_spectrum_enabled:
            self.spectrum_node.spectrum = self.spectrum
        else:
            # No SpectrumNode yet created. Let's do that.
            spectrum_node = SpectrumNode(spectrum=self.spectrum)
            app.specter.node_manager.nodes[spectrum_node_alias] = spectrum_node
            app.specter.node_manager.save_node(spectrum_node)
        self.activate_spectrum_node()

    def disable_spectrum(self):
        self.stop_spectrum()
        spectrum_node = None
        if self.is_spectrum_enabled:
            app.specter.node_manager.delete_node(self.spectrum_node)
        logger.info("Spectrum disabled")


    def start_spectrum(self):
        ''' instantiate Spectrum and syncs it '''
        logger.info("Creating Spectrum Object ...")
        self.spectrum = Spectrum(
            app.config["ELECTRUM_HOST"],
            app.config["ELECTRUM_PORT"],
            datadir=self.data_folder,
            app=app,
            ssl=app.config["ELECTRUM_USES_SSL"]
        )
        self.spectrum.sync()

    def activate_spectrum_node(self):
        nm: NodeManager = app.specter.node_manager
        nm.switch_node(spectrum_node_alias)

    def stop_spectrum(self):
        self.spectrum.stop()
        self.spectrum = None

    def callback_adjust_view_model(self, view_model: WelcomeVm):
        if view_model.__class__.__name__ == "WelcomeVm":
            # potentially, we could make a reidrect here:
            # view_model.about_redirect=url_for("spectrum_endpoint.some_enpoint_here")
            # but we do it small here and only replace a specific component:
            view_model.get_started_include = "spectrum/welcome/components/get_started.jinja"
        return view_model

