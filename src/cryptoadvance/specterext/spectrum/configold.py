"""
Here Configuration of your Extension (and maybe your Application) takes place
"""
import os
from cryptoadvance.specter.config import ProductionConfig as SpecterProductionConfig


class BaseConfig:
    ''' This is a extension-based Config which is used as Base '''
    SPECTRUM_SOMEKEY = "some value"

class ProductionConfig(BaseConfig):
    ''' This is a extension-based Config for Production '''
    pass


class AppProductionConfig(SpecterProductionConfig):
    ''' The AppProductionConfig class can be used to user this extension as application
    '''
    # Where should the User endup if he hits the root of that domain?
    ROOT_URL_REDIRECT = "/spc/ext/spectrum"
    # I guess this is the only extension which should be available?
    EXTENSION_LIST = [
        "cryptoadvance.specterext.spectrum.service"
    ]
    # You probably also want a different folder here
    SPECTER_DATA_FOLDER=os.path.expanduser("~/.spectrum")