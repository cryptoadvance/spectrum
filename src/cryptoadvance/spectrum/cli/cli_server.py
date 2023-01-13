import logging
import os
from ..server import create_app, init_app
import click

logger = logging.getLogger(__name__)


@click.group()
def cli():
    pass


@cli.command()
@click.option("--port", default="5000")
# set to 0.0.0.0 to make it available outside
@click.option("--host", default="127.0.0.1")
# for https:
@click.option("--cert")
@click.option("--key")
@click.option(
    "--config",
    default="cryptoadvance.spectrum.config.LocalElectrumConfig",
    help="A class which sets reasonable default values.",
)
def server(port, host, cert, key, config):
    # a hack as the pass_context is broken for some reason
    # we determine debug from what is set in the entry_point via the debug-level.
    debug = logger.isEnabledFor(logging.DEBUG)
    logger.info(f"DEBUG is {debug}")

    app = create_app(config)
    init_app(app)
    logger.info("Starting up ...")
    app.run(debug=debug, port=app.config["PORT"], host=host)
