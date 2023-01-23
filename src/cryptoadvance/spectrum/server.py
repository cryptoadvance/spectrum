import json
import logging
import os

from flask import Flask, g, request

from .db import Script, db
from .spectrum import Spectrum
from .server_endpoints.core_api import core_api
from .server_endpoints.healthz import healthz

logger = logging.getLogger(__name__)


def create_app(config="cryptoadvance.spectrum.config.EmzyElectrumLiteConfig"):
    if os.environ.get("CONFIG"):
        config = os.environ.get("CONFIG")
    app = Flask(__name__)
    app.config.from_object(config)
    logger.info(f"config: {config}")
    return app


def init_app(app, datadir=None, standalone=True):
    # create folder if doesn't exist
    if datadir is None:
        datadir = app.config["SPECTRUM_DATADIR"]
    if not os.path.exists(datadir):
        os.makedirs(datadir)
    db.init_app(app)

    with app.app_context():
        db.create_all()
        app.logger.info("-------------------------CONFIGURATION-OVERVIEW------------")
        app.logger.info("Config from " + os.environ.get("CONFIG", "empty"))
        for key, value in sorted(app.config.items()):
            if key in ["DB_PASSWORD", "SECRET_KEY", "SQLALCHEMY_DATABASE_URI"]:
                app.logger.info("{} = {}".format(key, "xxxxxxxxxxxx"))
            else:
                app.logger.info("{} = {}".format(key, value))
        app.logger.info("-----------------------------------------------------------")
        from cryptoadvance.spectrum.server_endpoints.core_api import core_api
        from .server_endpoints.healthz import healthz

        app.register_blueprint(core_api)
        app.register_blueprint(healthz)

        # if not getattr(g, "electrum", None):
        logger.info("Creating Spectrum Object ...")
        app.spectrum = Spectrum(
            app.config["ELECTRUM_HOST"],
            app.config["ELECTRUM_PORT"],
            ssl=app.config["ELECTRUM_USES_SSL"],
            datadir=app.config["SPECTRUM_DATADIR"],
            app=app,
        )
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
