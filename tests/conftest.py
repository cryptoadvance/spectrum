import os
import shutil
from flask import Flask
import tempfile
import pytest
from cryptoadvance.specterext.spectrum.config import TestConfig
from cryptoadvance.specterext.spectrum.server import create_app, init_app
import sys

@pytest.fixture
def empty_data_folder():
    # Make sure that this folder never ever gets a reasonable non-testing use-case
    with tempfile.TemporaryDirectory(prefix="specter_home_tmp_") as data_folder:
        yield data_folder

def spectrum_app_with_config(config={}, specter=None):
    """helper-function to create SpectrumFlasks"""
    
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
        shutil.rmtree(app.config["DATADIR"], ignore_errors=False)
    except FileNotFoundError:
        pass
    with app.app_context():
        app.config["TESTING"] = True
        app.testing = True
        init_app(app, standalone=True)
        return app

@pytest.fixture
def app() -> Flask:
    """the Flask-App, but uninitialized"""
    return spectrum_app_with_config(config="cryptoadvance.specterext.spectrum.config.TestConfig")

@pytest.fixture
def client(app):
    """a test_client from an initialized Flask-App"""
    return app.test_client()