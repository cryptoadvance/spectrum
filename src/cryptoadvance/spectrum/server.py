import json
import logging
import os

from flask import Flask, g, request

from .db import Script, db
from .spectrum import Spectrum

logger = logging.getLogger(__name__)

def create_app(config="cryptoadvance.spectrum.config.LocalElectrumConfig"):
    if os.environ.get("CONFIG"):
        config = os.environ.get("CONFIG")
    app = Flask(__name__)
    app.config.from_object(config)
    logger.info(f"config: {config}")

    # create folder if doesn't exist
    if not os.path.exists(app.config["DATADIR"]):
        os.makedirs(app.config["DATADIR"])

    db.init_app(app)

    app.logger.info("-------------------------CONFIGURATION-OVERVIEW------------")
    app.logger.info("Config from "+os.environ.get("CONFIG","empty"))
    for key, value in sorted(app.config.items()):
        if key in ["DB_PASSWORD","SECRET_KEY","SQLALCHEMY_DATABASE_URI"]:
            app.logger.info("{} = {}".format(key,"xxxxxxxxxxxx"))
        else:
            app.logger.info("{} = {}".format(key,value))
    app.logger.info("-----------------------------------------------------------")

    @app.route("/", methods=["GET", "POST"])
    def index():
        if request.method == "GET":
            return "JSONRPC server handles only POST requests"
        data = request.get_json()
        if isinstance(data, dict):
            return json.dumps(app.spectrum.jsonrpc(data))
        if isinstance(data, list):
            return json.dumps([app.spectrum.jsonrpc(item) for item in data])

    @app.route("/wallet/", methods=["GET", "POST"])
    @app.route("/wallet/<path:wallet_name>", methods=["GET", "POST"])
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

    @app.route("/healthz/liveness")
    def liveness():
        return {"message": "i am alive"}

    @app.route("/healthz/readyness")
    def readyness():
        try:
            # Probably improvable:
            assert app.spectrum.sock is not None
        except Exception as e:
            return {"message": "i am not ready"}, 500
        return {"message": "i am ready"}

    with app.app_context():
        db.create_all()

    with app.app_context():
        # if not getattr(g, "electrum", None):
        logger.info("Creating Spectrum Object ...")
        app.spectrum = Spectrum(
            app.config["ELECTRUM_HOST"],
            app.config["ELECTRUM_PORT"],
            datadir=app.config["DATADIR"],
            app=app,
            ssl=app.config["ELECTRUM_USES_SSL"]
        )

    return app


def main():
    # TODO: debug=True spawns two Electrum servers and this causes duplications in transactions
    config = {
        "datadir": "data",
        "database": os.path.abspath(os.path.join("data", "wallets.sqlite")),
        "host": "127.0.0.1",
        "port": 8081,
        "debug": False,
        "electrum": {
            "host": "127.0.0.1",
            "port": 60401,  # 50000,
            # "host": "35.201.74.156",
            # "port": 143,
        },
    }
    app = create_app(config)
    app.run(debug=config["debug"], port=config["port"], host=config["host"])


if __name__ == "__main__":
    main()
