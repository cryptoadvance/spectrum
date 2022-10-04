import datetime
import errno
import json
import logging
import os
import sys

import requests
import urllib3

from cryptoadvance.specter.helpers import is_ip_private
from cryptoadvance.specter.specter_error import SpecterError, handle_exception
from cryptoadvance.specter.rpc import BitcoinRPC

from cryptoadvance.specterext.spectrum.spectrum import RPCError, Spectrum

logger = logging.getLogger(__name__)

# TODO: redefine __dir__ and help

class BridgeRPC(BitcoinRPC):
    ''' A class which behaves like a BitcoinRPC but internally bridges to Spectrum.jsonrpc '''

    def __init__(
        self,
        spectrum,
        wallet_name=None
    ):
        self.spectrum: Spectrum = spectrum
        self.wallet_name = wallet_name

    def wallet(self, name=""):
        return type(self)(
            self.spectrum,
            wallet_name=name,
        )

    def clone(self):
        """
        Returns a clone of self.
        Useful if you want to mess with the properties
        """
        return self.__class__(
            self,
            self.spectrum,
            wallet=self.wallet
        )

    def multi(self, calls: list, **kwargs):
        """Makes batch request to Core"""
        type(self).counter += len(calls)
        # some debug info for optimizations
        # methods = " ".join(list(dict.fromkeys([call[0] for call in calls])))
        # wallet = self.path.split("/")[-1]
        # print(f"{self.counter}: +{len(calls)} {wallet} {methods}")
        headers = {"content-type": "application/json"}
        payload = [
            {
                "method": method,
                "params": args if args != [None] else [],
                "jsonrpc": "2.0",
                "id": i,
            }
            for i, (method, *args) in enumerate(calls)
        ]
        timeout = self.timeout
        if "timeout" in kwargs:
            timeout = kwargs["timeout"]

        if kwargs.get("no_wait"):
            # Zero is treated like None, i.e. infinite wait
            timeout = 0.001

        url = self.url
        if "wallet" in kwargs:
            url = url + "/wallet/{}".format(kwargs["wallet"])
        return [ self.spectrum.jsonrpc(item,wallet_name=self.wallet_name) for item in payload ]



    def __getattr__(self, method):
        def fn(*args, **kwargs):
            r = self.multi([(method, *args)], **kwargs)[0]
            if r["error"] is not None:
                raise RPCError(
                    f"Request error for method {method}: {r['error']['message']}", r
                )
            return r["result"]

        return fn

    def __repr__(self) -> str:
        return f"<BitcoinRpc {self.url}>"
