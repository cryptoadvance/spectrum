import logging
from flask import redirect, render_template, request, url_for, flash
from flask import current_app as app
from flask_login import login_required, current_user

from cryptoadvance.specter.specter import Specter
from cryptoadvance.specter.services.controller import user_secret_decrypted_required
from cryptoadvance.specter.user import User
from cryptoadvance.specter.wallet import Wallet
from cryptoadvance.specter.specter_error import SpecterError
from ..service import SpectrumService


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
    wallet_names = sorted(current_user.wallet_manager.wallets.keys())
    wallets = [current_user.wallet_manager.wallets[name] for name in wallet_names]

    return render_template(
        "spectrum/settings.jinja",
        wallets=wallets,
        cookies=request.cookies,
    )

@spectrum_endpoint.route("/settings", methods=["POST"])
@login_required
def settings_post():
    show_menu = request.form["show_menu"]
    host = request.form.get("host")
    port = request.form.get("port")
    ssl = request.form.get("ssl")

    user = app.specter.user_manager.get_user()
    if show_menu == "yes":
        user.add_service(SpectrumService.id)
    else:
        user.remove_service(SpectrumService.id)
    used_wallet_alias = request.form.get("used_wallet")
    if used_wallet_alias != None:
        wallet = current_user.wallet_manager.get_by_alias(used_wallet_alias)
        SpectrumService.set_associated_wallet(wallet)
        ext().set_current_user_service_data({"electrum_connection": { "host": host, "port":port, "ssl":ssl}})
    return redirect(url_for(f"{ SpectrumService.get_blueprint_name()}.settings_get"))

@spectrum_endpoint.route("/spectrum_setup", methods=["GET"])
@login_required
def spectrum_setup():
    ext().enable_spectrum()
    return render_template(
        "spectrum/spectrum_setup.jinja",
    )

# @spectrum_endpoint.route("/about", methods=["POST"])
# @login_required
# def about():
#     return render_template(
#         "spectrum/to_be_done_about.jinja",
#         cookies=request.cookies,
#     )

