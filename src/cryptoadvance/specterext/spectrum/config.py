''' A config module contains static configuration '''
import logging
import os
from pathlib import Path
import datetime
import secrets
from flask import current_app as app

try:
    # Python 2.7
    import ConfigParser as configparser
except ImportError:
    # Python 3
    import configparser

# BASEDIR = os.path.abspath(os.path.dirname(__file__))

logger = logging.getLogger(__name__)

def _get_bool_env_var(varname, default=None):
    value = os.environ.get(varname, default)
    if value is None:
        return False
    elif isinstance(value, str) and value.strip().lower() == 'false':
        return False
    elif bool(value) is False:
        return False
    else:
        return bool(value)

class StandaloneConfig:
    HOST="127.0.0.1"
    PORT=8081
    SECRET_KEY='development key'
class BaseConfig(object):
    """Base configuration."""
    USERNAME='admin'
    DATADIR="data" # used for sqlite but also for txs-cache

# Level 1: How does persistence work?
# Convention: BlaConfig

class LiteConfig(BaseConfig):
    # The Folder to store the DB into is chosen here NOT to be spectrum-extension specific.
    # We're using Flask-Sqlalchemy and so we can only use one DB per App so we assume that
    # the DB is shared between different Extensions.
    # Instead, the tables are all prefixed with "spectrum_"
    # ToDo: separate the other stuff /txs) in a separate directory
    DATADIR=os.path.join(app.config["SPECTER_DATA_FOLDER"], "sqlite")
    DATABASE=os.path.abspath(os.path.join(DATADIR, "db.sqlite"))
    SQLALCHEMY_DATABASE_URI = 'sqlite:///' + DATABASE
    SQLALCHEMY_TRACK_MODIFICATIONS=False

class PostgresConfig(BaseConfig):
    """Development configuration with Postgres."""
    DEBUG = True
    DB_USERNAME = os.environ.get('DB_USER', default='spectrum')
    DB_PASSWORD = os.environ.get('DB_PASSWORD')
    DB_HOST = os.environ.get('DB_HOST', default='127.0.0.1') # will be overridden in docker-compose, but good for dev
    DB_PORT = os.environ.get('DB_PORT', default='5432')
    DB_DATABASE = os.environ.get('DB_DATABASE', default='spectrum')
    SQL_ALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_DATABASE_URI = f'postgresql+psycopg2://{DB_HOST}:{DB_PORT}/{DB_DATABASE}?user={DB_USERNAME}&password={DB_PASSWORD}' # &ssl=true

# Level 2: Where do we get an electrum from ?
# Convention: Prefix a level 1 config with the electrum solution
class NigiriLocalElectrumLiteConfig(LiteConfig):
    ELECTRUM_HOST="127.0.0.1"
    ELECTRUM_PORT=50000
    ELECTRUM_USES_SSL=_get_bool_env_var('ELECTRUM_USES_SSL', default="false")

class EmzyElectrumLiteConfig(LiteConfig):
    ELECTRUM_HOST=os.environ.get('ELECTRUM_HOST', default='electrum.emzy.de')
    ELECTRUM_PORT=int(os.environ.get('ELECTRUM_PORT', default='50002'))
    ELECTRUM_USES_SSL=_get_bool_env_var('ELECTRUM_USES_SSL', default="true")

class EmzyElectrumPostgresConfig(PostgresConfig):
    ELECTRUM_HOST=os.environ.get('ELECTRUM_HOST', default='electrum.emzy.de')
    ELECTRUM_PORT=int(os.environ.get('ELECTRUM_PORT', default='50002'))
    ELECTRUM_USES_SSL=_get_bool_env_var('ELECTRUM_USES_SSL', default="true")

# Level 2: Back to the problem-Space.
# Convention: ProblemConfig where problem is usually one of Test/Production or so

class TestConfig(NigiriLocalElectrumLiteConfig):
    pass

class DevelopmentConfig(EmzyElectrumLiteConfig):
    pass

class ProductionConfig(EmzyElectrumLiteConfig):
    ''' Not sure whether we're production ready, though '''
    pass