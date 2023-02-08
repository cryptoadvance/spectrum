import code
import json
import logging
import shutil
import signal
import sys
import tempfile
import traceback
from binascii import hexlify
import pytest

from cryptoadvance.spectrum.util_specter import setup_logging
from cryptoadvance.spectrum.cli import setup_logging
from cryptoadvance.spectrum.config import TestConfig
from cryptoadvance.spectrum.server import create_app, init_app
from embit import script
from embit.bip32 import NETWORKS, HDKey
from embit.bip39 import mnemonic_to_seed
from flask import Flask
from werkzeug.utils import import_string
from werkzeug.utils import ImportStringError

from fix_infrastructure import MockServer

logger = logging.getLogger(__name__)

pytest_plugins = [
    # "fix_infrastructure",
    "fix_keys_and_seeds_embit"
]

# This is from https://stackoverflow.com/questions/132058/showing-the-stack-trace-from-a-running-python-application
# it enables stopping a hanging test via sending the pytest-process a SIGUSR2 (12)
# kill 12 pid-of-pytest
# In the article they claim to open a debug-console which didn't work for me but at least
# you get a stacktrace in the output.
def debug(sig, frame):
    """Interrupt running process, and provide a python prompt for
    interactive debugging."""
    d = {"_frame": frame}  # Allow access to frame object.
    d.update(frame.f_globals)  # Unless shadowed by global
    d.update(frame.f_locals)

    i = code.InteractiveConsole(d)
    message = "Signal received : entering python shell.\nTraceback:\n"
    message += "".join(traceback.format_stack(frame))
    i.interact(message)


def listen():
    signal.signal(signal.SIGUSR2, debug)  # Register handler


def pytest_addoption(parser):
    """Internally called to add options to pytest
    see pytest_generate_tests(metafunc) on how to check that
    Also used to register the SIGUSR2 (12) as decribed in conftest.py
    """
    parser.addoption("--docker", action="store_true", help="run bitcoind in docker")
    parser.addoption(
        "--bitcoind-version",
        action="store",
        default="v0.20.1",
        help="Version of bitcoind (something which works with git checkout ...)",
    )
    parser.addoption(
        "--bitcoind-log-stdout",
        action="store",
        default=False,
        help="Whether bitcoind should log to stdout (default:False)",
    )
    parser.addoption(
        "--elementsd-version",
        action="store",
        default="master",
        help="Version of elementsd (something which works with git checkout ...)",
    )
    parser.addoption(
        "--config",
        action="store",
        default="cryptoadvance.spectrum.config.TestConfig",
        help="The config-class to use, usually cryptoadvance.spectrum.config.Testconfig ",
    )
    listen()


@pytest.fixture
def empty_data_folder():
    # Make sure that this folder never ever gets a reasonable non-testing use-case
    with tempfile.TemporaryDirectory(prefix="specter_home_tmp_") as data_folder:
        yield data_folder


def spectrum_app_with_config(config={}):
    """helper-function to create SpectrumFlasks"""
    setup_logging(debug=True)
    logger.info("Deleting ./data")
    shutil.rmtree("./data", ignore_errors=True)
    if isinstance(config, dict):
        tempClass = type("tempClass", (TestConfig,), {})
        for key, value in config.items():
            setattr(tempClass, key, value)
        # service_manager will expect the class to be defined as a direct property of the module:
        if hasattr(sys.modules[__name__], "tempClass"):
            delattr(sys.modules[__name__], "tempClass")
        assert not hasattr(sys.modules[__name__], "tempClass")
        setattr(sys.modules[__name__], "tempClass", tempClass)
        assert hasattr(sys.modules[__name__], "tempClass")
        assert getattr(sys.modules[__name__], "tempClass") == tempClass
        config = tempClass
    app = create_app(config=config)
    try:
        shutil.rmtree(app.config["SPECTRUM_DATADIR"], ignore_errors=False)
    except FileNotFoundError:
        pass
    with app.app_context():
        app.config["TESTING"] = True
        app.testing = True
        init_app(app, standalone=True)
        return app


@pytest.fixture
def config(request):
    # Creates a class out of a fully qualified Class as string
    try:
        mytype = import_string(request.config.getoption("config"))
    except ImportStringError as e:
        raise Exception(
            """
            Module not found. Try:
            --config cryptoadvance.spectrum.config.TestConfig (default) or
            --config cryptoadvance.spectrum.config.EmzyElectrumLiteConfig
        """
        )
        raise e
    return mytype


@pytest.fixture
def app() -> Flask:
    """the Flask-App, but uninitialized"""
    return spectrum_app_with_config(config="cryptoadvance.spectrum.config.TestConfig")


@pytest.fixture
def app_offline() -> Flask:
    """provoke an offline spectrum by passing a closed port"""
    return spectrum_app_with_config(
        config={
            "ELECTRUM_PORT": "localhost",
            "ELECTRUM_PORT": 30011,
            "ELECTRUM_USES_SSL": False,
        }
    )


@pytest.fixture
def app_nigiri() -> Flask:
    """the Flask-App, but uninitialized"""
    server = MockServer(
        spectrum_app_with_config(config="cryptoadvance.spectrum.config.TestConfig")
    )
    server.start()
    yield server
    server.shutdown_server()


@pytest.fixture
def client(app):
    """a test_client from an initialized Flask-App"""
    return app.test_client()


@pytest.fixture
def spectrum_node():
    """A Spectrum node"""
    node_dict = {
        "python_class": "cryptoadvance.specterext.spectrum.spectrum_node.SpectrumNode",
        "name": "Spectrum Node",
        "alias": "spectrum_node",
        "host": "electrum.emzy.de",
        "port": 5002,
        "ssl": True,
    }

    # Instantiate via PersistentObject:
    sn = PersistentObject.from_json(node_dict)
    assert type(sn) == SpectrumNode
    return sn
