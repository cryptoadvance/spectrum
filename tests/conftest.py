from flask import Flask
import pytest
from cryptoadvance.specterext.spectrum.config import TestConfig
from cryptoadvance.specterext.spectrum.server import create_app
import sys

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
    with app.app_context():
        app.config["TESTING"] = True
        app.testing = True
        #init_app(app, specter=specter)
        return app

@pytest.fixture
def app() -> Flask:
    """the Flask-App, but uninitialized"""
    return spectrum_app_with_config(config="cryptoadvance.spectrum.config.TestConfig")

@pytest.fixture
def client(app):
    """a test_client from an initialized Flask-App"""
    return app.test_client()