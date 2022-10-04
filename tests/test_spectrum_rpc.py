import json
import logging
from cryptoadvance.specterext.spectrum.spectrum import Spectrum

def test_root(caplog,client):
    caplog.set_level(logging.INFO)
    caplog.set_level(logging.DEBUG, logger="cryptoadvance.spectrum")
    result = client.get("/")
    
    assert result.status_code == 200
    assert result.get_data(as_text=True) == "JSONRPC server handles only POST requests"
    result = client.post("/",json={})
    assert result.status_code == 200
    assert json.loads(result.data)["error"]["message"] == "Method not found (None)"

def test_getmininginfo(caplog,client):
    caplog.set_level(logging.INFO)
    caplog.set_level(logging.DEBUG, logger="cryptoadvance.spectrum")
    result = client.post("/", json={"method":"getmininginfo"})
    assert result.status_code == 200
    data = json.loads(result.data)
    assert data["result"]["blocks"] == 0

# -----------------------------------
# test the same, but this time with a BridgeRPC

def test_getmininginfo_bridge(caplog, app):
    print(app.spectrum)
    request = {
                "method": "getmininginfo"
    }
    result = app.spectrum.jsonrpc(request)
    data = result # Skip the parsing and http-stuff
    assert data["result"]["blocks"] == 0