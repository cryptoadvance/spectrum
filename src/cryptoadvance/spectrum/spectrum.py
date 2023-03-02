import json
import logging
import math
import os
from pydoc import describe
import random
from socket import socket
import threading
import time
import traceback
from functools import wraps
from datetime import datetime

from embit import bip32
from embit.descriptor import Descriptor as EmbitDescriptor
from embit.descriptor.checksum import add_checksum
from embit.finalizer import finalize_psbt
from embit.networks import NETWORKS
from embit.psbt import PSBT, DerivationPath
from embit.script import Script as EmbitScript
from embit.script import Witness
from embit.transaction import Transaction as EmbitTransaction
from embit.transaction import TransactionInput, TransactionOutput
from sqlalchemy.sql import func

from .db import UTXO, Descriptor, Script, Tx, TxCategory, Wallet, db
from .elsock import ElectrumSocket, ElSockTimeoutException
from .util import (
    FlaskThread,
    SpectrumException,
    btc_to_sat,
    get_blockhash,
    handle_exception,
    parse_blockheader,
    sat_to_btc,
    scripthash,
)

logger = logging.getLogger(__name__)

# a set of registered rpc calls that do not need a wallet
RPC_METHODS = set()
# wallet-specific rpc calls
WALLETRPC_METHODS = set()


def rpc(f):
    """A decorator that registers a generic rpc method"""
    method = f.__name__
    RPC_METHODS.add(method)

    @wraps(f)
    def wrapper(*args, **kwargs):
        return f(*args, **kwargs)

    return wrapper


def walletrpc(f):
    """A decorator that registers a wallet rpc method"""
    method = f.__name__
    WALLETRPC_METHODS.add(method)

    @wraps(f)
    def wrapper(*args, **kwargs):
        return f(*args, **kwargs)

    return wrapper


class RPCError(Exception):
    """Should use one of : https://github.com/bitcoin/bitcoin/blob/v22.0/src/rpc/protocol.h#L25-L88"""

    def __init__(self, message, code=-1):  # -1 is RPC_MISC_ERROR
        self.message = message
        self.code = code

    def to_dict(self):
        return {"code": self.code, "message": self.message}


# we detect chain by looking at the hash of the 0th block
ROOT_HASHES = {
    "000000000019d6689c085ae165831e934ff763ae46a2a6c172b3f1b60a8ce26f": "main",
    "000000000933ea01ad0ee984209779baaec3ced90fa3f408719526f8d77f4943": "test",
    "00000008819873e925422c1ff0f99f7cc9bbb232af63a077a480a3633bee1ef6": "signet",
    # anything else is regtest
}


