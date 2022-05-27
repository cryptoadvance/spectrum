from flask import Flask, request, g
from .db import db
from .spectrum import Spectrum

import json
import os


def create_app(config):
    app = Flask(__name__)

    # create folder if doesn't exist
    if not os.path.exists(config["datadir"]):
        os.makedirs(config["datadir"])

    app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{config['database']}"

    # 32 bytes generated from us.random
    # TODO: generate at start
    app.config["SECRET_KEY"] = "feoj49j(*$I$NGO4f380jfkosf024m8ODFKv"
    db.init_app(app)

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

    # create database if doesn't exist
    if not os.path.exists(config["database"]):
        with app.app_context():
            db.create_all()

    with app.app_context():
        # if not getattr(g, "electrum", None):
        app.spectrum = Spectrum(
            config["electrum"]["host"],
            config["electrum"]["port"],
            datadir=config["datadir"],
        )

    return app


def main():
    config = {
        "datadir": "data",
        "database": os.path.abspath(os.path.join("data", "wallets.sqlite")),
        "host": "127.0.0.1",
        "port": 8081,
        "debug": True,
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
