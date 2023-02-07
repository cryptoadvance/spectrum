import os
from threading import Thread
from uuid import uuid4

import pytest
import requests
from flask import Flask, jsonify


class MockServer(Thread):
    """A Flask-Server which you can spinup in tests. It's running in a thread

    copied from https://gist.github.com/eruvanos/f6f62edb368a20aaa880e12976620db8
    """

    def __init__(self, app, port=8081):
        super().__init__()
        self.port = port
        self.app = app
        self.url = "http://localhost:%s" % self.port

        self.app.add_url_rule("/shutdown", view_func=self._shutdown_server)

    def _shutdown_server(self):
        from flask import request

        if not "werkzeug.server.shutdown" in request.environ:
            raise RuntimeError("Not running the development server")
        request.environ["werkzeug.server.shutdown"]()
        return "Server shutting down..."

    def shutdown_server(self):
        requests.get("http://localhost:%s/shutdown" % self.port)
        self.join()

    def add_callback_response(self, url, callback, methods=("GET",)):
        callback.__name__ = str(
            uuid4()
        )  # change name of method to mitigate flask exception
        self.app.add_url_rule(url, view_func=callback, methods=methods)

    def add_json_response(self, url, serializable, methods=("GET",)):
        def callback():
            return jsonify(serializable)

        self.add_callback_response(url, callback, methods=methods)

    def run(self):
        self.app.run(port=self.port)
