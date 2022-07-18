import os
from threading import Thread
from uuid import uuid4

import pytest
import requests
from cryptoadvance.specter.process_controller.bitcoind_controller import \
    BitcoindPlainController
from cryptoadvance.specter.util.common import str2bool
from flask import Flask, jsonify


def instantiate_bitcoind_controller(
    request, rpcport=18543, extra_args=[]
) -> BitcoindPlainController:
    # logging.getLogger().setLevel(logging.DEBUG)
    requested_version = request.config.getoption("--bitcoind-version")
    log_stdout = str2bool(request.config.getoption("--bitcoind-log-stdout"))
    if os.path.isfile("tests/bitcoin/src/bitcoind"):
        bitcoind_controller = BitcoindPlainController(
            bitcoind_path="tests/bitcoin/src/bitcoind", rpcport=rpcport
        )  # always prefer the self-compiled bitcoind if existing
    elif os.path.isfile("tests/bitcoin/bin/bitcoind"):
        bitcoind_controller = BitcoindPlainController(
            bitcoind_path="tests/bitcoin/bin/bitcoind", rpcport=rpcport
        )  # next take the self-installed binary if existing
    else:
        bitcoind_controller = BitcoindPlainController(
            rpcport=rpcport
        )  # Alternatively take the one on the path for now
    bitcoind_controller.start_bitcoind(
        cleanup_at_exit=True,
        cleanup_hard=True,
        extra_args=extra_args,
        log_stdout=log_stdout,
    )
    assert not bitcoind_controller.datadir is None
    running_version = bitcoind_controller.version()
    requested_version = request.config.getoption("--bitcoind-version")
    assert running_version == requested_version, (
        "Please make sure that the Bitcoind-version (%s) matches with the version in pytest.ini (%s)"
        % (running_version, requested_version)
    )
    return bitcoind_controller

@pytest.fixture(scope="session")
def bitcoin_regtest(request):
    bitcoind_regtest = instantiate_bitcoind_controller(request, extra_args=None)
    try:
        assert bitcoind_regtest.get_rpc().test_connection()
        assert not bitcoind_regtest.datadir is None
        yield bitcoind_regtest
    finally:
        bitcoind_regtest.stop_bitcoind()

class MockServer(Thread):
    ''' A Flask-Server which you can spinup in tests. It's running in a thread
    
        copied from https://gist.github.com/eruvanos/f6f62edb368a20aaa880e12976620db8
    '''
    def __init__(self, app, port=8081):
        super().__init__()
        self.port = port
        self.app = app
        self.url = "http://localhost:%s" % self.port

        self.app.add_url_rule("/shutdown", view_func=self._shutdown_server)

    def _shutdown_server(self):
        from flask import request
        if not 'werkzeug.server.shutdown' in request.environ:
            raise RuntimeError('Not running the development server')
        request.environ['werkzeug.server.shutdown']()
        return 'Server shutting down...'

    def shutdown_server(self):
        requests.get("http://localhost:%s/shutdown" % self.port)
        self.join()

    def add_callback_response(self, url, callback, methods=('GET',)):
        callback.__name__ = str(uuid4())  # change name of method to mitigate flask exception
        self.app.add_url_rule(url, view_func=callback, methods=methods)

    def add_json_response(self, url, serializable, methods=('GET',)):
        def callback():
            return jsonify(serializable)
        
        self.add_callback_response(url, callback, methods=methods)

    def run(self):
        self.app.run(port=self.port)
