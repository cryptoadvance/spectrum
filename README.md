# Spectrum - Specter Desktop + Electrum

Note! Requires embit from master branch.

To run, assuming you have electrs listening on port 60401:
```
python3 -m cryptoadvance.spectrum
```

Then connect Specter-Desktop to rpc port 8081 with any credentials

## TODO:

- properly process notifications with multiple scripts
- psbt functionality
- refill keypool when address is used

- load from `config.toml`, cli args and env vars
- reconnect with electrum on disconnect
- add support for credentials / cookie file for RPC calls
