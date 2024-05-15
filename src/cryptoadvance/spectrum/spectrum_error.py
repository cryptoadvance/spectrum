class RPCError(Exception):
    """Should use one of : https://github.com/bitcoin/bitcoin/blob/v22.0/src/rpc/protocol.h#L25-L88"""

    def __init__(self, message, code=-1):  # -1 is RPC_MISC_ERROR
        self.message = message
        self.code = code

    def to_dict(self):
        return {"code": self.code, "message": self.message}