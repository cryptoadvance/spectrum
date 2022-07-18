''' A config module contains static configuration '''
import logging
import os
from pathlib import Path
import datetime
import secrets

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

class BaseConfig(object):
    """Base configuration."""
    SECRET_KEY='development key'
    USERNAME='admin'
    HOST="127.0.0.1"
    PORT=8081

# Level 1: How does persistence work?
# Convention: BlaConfig

class LiteConfig(BaseConfig):
    DATADIR="data"
    DATABASE=os.path.abspath(os.path.join(DATADIR, "wallets.sqlite"))
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

class ProductionConfig(EmzyElectrumPostgresConfig):
    ''' Not sure whether we're production ready, though '''
    SECRET_KEY = os.getenv("SECRET_KEY", secrets.token_urlsafe(16))


