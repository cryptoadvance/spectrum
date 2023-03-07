import json
import time
import logging
from cryptoadvance.spectrum.spectrum import Spectrum

logger = logging.getLogger(__name__)


def test_root(caplog, client):
    caplog.set_level(logging.INFO)
    caplog.set_level(logging.DEBUG, logger="cryptoadvance.spectrum")
    result = client.get("/")
    assert result.status_code == 200
    assert result.data == b"JSONRPC server handles only POST requests"
    result = client.post("/", json={})
    assert result.status_code == 200
    assert json.loads(result.data)["error"]["message"] == "Method not found (None)"


def test_unknownmethod(caplog, client):
    caplog.set_level(logging.INFO)
    caplog.set_level(logging.DEBUG, logger="cryptoadvance.spectrum")
    result = client.post("/", json={"method": "unknownmethod"})
    assert result.status_code == 200


def test_getmininginfo(caplog, client):
    caplog.set_level(logging.INFO)
    caplog.set_level(logging.DEBUG, logger="cryptoadvance.spectrum")
    result = client.post("/", json={"method": "getmininginfo"})
    assert result.status_code == 200
    assert json.loads(result.data)["result"]["blocks"] >= 0


def test_getblockchaininfo(caplog, client):
    caplog.set_level(logging.INFO)
    caplog.set_level(logging.DEBUG, logger="cryptoadvance.spectrum")
    result = client.post("/", json={"method": "getblockchaininfo"})
    assert result.status_code == 200
    print(json.loads(result.data))
    assert json.loads(result.data)["result"]["blocks"] >= 0


def test_getnetworkinfo(caplog, client):
    caplog.set_level(logging.INFO)
    caplog.set_level(logging.DEBUG, logger="cryptoadvance.spectrum")
    result = client.post("/", json={"method": "getnetworkinfo"})
    assert result.status_code == 200
    print(json.loads(result.data))
    assert json.loads(result.data)["result"]["version"] == 230000


def test_getmempoolinfo(caplog, client):
    caplog.set_level(logging.INFO)
    caplog.set_level(logging.DEBUG, logger="cryptoadvance.spectrum")
    result = client.post("/", json={"method": "getmempoolinfo"})
    assert result.status_code == 200
    print(json.loads(result.data))
    assert json.loads(result.data)["result"]["loaded"]


def test_uptime(caplog, client):
    caplog.set_level(logging.INFO)
    caplog.set_level(logging.DEBUG, logger="cryptoadvance.spectrum")
    result = client.post("/", json={"method": "uptime"})
    assert result.status_code == 200
    print(json.loads(result.data))
    assert json.loads(result.data)["result"] >= 0


def test_getblockhash(caplog, client):
    caplog.set_level(logging.DEBUG)
    caplog.set_level(logging.DEBUG, logger="cryptoadvance.spectrum")

    result = client.post(
        "/",
        json={
            "method": "getblockhash",
            "params": [0],
            "jsonrpc": "2.0",
            "id": 0,
        },
    )

    assert result.status_code == 200
    print(json.loads(result.data))

    # assert json.loads(result.data)["result"] == '0f9188f13cb7b2c71f2a335e3a4fc328bf5beb436012afca590b1a11466e2206' # Hash of hard coded regtest genesis block


def test_rescanblockchain(caplog, client):
    caplog.set_level(logging.DEBUG)
    caplog.set_level(logging.DEBUG, logger="cryptoadvance.spectrum")

    result = client.post(
        "/",
        json={
            "method": "createwallet",
            "params": ["name_of_wallet"],
            "jsonrpc": "2.0",
            "id": 0,
        },
    )
    assert result.status == "200 OK"

    result = client.post(
        "/wallet/name_of_wallet",
        json={
            "method": "rescanblockchain",
            "params": [0],
            "jsonrpc": "2.0",
            "id": 0,
        },
    )

    assert result.status_code == 200
    print(json.loads(result.data))


def test_createwallet(caplog, client):
    caplog.set_level(logging.DEBUG)
    caplog.set_level(logging.DEBUG, logger="cryptoadvance.spectrum")

    result = client.post(
        "/wallet/some_shiny_new_wallet",
        json={
            "method": "createwallet",
            "params": ["some_shiny_new_wallet"],
            "jsonrpc": "2.0",
            "id": 0,
        },
    )
    print(json.loads(result.data))
    assert result.status_code == 200


def test_getreceivedbyaddress(caplog, client):
    caplog.set_level(logging.DEBUG)
    caplog.set_level(logging.DEBUG, logger="cryptoadvance.spectrum")

    result = client.post(
        "/wallet/some_nonexisting_wallet",
        json={
            "method": "getreceivedbyaddress",
            "params": ["bc1q09vm5lfy0j5reeulh4x5752q25uqqvz34hufdl", 6],
            "jsonrpc": "2.0",
            "id": 0,
        },
    )
    assert result.status_code == 200
    assert (
        json.loads(result.data)["error"]["message"]
        == "Requested wallet some_nonexisting_wallet does not exist or is not loaded"
    )
    result = client.post(
        "/",
        json={
            "method": "createwallet",
            "params": ["some_new_wallet_to_test_getreceivedbyaddress"],
            "jsonrpc": "2.0",
            "id": 0,
        },
    )

    result = client.post(
        "/wallet/some_new_wallet_to_test_getreceivedbyaddress",
        json={
            "method": "getreceivedbyaddress",
            "params": ["bc1qtr5cwxum3uwvyxgc8sgqm8gr658eksruyv3sty", 6],
            "jsonrpc": "2.0",
            "id": 0,
        },
    )
    assert result.status_code == 200
    print(json.loads(result.data))
    assert False
