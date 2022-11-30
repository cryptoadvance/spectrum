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
    # Show current configuration
    if ext().id in specter().user.services:
        show_menu = "yes"
    else:
        show_menu = "no"
    electrum_options = app.config["ELECTRUM_OPTIONS"]
    elec_chosen_option = "manual"
    spectrum_node: SpectrumNode = ext().spectrum_node
    if spectrum_node is not None:
        host = spectrum_node.host
        port = spectrum_node.port
        ssl = spectrum_node.ssl
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
            show_menu = show_menu,
        )
    else:
        return render_template(
            "spectrum/settings.jinja",
            elec_options=electrum_options,
            elec_chosen_option="list",
            show_menu = show_menu,
        )


@spectrum_endpoint.route("/settings", methods=["POST"])
@login_required
def settings_post():
    # Node status before saving the settings
    node_is_running_before_request = False
    host_before_request = None
    if ext().is_spectrum_node_available:
        node_is_running_before_request = ext().spectrum_node.is_running
        host_before_request = ext().spectrum_node.host
        logger.debug(f"The host before saving the new settings: {host_before_request}")
    logger.debug(f"Node running before updating settings: {node_is_running_before_request}")
    
    # Gather the Electrum server settings from the form and update with them
    success = False
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
    # If there is already a Spectrum node, just update with the new values (restarts Spectrum)
    if ext().is_spectrum_node_available:
        ext().update_electrum(host, port, ssl)
    # Otherwise, create the Spectrum node and then start Spectrum
    else:
        ext().enable_spectrum(host, port, ssl, activate_spectrum_node=False)
    # Make the Spectrum node the new active node and save it to disk, but only if the connection is working"""
    # BETA_VERSION: Additional check that there is no Bitcoin Core node for the same network alongside the Spectrum node 
    spectrum_node = ext().spectrum_node

    if check_for_node_on_same_network(spectrum_node):
        # Delete Spectrum node again (it wasn't saved to disk yet)
        del specter().node_manager.nodes[spectrum_node.alias]
        return render_template("spectrum/spectrum_setup_beta.jinja",
                                    core_node_exists=True)

    if ext().spectrum_node.is_running:
        logger.debug("Activating Spectrum node ...")
        ext().activate_spectrum_node()
        success = True
    
    # Set the menu item
    show_menu = request.form["show_menu"]
    user = specter().user_manager.get_user()
    if show_menu == "yes":
        user.add_service(ext().id)
    else:
        user.remove_service(ext().id)
    
    # Determine changes for better feedback message in the jinja template
    logger.debug(f"Node running after updating settings: {success}")
    host_after_request = ext().spectrum_node.host
    logger.debug(f"The host after saving the new settings: {host_after_request}")
    
    changed_host, check_port_and_ssl = evaluate_current_status(
        node_is_running_before_request, 
        host_before_request, 
        host_after_request, 
        success
    )

    return render_template("spectrum/spectrum_setup.jinja", 
                    success=success, 
                    changed_host=changed_host,
                    host_type = option_mode,
                    check_port_and_ssl = check_port_and_ssl,
                    )

def check_for_node_on_same_network(spectrum_node):
        if spectrum_node is not None:
            current_spectrum_chain = spectrum_node.chain
            nodes_current_chain = specter().node_manager.nodes_by_chain(current_spectrum_chain)
            # Check whether there is a Bitcoin Core node for the same network:
            core_node_exists = False
            for node in nodes_current_chain:
                logger.debug(node)
                if node.fqcn != "cryptoadvance.specterext.spectrum.spectrum_node.SpectrumNode" and not node.is_liquid:
                    return True
        return False

def evaluate_current_status(node_is_running_before_request, host_before_request, host_after_request, success):
    ''' Figures out whether the:
        * the user changed the host and/or
        * the user changed the port/ssl
        and returns two booleans: changed_host, check_port_and_ssl
        useful for user-feedback.
    '''
    changed_host = False
    check_port_and_ssl = False
    if node_is_running_before_request == success and success == True and host_before_request == host_after_request:
        # Case 1: We changed a setting that didn't impact the Spectrum node, currently only the menu item setting
            return redirect(url_for(f"{ SpectrumService.get_blueprint_name()}.settings_get"))
    if node_is_running_before_request == success and success == True and host_before_request != host_after_request:
        # Case 2: We changed the host but switched from one working connection to another one
            changed_host = True
    if node_is_running_before_request and not success:
        # Case 3: We changed the host from a working to a broken connection
        if host_before_request != host_after_request:
            changed_host = True
        # Case 4: We didn't change the host but probably other configs such as port and / or ssl which are likely the reason for the broken connection
        # TODO: Worth it to also check for changes in the port / ssl configs?
        else:
            check_port_and_ssl = True
    if not node_is_running_before_request and success:
        # Case 5: We changed the host from a broken to a working connection
        if host_before_request != host_after_request and host_before_request != None:
            changed_host = True
        # Case 6: We didn't change the host but only the port and / or ssl config which did the trick
        else:
            # Not necessary since this is set to False by default, just to improve readability
            check_port_and_ssl = False
    return changed_host, check_port_and_ssl
