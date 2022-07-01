import logging
from threading import Thread

from embit import hashes
from embit.script import address_to_scriptpubkey
from flask import current_app as app

logger = logging.getLogger(__name__)

def get_blockhash(hex_header):
    return hashes.double_sha256(bytes.fromhex(hex_header))[::-1].hex()


def scripthash(script):
    """Calculates a scripthash for Electrum from address"""
    return hashes.sha256(script.data)[::-1].hex()


def sat_to_btc(sat):
    sat = sat or 0  # if None is passed
    return round(sat * 1e-8, 8)


def btc_to_sat(btc):
    btc = btc or 0  # if None is passed
    return round(btc * 1e8)



def handle_exception(exception):
    ''' prints the exception and most important the stacktrace '''
    logger.error("----START-TRACEBACK-----------------------------------------------------------------")
    logger.exception(exception)    # the exception instance
    logger.error("----END---TRACEBACK-----------------------------------------------------------------")

class FlaskThread(Thread):
    ''' A FlaskThread passes the applicationcontext to the new thread in order to make stuff working seamlessly in new threadsS
        copied from https://stackoverflow.com/questions/39476889/use-flask-current-app-logger-inside-threading '''
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.app = app._get_current_object()
        self.daemon = True

    def run(self):
        logger.debug("New thread started"+str(self._target))
        logger.debug(self.app)
        with self.app.app_context():
            super().run()
