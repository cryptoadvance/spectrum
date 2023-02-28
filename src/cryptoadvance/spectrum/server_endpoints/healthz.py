import json, logging

from flask import Blueprint, request

from flask import current_app as app

logger = logging.getLogger(__name__)

healthz = Blueprint("healthz", __name__)


@healthz.route("/healthz/liveness")
def liveness():
    return {"message": "i am alive"}


@healthz.route("/healthz/readyness")
def readyness():
    try:
        # Probably improvable:
        logger.info("ready?")
        assert app.spectrum.is_connected()
    except Exception as e:
        logger.info("no!")
        return {"message": "i am not ready"}, 500
    return {"message": "i am ready"}
