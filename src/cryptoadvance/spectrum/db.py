"""
[![](https://mermaid.ink/img/pako:eNp9VMtuwjAQ_BXLpz7gB3Ks4NBTD1CVA1K02Eti4diRHxQU5d_rPAiJA80pnhl7Z8ebVJRpjjShTIK1KwGZgWKvSHh-QEp05G25JCu0zIjSadNR93VLb9rFbNcT-Hu7--rAThCBI-V2N9M1UAe2hnt11UGEvG-cESojCgocsIPWkpRGnMFhesKrTVHBQSKPd1mcY2Wo8qsNTy3Ivpd6bOAeRTUtCMyJc2RCKIdGgYyL8CjfwAQpUXhxqVAcLw8Kd6FUkw0j7air0TXEaA42nzEu5DSAHyL7DCczrY7CFKN8esKrOQWcG7T25XWwPTbeXPXUtrsIPgHO2rsJkKPIchfXhkJ75aYRS81ONyv1jeqesYnt7h8LfRCH5qxJQs-ttFon4qkzWEpg2EzbQKyVLwgLGWfaXJ-3_bjHgDbKI_bn1XRBCzQFCB4-4ranPXU5BiM0Ca8cj-DD4NK9aqS-5KHwmoswajQ5grS4oOCd3lwVo4kzHm-i_l_Qq-o_ZgxJhg)](https://mermaid-js.github.io/mermaid-live-editor/edit#pako:eNp9VMtuwjAQ_BXLpz7gB3Ks4NBTD1CVA1K02Eti4diRHxQU5d_rPAiJA80pnhl7Z8ebVJRpjjShTIK1KwGZgWKvSHh-QEp05G25JCu0zIjSadNR93VLb9rFbNcT-Hu7--rAThCBI-V2N9M1UAe2hnt11UGEvG-cESojCgocsIPWkpRGnMFhesKrTVHBQSKPd1mcY2Wo8qsNTy3Ivpd6bOAeRTUtCMyJc2RCKIdGgYyL8CjfwAQpUXhxqVAcLw8Kd6FUkw0j7air0TXEaA42nzEu5DSAHyL7DCczrY7CFKN8esKrOQWcG7T25XWwPTbeXPXUtrsIPgHO2rsJkKPIchfXhkJ75aYRS81ONyv1jeqesYnt7h8LfRCH5qxJQs-ttFon4qkzWEpg2EzbQKyVLwgLGWfaXJ-3_bjHgDbKI_bn1XRBCzQFCB4-4ranPXU5BiM0Ca8cj-DD4NK9aqS-5KHwmoswajQ5grS4oOCd3lwVo4kzHm-i_l_Qq-o_ZgxJhg)


"""

from flask_sqlalchemy import SQLAlchemy
from embit.descriptor import Descriptor as EmbitDescriptor
from embit.descriptor.checksum import add_checksum
from embit.script import Script as EmbitScript
from enum import Enum
import time
from .util import sat_to_btc
from sqlalchemy.ext.declarative import declared_attr
from cryptoadvance.spectrum.util_specter import snake_case2camelcase
from sqlalchemy.orm import DeclarativeMeta, declarative_base
from flask_sqlalchemy.model import BindMetaMixin, Model


class NoNameMeta(BindMetaMixin, DeclarativeMeta):
    pass


CustomModel = declarative_base(cls=Model, metaclass=NoNameMeta, name="Model")

db = SQLAlchemy(model_class=CustomModel)
# db = SQLAlchemy()


class SpectrumModel(db.Model):
    __abstract__ = True

    @declared_attr
    def __tablename__(cls):
        return "spectrum_" + snake_case2camelcase(cls.__name__)


class TxCategory(Enum):
    UNKNOWN = 0
    RECEIVE = 1
    SEND = 2
    CHANGE = 3  # hidden

    def __str__(self):
        return self.name.lower()


class Wallet(SpectrumModel):
    id = db.Column(db.Integer, primary_key=True)
    # maybe later User can be added to the wallet,
    # so wallet name may not be unique
    # value is like specter_hotstorage.../wallet_name_can_be_long
    name = db.Column(db.String(200), unique=True)
    private_keys_enabled = db.Column(db.Boolean, default=False)
    # if non-empty, using hdseed, 32 bytes
    # potentially encrypted, so some extra space here
    seed = db.Column(db.String(200), nullable=True, default=None)
    # salt for password if password is used, None if password is not used
    password_salt = db.Column(db.String(100), nullable=True, default=None)

    def get_descriptor(self, internal=False):
        for desc in self.descriptors:
            if desc.active and desc.internal == internal:
                return desc

    def get_keypool(self, internal=False):
        # TODO
        return 1000


