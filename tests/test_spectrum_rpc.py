import json
import time
import logging
from cryptoadvance.spectrum.spectrum import Spectrum

logger = logging.getLogger(__name__)

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
    assert json.loads(result.data)["result"]["blocks"] >= 0

def test_getblockchaininfo(caplog,client):
    caplog.set_level(logging.INFO)
    caplog.set_level(logging.DEBUG, logger="cryptoadvance.spectrum")
    result = client.post("/", json={"method":"getblockchaininfo"})
    assert result.status_code == 200
    print(json.loads(result.data))
    assert json.loads(result.data)["result"]["blocks"] >= 0

def test_getnetworkinfo(caplog,client):
    caplog.set_level(logging.INFO)
    caplog.set_level(logging.DEBUG, logger="cryptoadvance.spectrum")
    result = client.post("/", json={"method":"getnetworkinfo"})
    assert result.status_code == 200
    print(json.loads(result.data))
    assert json.loads(result.data)["result"]["version"] == 230000

def test_getmempoolinfo(caplog,client):
    caplog.set_level(logging.INFO)
    caplog.set_level(logging.DEBUG, logger="cryptoadvance.spectrum")
    result = client.post("/", json={"method":"getmempoolinfo"})
    assert result.status_code == 200
    print(json.loads(result.data))
    assert json.loads(result.data)["result"]["loaded"]

def test_uptime(caplog,client):
    caplog.set_level(logging.INFO)
    caplog.set_level(logging.DEBUG, logger="cryptoadvance.spectrum")
    result = client.post("/", json={"method":"uptime"})
    assert result.status_code == 200
    print(json.loads(result.data))
    assert json.loads(result.data)["result"] >= 0

def test_getblockhash(caplog, client):
    caplog.set_level(logging.DEBUG)
    caplog.set_level(logging.DEBUG, logger="cryptoadvance.spectrum")
    
    result = client.post("/", json={
        "method":"getblockhash",
        "params": [0],
        "jsonrpc": "2.0",
        "id": 0,
    })
    
    assert result.status_code == 200
    print(json.loads(result.data))
    
    assert len(json.loads(result.data)["result"]) == 64