class Spectrum:
    blocks = 0
    chain = "regtest"
    roothash = ""  # hash of the 0'th block
    bestblockhash = ""  # hash of the current best block

    def __init__(
        self,
        host="127.0.0.1",
        port=50001,
        ssl=True,
        datadir="data",
        app=None,
        proxy_url=None,
    ):
        self.app = app
        self.host = host
        self.port = port
        self.ssl = ssl
        self.proxy_url = proxy_url
        assert type(ssl) == bool, f"ssl is of type {type(ssl)}"
        self.datadir = datadir
        if not os.path.exists(self.txdir):
            logger.info(f"Creating txdir {self.txdir} ")
            os.makedirs(self.txdir)

        logger.info(f"Creating ElectrumSocket {host}:{port} (ssl={ssl})")
        self.sock = ElectrumSocket(
            host=host,
            port=port,
            callback=self.process_notification,
            socket_recreation_callback=self._sync,
            use_ssl=ssl,
            proxy_url=proxy_url,
        )

        # self.sock = ElectrumSocket(host="35.201.74.156", port=143, callback=self.process_notification)
        # 143 - Testnet, 110 - Mainnet, 195 - Liquid
        self.t0 = time.time()  # for uptime
        if self.sock and self.sock.status == "ok":
            logger.info(f"Pinged electrum in {self.sock.ping()} ")
            logger.info("subscribe to block headers")
            res = self.sock.call("blockchain.headers.subscribe")
            self.blocks = res["height"]
            self.bestblockhash = get_blockhash(res["hex"])
            logger.info("detect chain from header")
            rootheader = self.sock.call("blockchain.block.header", [0])
            logger.info(f"Set roothash {self.roothash}")
            self.roothash = get_blockhash(rootheader)
            self.chain = ROOT_HASHES.get(self.roothash, "regtest")

    def stop(self):
        logger.info("Stopping Spectrum")
        del self.sock

    def is_connected(self) -> bool:
        """Returns True if there is a socket connection, False otherwise."""
        return self.sock.status == "ok"

    @property
    def uses_tor(self):
        """Whether the underlying ElectrumSocket uses Tor"""
        return self.sock.uses_tor

    @property
    def txdir(self):
        return os.path.join(self.datadir, "txs")

    @property
    def progress_percent(self):
        """This reflects the sync-progress of the _sync-method. It'll be returned in the
        verificationprogress of getblockchaininfo
        """
        if hasattr(self, "_progress_percent"):
            return self._progress_percent
        else:
            return 0

    @progress_percent.setter
    def progress_percent(self, value):
        """Will be called from the sync-progress only"""
        self._progress_percent = int(value)

    def _sync(self):
        """This code is checking self.sock for properly working (otherwise offline-mode)
        and if it is, it subscribes to all scripts and checks if the state of the
        script matches the response from the subscription. If they don't match,
        it calls a sync_script function to update the state. It also logs progress
        every 100 scripts subscribed to and updates self.progress_percent
        """
        ts = 0
        try:
            if self.sock.status != "ok":
                logger.info("Syncprocess not starting, in offline-mode")
                return
            if hasattr(self, "_sync_in_progress") and self._sync_in_progress:
                logger.info("Syncprocess not starting, already running!")
                return
            self._sync_in_progress = True

            subscription_logging_counter = 0
            # subscribe to all scripts
            all_scripts = Script.query.all()
            all_scripts_len = len(all_scripts)
            logger.info(
                f"Syncprocess starting ({all_scripts_len} needs subscriptions)..."
            )
            ts = datetime.now()
            for sc in all_scripts:
                # ignore external scripts (labeled recepients)
                if sc.index is None:
                    continue
                subscription_logging_counter += 1
                if subscription_logging_counter % 100 == 0:
                    self.sync_speed = subscription_logging_counter / int(
                        (datetime.now() - ts).total_seconds()
                    )
                    self.progress_percent = int(
                        subscription_logging_counter / all_scripts_len * 100
                    )
                    logger.info(
                        f"Syncprocess now subscribed to {subscription_logging_counter} scripthashes ({self.progress_percent}%, {self.sync_speed} scripts/s)"
                    )

                try:
                    res = self.sock.call(
                        "blockchain.scripthash.subscribe", [sc.scripthash]
                    )
                except ElSockTimeoutException:
                    logger.error(
                        "Syncprocess got an ElSockTimeoutException. Stop Syncing!"
                    )
                    self.progress_percent = 0
                    return
                if res != sc.state:
                    self.sync_script(sc, res)
            self.progress_percent = 100
        except Exception as e:
            logger.exception(e)
        finally:
            self._sync_in_progress = False
            ts_diff_s = int((datetime.now() - ts).total_seconds())
            logger.info(
                f"Syncprocess finished syncing {all_scripts_len} scripts in {ts_diff_s} with {self.sync_speed} scripts/s)"
            )

    def sync(self, asyncc=True):
        if asyncc:
            # Using a FlaskThread means also by default that it's a daemon-thread. This has the advantage that
            # The thread is killed when the main-thread is killed but it does not do it in a tidy way.
            # Potentially harmfull for a LiteConfig but hopefully no problem for a PostgresConfig
            t = FlaskThread(
                target=self._sync,
            )
            t.start()
        else:
            self._sync()

    # ToDo: subcribe_scripts and sync is very similiar. One does it for all of the scripts in the DB,
    # the other one only for a specific descriptor. We should merge them!
    def subcribe_scripts(self, descriptor, asyncc=True):
        """Takes a descriptor and syncs all the scripts into the DB
        creates a new thread doing that.
        """
        if asyncc:
            t = FlaskThread(
                target=self._subcribe_scripts,
                args=[
                    descriptor.id,
                ],
            )
            t.start()
        else:
            self._subcribe_scripts(descriptor.id)

    def _subcribe_scripts(self, descriptor_id: int) -> None:
        descriptor: Descriptor = Descriptor.query.filter(
            Descriptor.id == descriptor_id
        ).first()
        logger.info(f"Starting sync/subscribe for {descriptor.descriptor[:30]}")
        # subscribe to all scripts in a thread to speed up creation of the wallet
        sc: Script
        relevant_scripts_query = Script.query.filter_by(descriptor=descriptor)
        relevant_scripts = relevant_scripts_query.all()
        relevant_scripts_count = relevant_scripts_query.count()

        count_scripts = 0
        count_syned_scripts = 0
        ts = datetime.now()
        for sc in relevant_scripts:
            # subscribing
            res = self.sock.call("blockchain.scripthash.subscribe", [sc.scripthash])
            count_scripts += 1

            # syncing
            if res != sc.state:
                self.sync_script(sc, res)
                count_syned_scripts += 1

            # logging and expose progress
            if count_scripts % 100 == 0:
                logger.info(
                    f"Now subscribed to {count_syned_scripts} of {relevant_scripts_count} scripthashes ({self.progress_percent}%) (via importdescriptor))"
                )
            self.progress_percent = int(
                count_syned_scripts / relevant_scripts_count * 100
            )

        self.progress_percent = 100
        ts_diff_s = int((datetime.now() - ts).total_seconds())
        logger.info(
            f"Finished Subscribing and syncing for descriptor {descriptor.descriptor[:30]} in {ts_diff_s}"
        )
        logger.info(
            f"A total of {len(relevant_scripts)} scripts got subscribed where {count_syned_scripts} got synced"
        )

    def sync_script(self, script, state=None):
        # Normally every script has 1-2 transactions and 0-1 utxos,
        # so even if we delete everything and resync it's ok
        # except donation addresses that may have many txs...
        logger.debug(
            f"Script {script.scripthash[:7]} is not synced {script.state} != {state}"
        )
        if script.state != None:
            logger.info(
                f"Script {script.scripthash[:7]} has an update from state {script.state} to {state}"
            )
        script_pubkey = script.script_pubkey
        internal = script.descriptor.internal
        # get all transactions, utxos and update balances
        # {height,tx_hash,tx_pos,value}
        utxos = self.sock.call("blockchain.scripthash.listunspent", [script.scripthash])
        # {confirmed,unconfirmed}
        balance = self.sock.call(
            "blockchain.scripthash.get_balance", [script.scripthash]
        )
        # {height,tx_hash}
        txs = self.sock.call("blockchain.scripthash.get_history", [script.scripthash])
        # dict with all txs in the database
        db_txs = {tx.txid: tx for tx in script.txs}
        # delete all txs that are not there any more:
        all_txids = {tx["tx_hash"] for tx in txs}
        for txid, tx in db_txs.items():
            if txid not in all_txids:
                db.session.delete(tx)
        for tx in txs:
            blockheader = self.sock.call("blockchain.block.header", [tx.get("height")])
            blockheader = parse_blockheader(blockheader)
            # update existing - set height
            tx_in_db = tx["tx_hash"] in db_txs
            try:
                tx_magic = self.sock.call(
                    "blockchain.transaction.get", [tx["tx_hash"], tx_in_db]
                )
            except ValueError as e:
                if str(e).startswith(
                    "verbose transactions are currently unsupported"
                ):  # electrs doesn't support it
                    tx_magic = self.sock.call(
                        "blockchain.transaction.get", [tx["tx_hash"], False]
                    )
                else:
                    raise e
            if tx_in_db:
                db_txs[tx["tx_hash"]].height = tx.get("height")
                db_txs[tx["tx_hash"]].blockhash = blockheader.get(
                    "blockhash"
                )  # not existing, how can we fix that?
                db_txs[tx["tx_hash"]].blocktime = blockheader.get(
                    "blocktime"
                )  # not existing, how can we fix that?
            # new tx
            else:

                tx_details = {
                    "tx_hash": tx_magic,
                    "blockhash": blockheader.get("blockhash"),
                    "blocktime": blockheader.get("blocktime"),
                }
                # dump to file
                fname = os.path.join(self.txdir, "%s.raw" % tx["tx_hash"])
                if not os.path.exists(fname):
                    with open(fname, "w") as f:
                        f.write(tx_magic)

                parsedTx = EmbitTransaction.from_string(tx_magic)
                replaceable = all([inp.sequence < 0xFFFFFFFE for inp in parsedTx.vin])

                category = TxCategory.RECEIVE
                amount = 0
                vout = 0
                if script_pubkey not in [out.script_pubkey for out in parsedTx.vout]:
                    category = TxCategory.SEND
                    amount = -sum([out.value for out in parsedTx.vout])
                else:
                    vout = [out.script_pubkey for out in parsedTx.vout].index(
                        script_pubkey
                    )
                    amount = parsedTx.vout[vout].value
                    if internal:  # receive to change is hidden in txlist
                        category = TxCategory.CHANGE

                t = Tx(
                    txid=tx["tx_hash"],
                    blockhash=tx_details.get("blockhash"),
                    height=tx.get("height"),
                    blocktime=tx_details.get("blocktime"),
                    replaceable=replaceable,
                    category=category,
                    vout=vout,
                    amount=amount,
                    fee=tx.get("fee", 0),
                    # refs
                    script=script,
                    wallet=script.wallet,
                )
                db.session.add(t)

        # dicts of all electrum utxos and all db utxos
        all_utxos = {(u["tx_hash"], u["tx_pos"]): u for u in utxos}
        db_utxos = {(u.txid, u.vout): u for u in script.utxos}
        # delete all utxos that are not in electrum utxos
        for k, utxo in db_utxos.items():
            # delete if spent
            if k not in all_utxos:
                db.session.delete(utxo)
        # add all utxos
        for k, utxo in all_utxos.items():
            # update existing
            if k in db_utxos:
                u = db_utxos[k]
                u.height = utxo.get("height")
                u.amount = utxo["value"]
            # add new
            else:
                u = UTXO(
                    txid=utxo["tx_hash"],
                    vout=utxo["tx_pos"],
                    height=utxo.get("height"),
                    amount=utxo["value"],
                    script=script,
                    wallet=script.wallet,
                )
                db.session.add(u)
        script.state = state
        script.confirmed = balance["confirmed"]
        script.unconfirmed = balance["unconfirmed"]
        db.session.commit()

    @property
    def network(self):
        return NETWORKS.get(self.chain, NETWORKS["main"])

    def process_notification(self, data):
        logger.info(f"process Notification: Electrum data {data}")
        method = data["method"]
        params = data["params"]
        if method == "blockchain.headers.subscribe":
            logger.info(params)
            self.blocks = params[0]["height"]
            self.bestblockhash = get_blockhash(params[0]["hex"])
        if method == "blockchain.scripthash.subscribe":
            scripthash = params[0]
            state = params[1]
            logger.info(f"electrum notification sh {scripthash} , state {state}")
            with self.app.app_context():
                scripts = Script.query.filter_by(scripthash=scripthash).all()
                for sc in scripts:
                    self.sync_script(sc, state)

    def get_wallet(self, wallet_name):
        w = Wallet.query.filter_by(name=wallet_name).first()
        if not w:
            raise RPCError(
                f"Requested wallet {wallet_name} does not exist or is not loaded", -18
            )
        return w

    def jsonrpc(self, obj, wallet_name=None, catch_exceptions=True):
        method = obj.get("method")
        id = obj.get("id", 0)
        params = obj.get("params", [])
        logger.debug(
            f"RPC called {method} {'wallet_name: ' + wallet_name if wallet_name else ''}"
        )
        try:
            args = None
            kwargs = None
            # get wallet by name
            wallet = self.get_wallet(wallet_name) if wallet_name is not None else None
            # unknown method
            if method not in RPC_METHODS and method not in WALLETRPC_METHODS:
                raise RPCError(f"Method not found ({method})", -32601)
            # wallet is not provided
            if method in WALLETRPC_METHODS and wallet is None:
                raise RPCError("Wallet file not specified", -19)
            m = getattr(self, f"{method}")
            if isinstance(params, list):
                args = params
                kwargs = {}
            else:
                args = []
                kwargs = params
            # for wallet-specific methods also pass wallet
            if method in WALLETRPC_METHODS:
                res = m(wallet, *args, **kwargs)
            else:
                res = m(*args, **kwargs)
        except RPCError as e:
            if not catch_exceptions:
                raise e
            logger.error(
                f"FAIL method: {method} wallet: {wallet_name} args: {args} kwargs: {kwargs} exc {e}"
            )
            return dict(result=None, error=e.to_dict(), id=id)
        except Exception as e:
            if not catch_exceptions:
                raise e
            logger.error(
                f"FAIL method: {method} wallet: {wallet_name} args: {args} kwargs: {kwargs} exc {e}"
            )
            handle_exception(e)
            return dict(result=None, error={"code": -500, "message": str(e)}, id=id)
        return dict(result=res, error=None, id=id)

    # ========= GENERIC RPC CALLS ========== #

    @rpc
    def getmininginfo(self):
        return {
            "blocks": self.blocks,
            "chain": self.chain,
            "difficulty": 0,  # we can potentially get it from the best header
            "networkhashps": 0,
            "warnings": "",
        }

    @rpc
    def getblockchaininfo(self):
        return {
            "chain": self.chain,
            "blocks": self.blocks,
            "headers": self.blocks,
            "bestblockhash": self.bestblockhash,
            "difficulty": 0,  # TODO: we can get it from block header if we need it
            "mediantime": int(
                time.time()
            ),  # TODO: we can get it from block header if we need it
            "verificationprogress": self.progress_percent / 100,
            "initialblockdownload": self.progress_percent != 100,
            "chainwork": "00",  # ???
            "size_on_disk": 0,
            "pruned": False,
            "softforks": {},
            "warnings": "",
        }

    @rpc
    def getnetworkinfo(self):
        """Dummy call, doing nothing"""
        return {
            "version": 230000,
            "subversion": "/Satoshi:0.23.0/",
            "protocolversion": 70016,
            "localservices": "0000000000000409",
            "localservicesnames": ["NETWORK", "WITNESS", "NETWORK_LIMITED"],
            "localrelay": True,
            "timeoffset": 0,
            "networkactive": True,
            "connections": 0,
            "connections_in": 0,
            "connections_out": 0,
            "networks": [
                {
                    "name": "ipv4",
                    "limited": False,
                    "reachable": True,
                    "proxy": "",
                    "proxy_randomize_credentials": False,
                },
                {
                    "name": "ipv6",
                    "limited": False,
                    "reachable": True,
                    "proxy": "",
                    "proxy_randomize_credentials": False,
                },
                {
                    "name": "onion",
                    "limited": True,
                    "reachable": False,
                    "proxy": "",
                    "proxy_randomize_credentials": False,
                },
            ],
            "relayfee": 0.00001000,
            "incrementalfee": 0.00001000,
            "localaddresses": [],
            "warnings": "",
        }

    @rpc
    def getmempoolinfo(self):
        """Dummy call, doing nothing"""
        return {
            "loaded": True,
            "size": 0,
            "bytes": 0,
            "usage": 64,
            "maxmempool": 300000000,
            "mempoolminfee": 0.00001000,
            "minrelaytxfee": 0.00001000,
            "unbroadcastcount": 0,
        }

    @rpc
    def uptime(self):
        return int(time.time() - self.t0)

    @rpc
    def getblockhash(self, height):
        if height == 0:
            return self.roothash
        if height == self.blocks:
            return self.bestblockhash
        if height < 0 or height > self.blocks:
            raise RPCError("Block height out of range", -8)
        logger.info(f"height: {height}")
        header = self.sock.call("blockchain.block.header", [height])
        return get_blockhash(header)

    @rpc
    def scantxoutset(self, action, scanobjects=[]):
        """Dummy call, doing nothing"""
        return None

    @rpc
    def getblockcount(self):
        return self.blocks

    @rpc
    def gettxoutsetinfo(
        self, hash_type="hash_serialized_2", hash_or_height=None, use_index=True
    ):
        """Dummy call, doing nothing"""
        return {
            "height": self.blocks,
            "bestblock": self.bestblockhash,
            "transactions": 0,
            "txouts": 0,
            "bogosize": 0,
            "hash_serialized_2": "",
            "disk_size": 0,
            "total_amount": 0,
        }

    @rpc
    def getblockfilter(self, blockhash, filtertype="basic"):
        """Dummy call, doing nothing"""
        return {}

    @rpc
    def estimatesmartfee(self, conf_target, estimate_mode="conservative"):
        if conf_target < 1 or conf_target > 1008:
            raise RPCError("Invalid conf_target, must be between 1 and 1008", -8)
        fee = self.sock.call("blockchain.estimatefee", [conf_target])
        # returns -1 if failed to estimate fee
        if fee < 0:
            return {
                "errors": ["Insufficient data or no feerate found"],
                "blocks": conf_target,
            }
        return {
            "feerate": fee,
            "blocks": conf_target,
        }

    @rpc
    def combinepsbt(self, txs):
        if not txs:
            raise RPCError("Parameter 'txs' cannot be empty", -8)
        psbt = PSBT.from_string(txs[0])
        for tx in txs[1::]:
            other = PSBT.from_string(tx)
            psbt.xpubs.update(other.xpubs)
            psbt.unknown.update(other.unknown)
            for i, inp in enumerate(other.inputs):
                psbt.inputs[i].update(inp)
            for i, out in enumerate(other.outputs):
                psbt.outputs[i].update(out)
        return str(psbt)

    @rpc
    def finalizepsbt(self, psbt, extract=True):
        psbt = PSBT.from_string(psbt)
        tx = None
        tx = finalize_psbt(psbt)
        if tx:
            if extract:
                return {"hex": str(tx), "complete": True}
            else:
                return {"psbt": str(psbt), "complete": True}
        return {"psbt": str(psbt), "complete": False}

    @rpc
    def testmempoolaccept(self, rawtxs, maxfeerate=0.1):
        # TODO: electrum doesn't have this method, we need to verify txs somehow differently
        # also missing txid and other stuff here
        return [{"allowed": True} for tx in rawtxs]

    @rpc
    def getrawtransaction(self, txid, verbose=False):
        """
        Get raw transaction data for a given transaction id.
        For more information on the Bitcoin RPC call see: https://developer.bitcoin.org/reference/rpc/getrawtransaction.html

        Parameters:
        - txid (str): The transaction id of the transaction you want to retrieve.
        - verbose (bool): Indicates whether to return detailed information about the transaction. Default is False.

        Returns:
        - dict: If verbose is set to True, it returns detailed information about the transaction specified by txid,
            otherwise it returns only the transaction data.
        Implementation details:
        - This method is using the ElectrumX API call `blockchain.transaction.get` which is documented here:
            https://electrumx.readthedocs.io/en/latest/protocol-methods.html#blockchain-transaction-get
        """
        if verbose:
            return self.sock.call("blockchain.transaction.get", [txid, True])
        else:
            return self.sock.call("blockchain.transaction.get", [txid, False])

    @rpc
    def sendrawtransaction(self, hexstring, maxfeerate=0.1):
        res = self.sock.call("blockchain.transaction.broadcast", [hexstring])
        if len(res) != 64:
            raise RPCError(res)
        return res

    # ========== WALLETS RPC CALLS ==========

    @rpc
    def listwallets(self):
        wallets = [w.name for w in Wallet.query.all()]
        logger.debug(f"These are the wallets from listwallets call: {wallets}")
        return wallets

    @rpc
    def listwalletdir(self):
        return [w.name for w in Wallet.query.all()]

    @rpc
    def createwallet(
        self,
        wallet_name,
        disable_private_keys=False,
        blank=False,
        passphrase="",
        avoid_reuse=False,
        descriptors=True,
        load_on_startup=True,
        external_signer=False,
    ):
        """Creates a wallet
        By default, it'll get a hotwallet
        """
        w = Wallet.query.filter_by(name=wallet_name).first()
        if w:
            raise RPCError("Wallet already exists", -4)
        w = Wallet(
            name=wallet_name,
            private_keys_enabled=(not disable_private_keys),
            seed=None,
        )
        db.session.add(w)
        db.session.commit()
        if not blank and not disable_private_keys:
            self.set_seed(w)  # random seed is set if nothing is passed as an argument
        return {"name": wallet_name, "warning": ""}

    @rpc
    def loadwallet(self, filename, load_on_startup=True):
        """Dummy call, doing nothing except checking wallet"""
        # this will raise if wallet doesn't exist
        self.get_wallet(filename)
        return {"name": filename, "warning": ""}

    @rpc
    def unloadwallet(self, filename, load_on_startup=True):
        """Dummy call, doing nothing except checking that wallet exists"""
        self.get_wallet(filename)
        return {"name": filename, "warning": ""}

    @walletrpc
    def getwalletinfo(self, wallet):
        confirmed, unconfirmed = self._get_balance(wallet)
        txnum = (
            db.session.query(Tx.txid)
            .filter(Tx.wallet_id == wallet.id)
            .distinct()
            .count()
        )
        return {
            "walletname": wallet.name,
            "walletversion": 169900,
            "format": "sqlite",
            "balance": sat_to_btc(confirmed),
            "unconfirmed_balance": sat_to_btc(unconfirmed),
            "immature_balance": 0,
            "txcount": txnum,
            "keypoolsize": wallet.get_keypool(internal=False),
            "keypoolsize_hd_internal": wallet.get_keypool(internal=True),
            "paytxfee": 0,
            "private_keys_enabled": wallet.private_keys_enabled,
            "avoid_reuse": False,
            "scanning": False,
            "descriptors": True,
            "external_signer": False,
        }

    @walletrpc
    def rescanblockchain(self, wallet: Wallet, up_from_height):
        """Dummy call, doing nothing"""
        logger.info("NOP: rescanblockchain")
        return {}

    @walletrpc
    def importdescriptors(self, wallet, requests):
        results = []
        for request in requests:
            try:
                self.importdescriptor(wallet, **request)
                result = {"success": True}
            except Exception as e:
                handle_exception(e)
                result = {"success": False, "error": {"code": -500, "message": str(e)}}
            results.append(result)
        return results

    @walletrpc
    def getnewaddress(self, wallet, label="", address_type=None):
        desc = wallet.get_descriptor(internal=False)
        if not desc:
            raise RPCError("No active descriptors", -500)
        # TODO: refill keypool, set label, subscribe
        return desc.getscriptpubkey().address(self.network)

    @walletrpc
    def getrawchangeaddress(self, wallet, address_type=None):
        desc = wallet.get_descriptor(internal=True)
        if not desc:
            raise RPCError("No active descriptors", -500)
        # TODO: refill keypool, subscribe
        return desc.getscriptpubkey().address(self.network)

    @walletrpc
    def listlabels(self, wallet, purpose=None):
        return list(
            {
                sc.label or ""
                for sc in db.session.query(Script.label)
                .filter(Script.wallet_id == wallet.id)
                .distinct()
                .all()
            }
        )

    @walletrpc
    def setlabel(self, wallet, address, label):
        scriptpubkey = EmbitScript.from_address(address)
        sc = Script.query.filter_by(
            script=scriptpubkey.data.hex(), wallet=wallet
        ).first()
        if sc:
            sc.label = label
        db.session.commit()

    @walletrpc
    def getaddressesbylabel(self, wallet, label):
        scripts = Script.query.filter_by(wallet=wallet, label=label).all()
        obj = {}
        for sc in scripts:
            obj[sc.address(self.network)] = {
                "purpose": "receive" if sc.index is not None else "send"
            }
        return obj

    def _get_tx(self, txid):
        fname = os.path.join(self.txdir, "%s.raw" % txid)
        if os.path.exists(fname):
            with open(fname, "r") as f:
                tx = EmbitTransaction.from_string(f.read())
            return tx

    @walletrpc
    def gettransaction(self, wallet, txid, include_watchonly=True, verbose=False):
        tx = self._get_tx(txid)
        if not tx:
            raise RPCError("Invalid or non-wallet transaction id", -5)
        txs = Tx.query.filter_by(wallet=wallet, txid=txid).all()
        if not txs:
            raise RPCError("Invalid or non-wallet transaction id", -5)
        tx0 = txs[0]
        confirmed = bool(tx0.height)
        t = int(time.time()) if not confirmed else tx0.blocktime
        obj = {
            "amount": sat_to_btc(sum([tx.amount for tx in txs])),
            "confirmations": (self.blocks - tx0.height + 1) if tx0.height else 0,
            "txid": txid,
            "walletconflicts": [],
            "time": t,
            "timereceived": t,
            "bip125-replaceable": "yes" if tx0.replaceable else "no",
            "details": [
                {
                    "address": tx.script.address(self.network),
                    "category": str(tx.category),
                    "amount": sat_to_btc(tx.amount),
                    "label": "",
                    "vout": tx.vout,
                }
                for tx in txs
                if tx.category != TxCategory.CHANGE
            ],
            "hex": str(tx),
        }
        if "send" in [d["category"] for d in obj["details"]]:
            obj.update({"fee": -sat_to_btc(tx0.fee or 0)})
        if confirmed:
            obj.update(
                {
                    "blockhash": tx0.blockhash,
                    "blockheight": tx0.height,
                    "blocktime": tx0.blocktime,
                }
            )
        else:
            obj.update({"trusted": False})
        if verbose:
            pass  # add "decoded"
        return obj

    @walletrpc
    def listtransactions(
        self, wallet, label="*", count=10, skip=0, include_watchonly=True
    ):
        txs = (
            db.session.query(Tx)
            .filter(
                Tx.wallet_id == wallet.id,
                Tx.category.in_([TxCategory.SEND, TxCategory.RECEIVE]),
            )
            .offset(skip)
            .limit(count)
            .all()
        )
        return [tx.to_dict(self.blocks, self.network) for tx in txs]

    def _get_balance(self, wallet: Wallet):
        """Returns a tuple: (confirmed, unconfirmed) in sats"""
        confirmed, unconfirmed = (
            db.session.query(
                func.sum(Script.confirmed).label("confirmed"),
                func.sum(Script.unconfirmed).label("unconfirmed"),
            )
            .filter(Script.wallet == wallet)
            .first()
        )
        if confirmed is None or unconfirmed is None:
            raise SpectrumException(f"No scripts for wallet {wallet.name}")
        return confirmed, unconfirmed

    @walletrpc
    def getbalances(self, wallet):
        confirmed, unconfirmed = self._get_balance(wallet)
        b = {
            "trusted": round(confirmed * 1e-8, 8),
            "untrusted_pending": round(unconfirmed * 1e-8, 8),
            "immature": 0.0,
        }
        if wallet.private_keys_enabled:
            return {"mine": b}
        else:
            return {
                "mine": b,
                "watchonly": b,
            }

    @walletrpc
    def lockunspent(self, wallet, unlock, transactions=[]):
        for txobj in transactions:
            txid = txobj["txid"]
            vout = txobj["vout"]
            utxo = UTXO.query.filter_by(wallet=wallet, txid=txid, vout=vout).first()
            if utxo is None:
                raise RPCError("Invalid parameter, unknown transaction", -8)
            if utxo.locked and not unlock:
                raise RPCError("Invalid parameter, output already locked", -8)
            if not utxo.locked and unlock:
                raise RPCError("Invalid parameter, expected locked output", -8)
            utxo.locked = not unlock
            db.session.commit()
        return True

    @walletrpc
    def listlockunspent(self, wallet):
        utxos = UTXO.query.filter_by(wallet=wallet, locked=True).all()
        return [{"txid": utxo.txid, "vout": utxo.vout} for utxo in utxos]

    @walletrpc
    def listunspent(
        self,
        wallet,
        minconf=1,
        maxconf=9999999,
        addresses=[],
        include_unsafe=True,
        query_options={},
    ):
        # TODO: options are currently ignored
        options = {
            "minimumAmount": 0,
            "maximumAmount": 0,
            "maximumCount": 99999999999,
            "minimumSumAmount": 0,
        }
        options.update(query_options)
        utxos = UTXO.query.filter_by(wallet=wallet, locked=False).all()
        return [
            {
                "txid": utxo.txid,
                "vout": utxo.vout,
                "amount": round(utxo.amount * 1e-8, 8),
                "spendable": True,
                "solvable": True,
                "safe": utxo.height is not None,
                "confirmations": (self.blocks - utxo.height + 1)
                if utxo.height
                else 0
                if utxo.height is not None
                else 0,
                "address": utxo.script.address(self.network),
                "scriptPubKey": utxo.script.script,
                "desc": utxo.script.descriptor.derive(utxo.script.index),
                # "desc": True, # should be descriptor, but we only check if desc is there or not
            }
            for utxo in utxos
        ]

    @walletrpc
    def listsinceblock(
        self,
        wallet,
        blockhash=None,
        target_confirmations=1,
        include_watchonly=True,
        include_removed=True,
    ):
        query = db.session.query(Tx).filter(
            Tx.wallet_id == wallet.id,
            Tx.category.in_([TxCategory.SEND, TxCategory.RECEIVE]),
        )
        # TODO: don't know how to get height from blockhash
        # looks like we need to store all block hashes as well
        if target_confirmations > 0:
            query = query.filter(Tx.height <= self.blocks - target_confirmations + 1)
        txs = query.all()
        txs = [
            {
                "address": tx.script.address(self.network),
                "category": str(tx.category),
                "amount": sat_to_btc(tx.amount),
                "label": "",
                "vout": tx.vout,
                "confirmations": (self.blocks - tx.height + 1) if tx.height else 0,
                "blockhash": tx.blockhash,
                "blockheight": tx.height,
                "blocktime": tx.blocktime,
                "txid": tx.txid,
                "time": tx.blocktime,
                "timereceived": tx.blocktime,
                "walletconflicts": [],
                "bip125-replaceable": "yes" if tx.replaceable else "no",
            }
            for tx in txs
        ]
        return {
            "transactions": [],
            "removed": [],
            "lastblock": self.bestblockhash,  # not sure about this one
        }

    @walletrpc
    def getreceivedbyaddress(self, wallet, address, minconf=1):
        sc = EmbitScript.from_address(address)
        script = Script.query.filter_by(script=sc.data.hex()).first()
        if not script:
            return 0
        # no transactions on this script
        if script.state is None:
            return 0
        (received,) = (
            db.session.query(
                func.sum(Tx.amount).label("amount"),
            )
            .filter(
                Tx.script == script,
                Tx.category.in_([TxCategory.CHANGE, TxCategory.RECEIVE]),
            )
            .first()
        )
        return sat_to_btc(received)

    @rpc
    def converttopsbt(self, hexstring, permitsigdata=False, iswitness=None):
        tx = EmbitTransaction.from_string(hexstring)
        # remove signatures
        if permitsigdata:
            for vin in tx.vin:
                vin.witness = Witness()
                vin.script_sig = EmbitScript()
        for vin in tx.vin:
            if vin.witness or vin.script_sig:
                raise RPCError(
                    "Inputs must not have scriptSigs and scriptWitnesses", -22
                )
        return str(PSBT(tx))

    def _fill_scope(self, scope, script, add_utxo=False):
        if add_utxo:
            tx = self._get_tx(scope.txid.hex())
            if tx is not None:
                is_segwit = tx.is_segwit
                # clear witness
                for vin in tx.vin:
                    vin.witness = Witness()
                scope.non_witness_utxo = tx
                vout = tx.vout[scope.vout]
                if is_segwit:
                    scope.witness_utxo = vout
        d = script.descriptor.get_descriptor(script.index)
        scope.witness_script = d.witness_script()
        scope.redeem_script = d.redeem_script()
        for k in d.keys:
            scope.bip32_derivations[k.get_public_key()] = DerivationPath(
                k.origin.fingerprint, k.origin.derivation
            )

    @walletrpc
    def walletcreatefundedpsbt(
        self, wallet, inputs=[], outputs=[], locktime=0, options={}, bip32derivs=True
    ):
        # we need to add more inputs if it's in options or if inputs are empty
        add_inputs = options.get("add_inputs", not bool(inputs))
        include_unsafe = options.get("include_unsafe", False)
        changeAddress = options.get("changeAddress", None)
        if changeAddress is None:
            desc = wallet.get_descriptor(internal=True)
            if not desc:
                raise RPCError("No active descriptors", -500)
            changeAddress = desc.getscriptpubkey().address(self.network)
        changePosition = options.get("changePosition", None)
        lockUnspents = options.get("lockUnspents", False)
        fee_rate = options.get("fee_rate", options.get("feeRate", 0) * 1e5)
        subtractFeeFromOutputs = options.get("subtractFeeFromOutputs", [])
        conf_target = options.get("conf_target", 6)
        replaceable = options.get("replaceable", False)
        if not fee_rate:
            fee_rate = self.sock.call("blockchain.estimatefee", [conf_target]) * 1e5
            if fee_rate < 0:
                fee_rate = 1
        destinations = []
        for out in outputs:
            for addr, amount in out.items():
                destinations.append(
                    TransactionOutput(
                        btc_to_sat(amount), EmbitScript.from_address(addr)
                    )
                )
        # don't add change out for now, just keep it here
        changeOut = TransactionOutput(0, EmbitScript.from_address(changeAddress))
        # get utxos from inputs
        inputs = [
            UTXO.query.filter_by(
                wallet=wallet, txid=inp["txid"], vout=inp["vout"]
            ).first()
            for inp in inputs
        ]
        if None in inputs:
            raise RPCError("Insufficient funds", -4)  # wrong utxo is provided in inputs
        sum_outs = sum([out.value for out in destinations])
        sum_ins = sum([inp.amount for inp in inputs])
        utxos = UTXO.query.filter_by(wallet=wallet, locked=False).order_by(
            UTXO.amount.desc()
        )
        tx = EmbitTransaction(
            vin=[TransactionInput(bytes.fromhex(inp.txid), inp.vout) for inp in inputs],
            vout=destinations,
            locktime=locktime,
        )
        sz = len(tx.serialize())
        # TODO: proper coin selection
        if add_inputs and sum_ins < (sum_outs + sz * fee_rate):
            for utxo in utxos:
                if not include_unsafe and not bool(utxo.height):
                    continue
                if utxo not in inputs:
                    inputs.append(utxo)
                    txin = TransactionInput(bytes.fromhex(utxo.txid), utxo.vout)
                    tx.vin.append(txin)
                    sz += len(txin.serialize())
                    sum_ins += utxo.amount
                if sum_ins >= (sum_outs + sz * fee_rate):
                    break
        if sum_ins < sum_outs:
            raise RPCError(f"Insufficient funds", -4)
        if not subtractFeeFromOutputs and sum_ins < (sum_outs + sz * fee_rate):
            raise RPCError(f"Insufficient funds", -4)
        change_amount = int(
            sum_ins - sum_outs - (sz + len(changeOut.serialize())) * fee_rate
        )
        # if it makes sense to add change output
        changepos = -1
        if change_amount > 0:
            changeOut.value = sum_ins - sum_outs  # we don't subtract fee right now
            tx.vout.insert(
                changePosition or random.randint(0, len(tx.vout) + 1), changeOut
            )
            changepos = tx.vout.index(changeOut)
        fee = math.ceil(len(tx.serialize()) * fee_rate)
        # subtract fee
        if subtractFeeFromOutputs:
            for idx in subtractFeeFromOutputs:
                tx.vout[idx].value -= math.ceil(fee / len(subtractFeeFromOutputs))
        elif changepos >= 0:
            tx.vout[changepos].value -= fee
        # set rbf if requested
        if replaceable:
            for inp in tx.vin:
                inp.sequence = 0xFFFFFFFD
        psbt = PSBT(tx)
        for i, inp in enumerate(psbt.inputs):
            self._fill_scope(inp, inputs[i].script, add_utxo=True)
        if changepos >= 0:
            sc = Script.query.filter_by(
                wallet=wallet, script=psbt.outputs[changepos].script_pubkey.data.hex()
            ).first()
            if sc:
                self._fill_scope(psbt.outputs[changepos], sc)
        if lockUnspents:
            for inp in inputs:
                inp.locked = True
            db.session.commit()
        return {"psbt": str(psbt), "fee": sat_to_btc(fee), "changepos": changepos}

    @walletrpc
    def walletprocesspsbt(self, wallet, psbt, sign=True, sighashtype=None):
        psbt = PSBT.from_string(psbt)
        # fill inputs
        for inp in psbt.inputs:
            tx = self._get_tx(inp.txid.hex())
            if tx is None:
                continue
            is_segwit = tx.is_segwit
            # clear witness
            for vin in tx.vin:
                vin.witness = Witness()
            inp.non_witness_utxo = tx
            vout = tx.vout[inp.vout]
            if is_segwit:
                inp.witness_utxo = vout
            sc = Script.query.filter(
                Script.wallet == wallet,
                Script.index.isnot(None),
                Script.script == vout.script_pubkey.data.hex(),
            ).first()
            if sc:
                self._fill_scope(inp, sc)
        # fill outputs
        for out in psbt.outputs:
            sc = Script.query.filter(
                Script.wallet == wallet,
                Script.index.isnot(None),
                Script.script == out.script_pubkey.data.hex(),
            ).first()
            if sc:
                self._fill_scope(out, sc)
        complete = False
        if sign and wallet.private_keys_enabled:
            for d in wallet.descriptors:
                psbt.sign_with(d.get_descriptor())
        res = str(psbt)
        try:
            if finalize_psbt(PSBT.from_string(res)):
                complete = True
        except:
            pass
        return {"psbt": res, "complete": complete}

    # ========== INTERNAL METHODS ==========

    def __repr__(self) -> str:
        return f"<Spectrum host={self.host} port={self.port} ssl={self.ssl}>"

    def set_seed(self, wallet, seed=None):
        if seed is None:
            seed = os.urandom(32).hex()
        self.seed = seed
        root = bip32.HDKey.from_seed(bytes.fromhex(seed))
        fgp = root.my_fingerprint.hex()
        # TODO: maybe better to use bip84?
        recv_desc = EmbitDescriptor.from_string(f"wpkh([{fgp}]{root}/0h/0/*)")
        change_desc = EmbitDescriptor.from_string(f"wpkh([{fgp}]{root}/0h/1/*)")
        self.importdescriptor(wallet, str(recv_desc), internal=False, active=True)
        self.importdescriptor(wallet, str(change_desc), internal=True, active=True)

    def importdescriptor(
        self,
        wallet: Wallet,
        desc: str,
        internal=False,
        active=False,
        label="",
        timestamp="now",
        next_index=0,
        **kwargs,
    ):
        logger.info(f"Importing descriptor {desc}")
        addr_range = kwargs.get("range", 300)  # because range is special keyword
        descriptor = EmbitDescriptor.from_string(desc)
        has_private_keys = any([k.is_private for k in descriptor.keys])
        private_descriptor = None
        if has_private_keys:
            private_descriptor = desc
            desc = str(descriptor)
        if active:
            # deactivate other active descriptor
            for old_desc in wallet.descriptors:
                if old_desc.internal == internal and old_desc.active:
                    old_desc.active = False
        d = Descriptor(
            wallet_id=wallet.id,
            active=active,
            internal=internal,
            descriptor=desc,
            private_descriptor=private_descriptor,
            next_index=next_index,
        )
        db.session.add(d)
        db.session.commit()
        # TODO: move to keypoolrefill or something
        # Add scripts
        logger.info(
            f"Creating {next_index + addr_range} scriptpubkeys for wallet {wallet}"
        )
        for i in range(0, next_index + addr_range):
            scriptpubkey = descriptor.derive(i).script_pubkey()
            address = scriptpubkey.address()
            # logger.info(f"   {address}")
            sc = Script(
                wallet=wallet,
                descriptor=d,
                index=i,
                script=scriptpubkey.data.hex(),
                scripthash=scripthash(scriptpubkey),
            )
            db.session.add(sc)
        db.session.commit()
        self.subcribe_scripts(d)
        return d