class Descriptor(SpectrumModel):
    """Descriptors tracked by the wallet"""

    id = db.Column(db.Integer, primary_key=True)
    wallet_id = db.Column(
        db.Integer, db.ForeignKey(f"{Wallet.__tablename__}.id"), nullable=False
    )
    wallet = db.relationship("Wallet", backref=db.backref("descriptors", lazy=True))
    # if we should use this descriptor for new addresses
    active = db.Column(db.Boolean, default=True)
    # if we should use it for change or receiving addresses
    internal = db.Column(db.Boolean, default=False)
    # descriptor itself, 15 cosigners, each xpub is 111 chars, plus derivation
    # but 3k should be enough
    descriptor = db.Column(db.String(3000), nullable=False)
    # original descriptor with private keys (if private keys are enabled)
    # potentially encrypted somehow
    # reqiured for Specter's hot wallet storage
    private_descriptor = db.Column(db.String(3000), nullable=True, default=None)
    # address index used by the next getnewaddress() call
    next_index = db.Column(db.Integer, default=0)

    def getscriptpubkey(self, index=None):
        if index is None:
            index = self.next_index
        d = EmbitDescriptor.from_string(self.private_descriptor or self.descriptor)
        return d.derive(index).script_pubkey()

    def derive(self, index):
        d = EmbitDescriptor.from_string(self.private_descriptor or self.descriptor)
        d = d.derive(index)
        for k in d.keys:
            k.key = k.key.get_public_key()
        return add_checksum(str(d))

    def get_descriptor(self, index=None):
        """Returns Descriptor class"""
        d = EmbitDescriptor.from_string(self.private_descriptor or self.descriptor)
        if index is not None:
            d = d.derive(index)
        return d


# We store script pubkeys instead of addresses as database is chain-agnostic
class Script(SpectrumModel):
    id = db.Column(db.Integer, primary_key=True)
    wallet_id = db.Column(
        db.Integer, db.ForeignKey(f"{Wallet.__tablename__}.id"), nullable=False
    )
    wallet = db.relationship("Wallet", backref=db.backref("scripts", lazy=True))
    # this must be nullable as we may need to label external scripts
    descriptor_id = db.Column(
        db.Integer,
        db.ForeignKey(f"{Descriptor.__tablename__}.id"),
        nullable=True,
        default=None,
    )
    descriptor = db.relationship("Descriptor", backref=db.backref("scripts", lazy=True))
    # derivation index if it's our address
    index = db.Column(db.Integer, nullable=True, default=None)

    script = db.Column(db.String(100), nullable=False)
    label = db.Column(db.String(500), nullable=True, default=None)
    # scripthash for electrum subscribtions, store for lookups
    scripthash = db.Column(db.String(64), nullable=True, default=None)
    # electrum stuff - hash of all txs on the address
    state = db.Column(db.String(64), nullable=True, default=None)
    # confirmed balance in sat
    confirmed = db.Column(db.BigInteger, default=0)
    # unconfirmed balance in sat
    unconfirmed = db.Column(db.BigInteger, default=0)

    def address(self, network):
        return self.script_pubkey.address(network)

    @property
    def script_pubkey(self):
        return EmbitScript(bytes.fromhex(self.script))


class UTXO(SpectrumModel):
    id = db.Column(db.Integer, primary_key=True)
    txid = db.Column(db.String(64))
    vout = db.Column(db.Integer)
    height = db.Column(db.Integer, default=None)
    # amount in sat
    amount = db.Column(db.BigInteger)
    # frozen or not
    locked = db.Column(db.Boolean, default=False)
    # refs
    script_id = db.Column(db.Integer, db.ForeignKey(f"{Script.__tablename__}.id"))
    script = db.relationship("Script", backref=db.backref("utxos", lazy=True))
    wallet_id = db.Column(
        db.Integer, db.ForeignKey(f"{Wallet.__tablename__}.id"), nullable=False
    )
    wallet = db.relationship("Wallet", backref=db.backref("utxos", lazy=True))


class Tx(SpectrumModel):
    id = db.Column(db.Integer, primary_key=True)
    txid = db.Column(db.String(64))
    blockhash = db.Column(db.String(64), default=None)
    height = db.Column(db.Integer, default=None)
    blocktime = db.Column(db.BigInteger, default=None)
    replaceable = db.Column(db.Boolean, default=False)
    category = db.Column(db.Enum(TxCategory), default=TxCategory.UNKNOWN)
    vout = db.Column(db.Integer, default=None)
    amount = db.Column(db.BigInteger, default=0)
    fee = db.Column(db.BigInteger, default=None)  # only for send
    # refs
    script_id = db.Column(db.Integer, db.ForeignKey(f"{Script.__tablename__}.id"))
    script = db.relationship("Script", backref=db.backref("txs", lazy=True))
    wallet_id = db.Column(
        db.Integer, db.ForeignKey(f"{Wallet.__tablename__}.id"), nullable=False
    )
    wallet = db.relationship("Wallet", backref=db.backref("txs", lazy=True))

    def to_dict(self, blockheight, network):
        confirmed = bool(self.height)
        confs = (blockheight - self.height + 1) if self.height else 0
        t = self.blocktime if confirmed else int(time.time())
        obj = {
            "address": self.script.address(network),
            "category": str(self.category),
            "amount": sat_to_btc(self.amount),
            "label": "",
            "vout": self.vout,
            "confirmations": confs,
            "txid": self.txid,
            "time": t,
            "timereceived": t,
            "walletconflicts": [],
            "bip125-replaceable": "yes" if self.replaceable else "no",
            "script_id": self.script_id,
        }
        if self.category == TxCategory.SEND:
            obj.update({"fee": -sat_to_btc(self.fee or 0)})
        if confirmed:
            obj.update(
                {
                    "blockhash": self.blockhash,
                    "blockheight": self.height,
                    "blocktime": t,
                }
            )
        else:
            obj.update({"trusted": False})
        return obj
