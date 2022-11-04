import logging
from flask import redirect, render_template, request, url_for, flash
from flask import current_app as app
from flask_login import login_required, current_user

from cryptoadvance.specter.specter import Specter
from cryptoadvance.specter.services.controller import user_secret_decrypted_required
from cryptoadvance.specter.user import User
from cryptoadvance.specter.wallet import Wallet
from cryptoadvance.specter.specter_error import SpecterError

from cryptoadvance.specterext.spectrum.spectrum_node import SpectrumNode
from .service import SpectrumService


logger = logging.getLogger(__name__)

spectrum_endpoint = SpectrumService.blueprint

def ext() -> SpectrumService:
    ''' convenience for getting the extension-object'''
    return app.specter.ext["spectrum"]

def specter() -> Specter:
    ''' convenience for getting the specter-object'''
    return app.specter


@spectrum_endpoint.route("/")
@login_required
def index(node_alias=None):
    if node_alias is not None and node_alias != "spectrum_node":
        raise SpecterError(f"Unknown Spectrum Node: {node_alias}")
    return render_template(
        "spectrum/index.jinja",
    )


@spectrum_endpoint.route("node/<node_alias>/", methods=["GET", "POST"])
@login_required
def node_settings(node_alias=None):
    if node_alias is not None and node_alias != "spectrum_node":
        raise SpecterError(f"Unknown Spectrum Node: {node_alias}")
    return redirect(url_for("spectrum_endpoint.settings_get"))

@spectrum_endpoint.route("/settings", methods=["GET"])
@login_required
def settings_get():

    # Get the user's Wallet objs, sorted by Wallet.name
    electrum_options = app.config["ELECTRUM_OPTIONS"]
    spectrum_node: SpectrumNode = ext().spectrum_node
    host = spectrum_node.host
    port = spectrum_node.port
    ssl = spectrum_node.ssl
    elec_chosen_option = "manual"
    for opt_key, elec in electrum_options.items():
        if elec["host"] == host and elec["port"] == port and elec["ssl"] == ssl:
            elec_chosen_option = opt_key

    return render_template(
        "spectrum/settings.jinja",
        elec_options=electrum_options,
        elec_chosen_option=elec_chosen_option,
        host = host,
        port = port,
        ssl = ssl,
    )

@spectrum_endpoint.route("/settings", methods=["POST"])
@login_required
def settings_post():

    host = request.form.get('host')
    try:
        port = int(request.form.get('port'))
    except ValueError:
        port = 0
    ssl = request.form.get('ssl') == "on"
    option_mode = request.form.get('option_mode')
    electrum_options = app.config["ELECTRUM_OPTIONS"]
    
    elec_option = request.form.get('elec_option')
    if option_mode == "list":
        host = electrum_options[elec_option]["host"]
        port = electrum_options[elec_option]["port"]
        ssl = electrum_options[elec_option]["ssl"]

    ext().update_electrum(host, port, ssl)
    return redirect(url_for(f"{ SpectrumService.get_blueprint_name()}.settings_get"))

@spectrum_endpoint.route("/spectrum_setup", methods=["GET"])
@login_required
def spectrum_setup():
    ext().enable_spectrum()
    return render_template(
        "spectrum/spectrum_setup.jinja",
    )

