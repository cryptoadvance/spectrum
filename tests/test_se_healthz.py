import logging

def test_readyness(caplog, client):
    """The root of the app"""
    caplog.set_level(logging.INFO)
    caplog.set_level(logging.DEBUG, logger="cryptoadvance.specter")
    result = client.get("/healthz/readyness")
    # By default there is no authentication
    assert result.status_code == 200
    result = client.get("/welcome/about")