#!/usr/bin/env python3
"""onmyoji_netclient.py - Client giao thuc gate Onmyoji, chay doc lap (khong can game).

Giao thuc (dich tu lib/mobilerpc/*, lib/client/GateClient.py, lib/common/*):
  frame     : u32le(len(pb)+2) | u16le(method_index) | protobuf
  transport : gui = RC4(zlib_sync_flush(frame)) ; nhan = zlib_decompress(RC4(data))
              (RC4 va zlib la stream lien tuc tren ca ket noi; zlib bat sau connect_server)
  handshake : seed_request(Void) -> seed_reply(SessionSeed)
              session_key(EncryptString{RSA-OAEP(loginpubkey, SessionKey)}) -> bat RC4(sha1(rand32))
              connect_server(ConnectServerRequest RE_CONNECTION, deviceid, entityid, authmsg=BSON)
              -> session_key_ok, connect_reply(type), roi entity_message hai chieu
  RPC       : EntityMessage{id=ObjectId 12B, method=Md5OrIndex{md5(name)|index}, parameters=msgpack(dict)}

Thong tin phien (authmsg, entityid, gate) doc tu RAM game bang pyobj_dump.ps1.
"""
import argparse, hashlib, json, os, socket, struct, sys, time, zlib

import bson, msgpack
from Crypto.Cipher import ARC4, PKCS1_OAEP
from Crypto.PublicKey import RSA
from Crypto.Random import get_random_bytes
from google.protobuf import descriptor_pb2, descriptor_pool, message_factory

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")

_pool = descriptor_pool.DescriptorPool()
for fn in ("common.proto.desc", "client_gate.proto.desc"):
    fdp = descriptor_pb2.FileDescriptorProto()
    fdp.ParseFromString(open(os.path.join(DATA, "proto", fn), "rb").read())
    _pool.Add(fdp)


def _msg(name):
    return message_factory.GetMessageClass(_pool.FindMessageTypeByName("mobile.server." + name))


GATE_SVC = _pool.FindServiceByName("mobile.server.IGateService")
GATE_CLI = _pool.FindServiceByName("mobile.server.IGateClient")
SVC_IDX = {m.name: i for i, m in enumerate(GATE_SVC.methods)}
STATIC_INDEX = {int(k): v for k, v in json.load(open(os.path.join(DATA, "static_index_map.json"))).items()}
_MD5N = os.path.join(DATA, "md5_names.json")
MD5_NAMES = {bytes.fromhex(k): v for k, v in json.load(open(_MD5N)).items()} if os.path.exists(_MD5N) else {}


class GateConn:
    def __init__(self, host, port, pubkey, verbose=True):
        self.verbose = verbose
        self.sock = socket.create_connection((host, int(port)), timeout=10)
        self.enc = self.dec = None
        self.comp = self.decomp = None
        self.buf = b""
        self.pubkey = RSA.importKey(pubkey)
        self.md5_names = {}
        self.dyn_index = {}

    def log(self, *a):
        if self.verbose:
            print(*a, flush=True)

    # ---------- transport ----------
    def _send_raw(self, data):
        if self.comp:
            data = self.comp.compress(data) + self.comp.flush(zlib.Z_SYNC_FLUSH)
        if self.enc:
            data = self.enc.encrypt(data)
        self.sock.sendall(data)

    def call(self, method, msg):
        pb = msg.SerializeToString()
        self._send_raw(struct.pack("<IH", len(pb) + 2, SVC_IDX[method]) + pb)

    def _recv_some(self, timeout):
        self.sock.settimeout(timeout)
        data = self.sock.recv(65536)
        if not data:
            raise ConnectionError("server closed connection")
        if self.dec:
            data = self.dec.decrypt(data)
        if self.decomp:
            data = self.decomp.decompress(data)
        self.buf += data

    def recv_frame(self, timeout=10.0):
        """Tra ve (method_name, message) cua IGateClient."""
        deadline = time.time() + timeout
        while True:
            if len(self.buf) >= 4:
                n = struct.unpack("<I", self.buf[:4])[0]
                if len(self.buf) >= 4 + n:
                    body = self.buf[4:4 + n]
                    self.buf = self.buf[4 + n:]
                    idx = struct.unpack("<H", body[:2])[0]
                    m = GATE_CLI.methods[idx]
                    msg = message_factory.GetMessageClass(m.input_type)()
                    msg.ParseFromString(body[2:])
                    return m.name, msg
            left = deadline - time.time()
            if left <= 0:
                raise TimeoutError("no frame")
            self._recv_some(left)

    # ---------- handshake ----------
    def handshake(self):
        self.call("seed_request", _msg("Void")())
        name, seed = self.recv_frame()
        assert name == "seed_reply", name
        self.log("[hs] seed =", seed.seed)
        sk = _msg("SessionKey")()
        sk.random_padding_header = get_random_bytes(32)
        sk.session_key = hashlib.sha1(get_random_bytes(32)).digest()
        sk.seed = seed.seed
        sk.random_padding_tail = get_random_bytes(32)
        es = _msg("EncryptString")()
        es.encryptstr = PKCS1_OAEP.new(self.pubkey).encrypt(sk.SerializeToString())
        self.call("session_key", es)
        # GateClient.set_crypter ngay sau khi gui session_key
        self.enc = ARC4.new(sk.session_key)
        self.dec = ARC4.new(sk.session_key)
        name, _ = self.recv_frame()
        self.log("[hs] <-", name)
        assert name == "session_key_ok", name

    def resume(self, deviceid, entityid, authmsg):
        req = _msg("ConnectServerRequest")()
        req.type = 1  # RE_CONNECTION
        req.deviceid = deviceid.encode() if isinstance(deviceid, str) else deviceid
        req.entityid = entityid
        req.authmsg = authmsg
        self.call("connect_server", req)
        # GateClient._reconnect_server: set_compressor ngay sau connect_server
        self.comp = zlib.compressobj()
        self.decomp = zlib.decompressobj()

    def new_connection(self, deviceid):
        req = _msg("ConnectServerRequest")()
        req.type = 0
        req.deviceid = deviceid.encode() if isinstance(deviceid, str) else deviceid
        self.call("connect_server", req)
        self.comp = zlib.compressobj()
        self.decomp = zlib.decompressobj()

    # ---------- entity RPC ----------
    def entity_call(self, entityid, method, params=None):
        em = _msg("EntityMessage")()
        em.id = entityid
        md5 = hashlib.md5(method.encode()).digest()
        self.md5_names[md5] = method
        em.method.md5 = md5
        if params is not None:
            em.parameters = msgpack.packb(params, use_bin_type=True)
        self.call("entity_message", em)

    def method_name(self, m):
        if m.index > 0:
            return STATIC_INDEX.get(m.index) or self.dyn_index.get(m.index) or "#%d" % m.index
        return self.md5_names.get(m.md5) or MD5_NAMES.get(m.md5) or "md5:" + m.md5.hex()

    def decode_params(self, raw):
        if not raw:
            return None
        try:
            return msgpack.unpackb(raw, raw=False, strict_map_key=False)
        except Exception:
            try:
                return bson.decode(raw)
            except Exception:
                return raw[:64]


