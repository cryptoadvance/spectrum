''' This is a duplication of cryptoadvance.specterext.spectrum.server_endpoints.core_api'''

import json,logging

# COMMENTED:
# from ..service import SpectrumService

from flask import (
    Blueprint,
    request
)

from flask import current_app as app

logger = logging.getLogger(__name__)

# Canged:
core_api = Blueprint("core_api", __name__)


@core_api.route("/", methods=["GET", "POST"])
def index():
    if request.method == "GET":
        return "JSONRPC server handles only POST requests"
    data = request.get_json()
    if isinstance(data, dict):
        return json.dumps(app.spectrum.jsonrpc(data))
    if isinstance(data, list):
        return json.dumps([app.spectrum.jsonrpc(item) for item in data])

@core_api.route("/wallet/", methods=["GET", "POST"])
@core_api.route("/wallet/<path:wallet_name>", methods=["GET", "POST"])
def walletrpc(wallet_name=""):
    if request.method == "GET":
        return "JSONRPC server handles only POST requests"
    data = request.get_json()
    if isinstance(data, dict):
        return json.dumps(app.spectrum.jsonrpc(data, wallet_name=wallet_name))
    if isinstance(data, list):
        return json.dumps(
            [app.spectrum.jsonrpc(item, wallet_name=wallet_name) for item in data]
        )

