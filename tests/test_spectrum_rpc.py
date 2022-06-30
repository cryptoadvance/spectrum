import json
import logging
from cryptoadvance.spectrum.spectrum import Spectrum

def test_root(caplog,client):
    caplog.set_level(logging.INFO)
    caplog.set_level(logging.DEBUG, logger="cryptoadvance.spectrum")
    result = client.get("/")
    assert result.status_code == 200
    assert result.data == b"JSONRPC server handles only POST requests"
    result = client.post("/",json={})
    assert result.status_code == 200
    assert json.loads(result.data)["error"]["message"] == "Method not found (None)"

def test_getmininginfo(caplog,client):
    caplog.set_level(logging.INFO)
    caplog.set_level(logging.DEBUG, logger="cryptoadvance.spectrum")
    result = client.post("/", json={"method":"getmininginfo"})
    assert result.status_code == 200
    assert json.loads(result.data)["result"]["blocks"] == 0