def short(v, n=300):
    s = repr(v)
    return s if len(s) <= n else s[:n] + "..."


def _parse_calls(s):
    """Parse --calls. Each token is either `method` (params={}) or
    `method={<json params>}` (JSON must start with { or [)."""
    out = []
    for tok in s.split(","):
        tok = tok.strip()
        if not tok:
            continue
        i = tok.find("=")
        if i != -1 and i + 1 < len(tok) and tok[i + 1] in "{[":
            name = tok[:i]
            params = json.loads(tok[i + 1:])
        else:
            name = tok
            params = {}
        out.append((name, params))
    return out


def _find_key(o, key):
    """Recursively find first value under `key` in a decoded msgpack/bson tree."""
    if isinstance(o, dict):
        for k, v in o.items():
            if k == key:
                return v
            r = _find_key(v, key)
            if r is not None:
                return r
    elif isinstance(o, list):
        for v in o:
            r = _find_key(v, key)
            if r is not None:
                return r
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--session", default=os.path.join(DATA, "session.json"))
    ap.add_argument("--calls", default="get_server_time,ping_message",
                    help="comma list; each `method` or `method={<json params>}`")
    ap.add_argument("--listen", type=float, default=8.0)
    ap.add_argument("--dump", default="", help="ghi toan bo message nhan duoc ra file JSONL")
    ap.add_argument("--only", default="", help="chi in cac method co chuoi nay")
    ap.add_argument("--reward-out", default="", help="append *_attack_return rewardId (JSONL)")
    a = ap.parse_args()
    s = json.load(open(a.session))
    entityid = bytes.fromhex(s["entityid"])
    authmsg = open(os.path.join(DATA, s["authmsg_file"]), "rb").read()

    c = GateConn(s["gate_ip"], s["gate_port"], s["pubkey"])
    print("[*] connected to gate %s:%s" % (s["gate_ip"], s["gate_port"]))
    c.handshake()
    c.resume(s["deviceid"], entityid, authmsg)
    t_end = time.time() + 10
    connected = False
    while time.time() < t_end:
        name, msg = c.recv_frame(timeout=max(0.1, t_end - time.time()))
        if name == "connect_reply":
            print("[*] connect_reply type =", msg.type, _msg("ConnectServerReply").DESCRIPTOR.enum_types_by_name["ReplyType"].values_by_number[msg.type].name)
            connected = msg.type == 2
            break
        print("[<]", name)
    if not connected:
        print("[!] resume failed"); return 1

    for m, p in _parse_calls(a.calls):
        print("[>] call", m, short(p, 200))
        c.entity_call(entityid, m, p)

    rewardf = open(a.reward_out, "a") if a.reward_out else None
    t_end = time.time() + a.listen
    seen = {}
    dumpf = open(a.dump, "w") if a.dump else None
    while time.time() < t_end:
        try:
            name, msg = c.recv_frame(timeout=max(0.1, t_end - time.time()))
        except TimeoutError:
            break
        if name == "entity_message":
            mn = c.method_name(msg.method)
            p = c.decode_params(msg.parameters)
            seen[mn] = seen.get(mn, 0) + 1
            if dumpf:
                dumpf.write(json.dumps({"method": mn, "params": p}, default=lambda o: o.hex() if isinstance(o, bytes) else (o.data.hex() if hasattr(o, "data") else str(o)), ensure_ascii=False) + "\n")
            if (not a.only or a.only in mn) and seen[mn] <= 2:
                print("[<] entity_message %-40s %s" % (mn, short(p, 240)))
            if "attack_return" in mn:
                rid = _find_key(p, "rewardId")
                if rid is not None:
                    print("[REWARD] %s rewardId=%r" % (mn, rid))
                    if rewardf:
                        rewardf.write(json.dumps({"method": mn, "rewardId": rid, "params": p}, default=lambda o: o.hex() if isinstance(o, bytes) else (o.data.hex() if hasattr(o, "data") else str(o)), ensure_ascii=False) + "\n")
                        rewardf.flush()
        elif name == "reg_md5_index":
            c.dyn_index[msg.index] = c.md5_names.get(msg.md5, msg.md5.hex())
        else:
            print("[<]", name, short(msg, 200))
    if rewardf:
        rewardf.close()
    print("[*] message counts:", dict(sorted(seen.items(), key=lambda x: -x[1])[:25]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
