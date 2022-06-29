from cryptoadvance.specterext.spectrum.electrum.network import pick_random_server, parse_server_list
from cryptoadvance.specterext.spectrum.elsock import ElectrumSocket


def test_parse_server_list():
    
    for server, out in parse_server_list().items():
        assert server
        assert out.get("t") or out.get("s")


def test_pick_random_server():

    server = pick_random_server().split(":")
    assert server[0] # This is the servername
    assert int(server[1]) # this is the port
    assert server[2] == "t" or server[2] == "s" # s is ssl-encrypted
    print(f"connecting to: {server}")
    elsock = ElectrumSocket(host=server[0], port=int(server[1]), use_ssl=server[2] == "s")

    res = elsock.call("blockchain.headers.subscribe")
    print(res)
    del elsock
    assert False

def test_emzy():
    elsock = ElectrumSocket(host="electrum.emzy.de", port=5002, use_ssl=True)
    print("created elsock!")
    res = elsock.ping()
    
    print(res)
    del elsock
    assert False


