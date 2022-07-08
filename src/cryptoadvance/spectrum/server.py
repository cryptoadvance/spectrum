import json
import logging
import os

from flask import Flask, g, request

from .db import Script, db
from .spectrum import Spectrum
from .server_endpoints.core_api import core_api
from .server_endpoints.healthz import healthz

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

    app.logger.info("-------------------------CONFIGURATION-OVERVIEW------------ (only in debug)")
    app.logger.info("Config from "+os.environ.get("CONFIG","empty"))
    # for key, value in sorted(app.config.items()):
    #     if key in ["DB_PASSWORD","SECRET_KEY","SQLALCHEMY_DATABASE_URI"]:
    #         app.logger.debug("{} = {}".format(key,"xxxxxxxxxxxx"))
    #     else:
    #         app.logger.debug("{} = {}".format(key,value))
    app.logger.info("-----------------------------------------------------------")

    app.register_blueprint(core_api)
    app.register_blueprint(healthz)

    app.logger.info(f"Creating Database Structure {app.config['SQLALCHEMY_DATABASE_URI']}...")
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

def init_app(app):
    with app.app_context():
        app.spectrum.sync()


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
