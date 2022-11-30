from cryptoadvance.spectrum.config import _get_bool_env_var
import os

def test_config_settings(app):
    assert app.config["ELECTRUM_HOST"] == "127.0.0.1"
    assert app.config["ELECTRUM_PORT"] == 50000
    assert app.config["ELECTRUM_USES_SSL"] == False # Nigiri doesn't use SSL

def test_get_bool_env_var():
    os.environ["bla"] = "false"
    assert not _get_bool_env_var("bla")
    os.environ["bla"] = "FaLse"
    assert not _get_bool_env_var("bla")
    os.environ["bla"] = "True"
    assert _get_bool_env_var("bla") 
    os.environ["bla"] = "true"
    assert _get_bool_env_var("bla") 
    os.environ["bla"] = "TrUe"
    assert _get_bool_env_var("bla") 
    os.environ["bla"] = "yes"
    assert _get_bool_env_var("bla") 
    os.environ["bla"] = "yEs"
    assert _get_bool_env_var("bla")
