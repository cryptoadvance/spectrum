# copied and adapted from https://github.com/spesmilo/electrum/blob/afa1a4d22a31d23d088c6670e1588eed32f7114d/lib/simple_config.py
# As we mainly use this in order to pick a random electrum-server (for now) other stuff has been heavily deleted



# Electrum - Lightweight Bitcoin Client
# Copyright (c) 2011-2016 Thomas Voegtlin
#
# Permission is hereby granted, free of charge, to any person
# obtaining a copy of this software and associated documentation files
# (the "Software"), to deal in the Software without restriction,
# including without limitation the rights to use, copy, modify, merge,
# publish, distribute, sublicense, and/or sell copies of the Software,
# and to permit persons to whom the Software is furnished to do so,
# subject to the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS
# BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN
# ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
# CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import random
import re

ELECTRUM_VERSION = '2.10.0'  # version of the client package
PROTOCOL_VERSION = '0.10'    # protocol version requested

DEFAULT_PORTS = {'t':'50001', 's':'50002'}

#There is a schedule to move the default list to e-x (electrumx) by Jan 2018
#Schedule is as follows:
#move ~3/4 to e-x by 1.4.17
#then gradually switch remaining nodes to e-x nodes

DEFAULT_SERVERS = {
    'erbium1.sytes.net':DEFAULT_PORTS,                  # core, e-x
    'ecdsa.net':{'t':'50001', 's':'110'},               # core, e-x
    'gh05.geekhosters.com':DEFAULT_PORTS,               # core, e-s
    'VPS.hsmiths.com':DEFAULT_PORTS,                    # core, e-x
    'electrum.anduck.net':DEFAULT_PORTS,                # core, e-s; banner with version pending
    'electrum.no-ip.org':DEFAULT_PORTS,                 # core, e-s
    'electrum.be':DEFAULT_PORTS,                        # core, e-x
    'helicarrier.bauerj.eu':DEFAULT_PORTS,              # core, e-x
    'elex01.blackpole.online':DEFAULT_PORTS,            # core, e-x
    'electrumx.not.fyi':DEFAULT_PORTS,                  # core, e-x
    'node.xbt.eu':DEFAULT_PORTS,                        # core, e-x
    'kirsche.emzy.de':DEFAULT_PORTS,                    # core, e-x
    'electrum.villocq.com':DEFAULT_PORTS,               # core?, e-s; banner with version recommended
    'us11.einfachmalnettsein.de':DEFAULT_PORTS,         # core, e-x
    'electrum.trouth.net':DEFAULT_PORTS,                # BU, e-s
    'Electrum.hsmiths.com':{'t':'8080', 's':'995'},     # core, e-x
    'electrum3.hachre.de':DEFAULT_PORTS,                # core, e-x
    'b.1209k.com':DEFAULT_PORTS,                        # XT, jelectrum
    'elec.luggs.co':{ 's':'443'},                       # core, e-x
    'btc.smsys.me':{'t':'110', 's':'995'},              # BU, e-x
}

def set_testnet():
    global DEFAULT_PORTS, DEFAULT_SERVERS
    DEFAULT_PORTS = {'t':'51001', 's':'51002'}
    DEFAULT_SERVERS = {
        'testnetnode.arihanc.com': DEFAULT_PORTS,
        'testnet1.bauerj.eu': DEFAULT_PORTS,
        '14.3.140.101': DEFAULT_PORTS,
        'testnet.hsmiths.com': {'t':'53011', 's':'53012'},
        'electrum.akinbo.org': DEFAULT_PORTS,
        'ELEX05.blackpole.online': {'t':'52011', 's':'52002'},
    }

def set_nolnet():
    global DEFAULT_PORTS, DEFAULT_SERVERS
    DEFAULT_PORTS = {'t':'52001', 's':'52002'}
    DEFAULT_SERVERS = {
        '14.3.140.101': DEFAULT_PORTS,
    }

NODES_RETRY_INTERVAL = 60
SERVER_RETRY_INTERVAL = 10

def parse_server_list():
    servers = {}
    with open("./src/cryptoadvance/specterext/spectrum/electrum/serverlist_online.txt","r") as file:
        lines=file.readlines()
    for line in lines:
        out = {}
        server = line.split()[0]
        port = line.split()[1]
        protocol = "s" if line.split()[2] == "ssl" else "t"
        servers[server] = { protocol: str(port)}
    return servers

def parse_servers(result):
    """ parse servers list into dict format"""
    servers = {}
    for item in result:
        host = item[1]
        out = {}
        version = None
        pruning_level = '-'
        if len(item) > 2:
            for v in item[2]:
                if re.match("[st]\d*", v):
                    protocol, port = v[0], v[1:]
                    if port == '': port = DEFAULT_PORTS[protocol]
                    out[protocol] = port
                elif re.match("v(.?)+", v):
                    version = v[1:]
                elif re.match("p\d*", v):
                    pruning_level = v[1:]
                if pruning_level == '': pruning_level = '0'
        if out:
            out['pruning'] = pruning_level
            out['version'] = version
            servers[host] = out
    return servers

def filter_protocol(hostmap, protocol = 's'):
    '''Filters the hostmap for those implementing protocol.
    The result is a list in serialized form.'''
    eligible = []
    for host, portmap in hostmap.items():
        port = portmap.get(protocol)
        if port:
            eligible.append(serialize_server(host, port, protocol))
    return eligible

def pick_random_server(hostmap = None, protocol = 's', exclude_set = set()):
    if hostmap is None:
        hostmap = parse_server_list()
    eligible = list(set(filter_protocol(hostmap, protocol)) - exclude_set)
    return random.choice(eligible) if eligible else None

proxy_modes = ['socks4', 'socks5', 'http']


def serialize_proxy(p):
    if not isinstance(p, dict):
        return None
    return ':'.join([p.get('mode'),p.get('host'), p.get('port'), p.get('user'), p.get('password')])


def deserialize_proxy(s):
    if not isinstance(s, str):
        return None
    if s.lower() == 'none':
        return None
    proxy = { "mode":"socks5", "host":"localhost" }
    args = s.split(':')
    n = 0
    if proxy_modes.count(args[n]) == 1:
        proxy["mode"] = args[n]
        n += 1
    if len(args) > n:
        proxy["host"] = args[n]
        n += 1
    if len(args) > n:
        proxy["port"] = args[n]
        n += 1
    else:
        proxy["port"] = "8080" if proxy["mode"] == "http" else "1080"
    if len(args) > n:
        proxy["user"] = args[n]
        n += 1
    if len(args) > n:
        proxy["password"] = args[n]
    return proxy


def deserialize_server(server_str):
    host, port, protocol = str(server_str).split(':')
    assert protocol in 'st'
    int(port)    # Throw if cannot be converted to int
    return host, port, protocol


def serialize_server(host, port, protocol):
    return str(':'.join([host, port, protocol]))

