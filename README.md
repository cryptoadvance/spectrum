# Spectrum - Specter Desktop + Electrum

This is a electrum-adapter. It exposes a Bitcoin-Core style API while using an electron API in the backend. It might be useful in specific usecases, e.g. having better performance when connecting to a electrum-server via Tor. In order to do that, it needs a Database. Quite easily you can use a kind of builtin SQLite. Depending on your usecase, you might want to use an external DB.

Note! Requires embit from master branch. (Still true?!)
## Modes of usage

This can be used either in standalone mode or as a specter-extension. The second option is probably the main use-case.

## Standalone

Get this to work with something like that:
```
python3 --version # Make sure you have at least 3.8. Might also work with lower versions though
virtualenv --python=python3 .env
. ./.env/bin/activate
pip3 install -e .

# If you have a electrum server running on localhost:
python3 -m cryptoadvance.spectrum server --config cryptoadvance.spectrum.config.NigiriLocalElectrumLiteConfig

# If you want to run on mainnet and use emzy's Server
python3 -m cryptoadvance.spectrum server --config cryptoadvance.spectrum.config.EmzyElectrumLiteConfig

# Using Emzy's server but with a postgres
export DB_USERNAME=bla
export DB_PASSWORD=blub
python3 -m cryptoadvance.spectrum server --config cryptoadvance.spectrum.config.EmzyElectrumPostgresConfig
```

Check the `config.py` for the env-vars which need to be exported in order to connect to something different than localhost.

## Specter Extension

In order to get a development environment:
```
virtualenv --python=python3 .env
. ./.env/bin/activate
pip3 install -e .
pip3 install cryptoadvance.specter
python3 -m cryptoadvance.specter server --config DevelopmentConfig --debug
```


## TODO:

- refill keypool when address is used or new address is requested
- flask `debug=True` flag creates two electrum sockets that notify twice - this causes duplications in the database
- reconnect with electrum on disconnect
- add support for credentials / cookie file for RPC calls


## Development

Before your create a PR, make sure to [blackify](https://github.com/psf/black) all your changes. In order to automate that,
there is a git [pre-commit hook](https://ljvmiranda921.github.io/notebook/2018/06/21/precommits-using-black-and-flake8/) which you can simply install like this:
```
pre-commit install
```