import logging
from flask import redirect, render_template, request, url_for, flash
from flask import current_app as app
from flask_login import login_required, current_user

from cryptoadvance.specter.specter import Specter
from cryptoadvance.specter.services.controller import user_secret_decrypted_required
from cryptoadvance.specter.user import User
from cryptoadvance.specter.wallet import Wallet
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
@user_secret_decrypted_required
def index():
    return render_template(
        "spectrum/index.jinja",
    )
    

@spectrum_endpoint.route("/settings", methods=["GET"])
@login_required
@user_secret_decrypted_required
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
@user_secret_decrypted_required
def settings_post():
    show_menu = request.form["show_menu"]
    user = app.specter.user_manager.get_user()
    if show_menu == "yes":
        user.add_service(SpectrumService.id)
    else:
        user.remove_service(SpectrumService.id)
    used_wallet_alias = request.form.get("used_wallet")
    if used_wallet_alias != None:
        wallet = current_user.wallet_manager.get_by_alias(used_wallet_alias)
        SpectrumService.set_associated_wallet(wallet)
    return redirect(url_for(f"{ SpectrumService.get_blueprint_name()}.settings_get"))
