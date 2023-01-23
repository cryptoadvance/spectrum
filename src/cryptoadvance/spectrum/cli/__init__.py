import logging
import os
import sys
import time
from logging.config import dictConfig

import click

from .cli_server import server


@click.group()
@click.option("--debug", is_flag=True, help="Show debug information on errors.")
def entry_point(debug):
    setup_logging(debug)


entry_point.add_command(server)


def setup_logging(debug=False):
    """central and early configuring of logging see
    https://flask.palletsprojects.com/en/1.1.x/logging/#basic-configuration
    However the dictConfig doesn't work, so let's do something similiar programatically
    """
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    logger = logging.getLogger("cryptoadvance")
    if debug:
        formatter = logging.Formatter("[%(levelname)7s] in %(module)15s: %(message)s")
        logger.setLevel(logging.DEBUG)
        # but not that chatty connectionpool
        logging.getLogger("urllib3.connectionpool").setLevel(logging.INFO)
        ch.setFormatter(formatter)
        logger.debug("RUNNING IN DEBUG MODE")
    else:
        formatter = logging.Formatter(
            # Too early to format that via the flask-config, so let's copy it from there:
            os.getenv(
                "SPECTERCM_LOGFORMAT",
                "[%(asctime)s] %(levelname)s in %(module)s: %(message)s",
            )
        )
        logger.setLevel(logging.INFO)
    ch.setFormatter(formatter)

    for logger in [
        # app.logger,
        # logging.getLogger('sqlalchemy'),
    ]:
        logger.setLevel(logging.DEBUG)

    logging.getLogger().handlers = []
    logging.getLogger().addHandler(ch)
