""" Contains stuff which is copy and pasted from specter
    in order to avoid dependency issues which are already severe enough.
"""
import logging
import os
from http.client import HTTPConnection


def snake_case2camelcase(word):
    return "".join(x.capitalize() or "_" for x in word.split("_"))


def setup_logging(debug=False, tracerpc=False, tracerequests=False):
    """This code sets up logging for a Python application. It sets the logging level to DEBUG if the tracerpc
    or tracerequests flags are set, and INFO otherwise. It also sets up the formatter for the log messages,
    which can be customized with an environment variable. Finally, it adds a StreamHandler to the root
    logger and removes any existing handlers.
    """
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    if tracerpc or tracerequests:
        if tracerpc:
            debug = True  # otherwise this won't work
            logging.getLogger("cryptoadvance.specter.rpc").setLevel(logging.DEBUG)
        if tracerequests:
            # from here: https://stackoverflow.com/questions/16337511/log-all-requests-from-the-python-requests-module
            HTTPConnection.debuglevel = 1
            requests_log = logging.getLogger("requests.packages.urllib3")
            requests_log.setLevel(logging.DEBUG)
            requests_log.propagate = True
    else:
        logging.getLogger("cryptoadvance.specter.rpc").setLevel(logging.INFO)

    if debug:
        # No need for timestamps while developing
        formatter = logging.Formatter("[%(levelname)7s] in %(module)15s: %(message)s")
        logging.getLogger("cryptoadvance").setLevel(logging.DEBUG)
        # but not that chatty connectionpool
        logging.getLogger("urllib3.connectionpool").setLevel(logging.INFO)
    else:
        formatter = logging.Formatter(
            # Too early to format that via the flask-config, so let's copy it from there:
            os.getenv(
                "SPECTER_LOGFORMAT",
                "[%(asctime)s] %(levelname)s in %(module)s: %(message)s",
            )
        )
        logging.getLogger("cryptoadvance").setLevel(logging.INFO)
    ch.setFormatter(formatter)
    logging.getLogger().handlers = []
    logging.getLogger().addHandler(ch)


def _get_bool_env_var(varname, default=None):

    value = os.environ.get(varname, default)

    if value is None:
        return False
    elif isinstance(value, str) and value.lower() == "false":
        return False
    elif bool(value) is False:
        return False
    else:
        return bool(value)
