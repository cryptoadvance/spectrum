import logging

def test_readyness(caplog, client):
    """The root of the app"""
    caplog.set_level(logging.DEBUG)
    caplog.set_level(logging.DEBUG, logger="cryptoadvance.specter")
    result = client.get("/healthz/liveness")
    assert result.status_code == 200
    result = client.get("/welcome/about")
    
    result = client.get("/healthz/readyness")
    assert result.status_code == 200
    result = client.get("/welcome/about")

def test_readyness(caplog, app_offline):
    """The root of the app"""
    client = app_offline.test_client()
    caplog.set_level(logging.DEBUG)
    caplog.set_level(logging.DEBUG, logger="cryptoadvance.specter")
    result = client.get("/healthz/liveness")
    assert result.status_code == 200
    
    result = client.get("/healthz/readyness")
    assert result.status_code == 500
    