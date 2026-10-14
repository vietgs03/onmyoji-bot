#!/usr/bin/env python3
"""api_sweep.py - Resume phien va goi lan luot cac RPC read-only (khong tham so), ghi lai phan hoi.

Dung: .venv-net/bin/python api_sweep.py [--list data/sweep_list.json] [--gap 0.35]
Output: data/api_sweep_results.json  {method: {"replies": [{"method","params"}], "latency": s}}
        data/api_sweep_all.jsonl      moi entity_message nhan duoc (kem method dang cho)
"""
import argparse, json, os, random, sys, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from onmyoji_netclient import DATA, GateConn, _msg  # noqa

def jdefault(o):
    if isinstance(o, bytes): return o.hex()
    if hasattr(o, "code") and hasattr(o, "data"): return {"ext": o.code, "hex": o.data.hex()}
    return str(o)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", default=os.path.join(DATA, "sweep_list.json"))
    ap.add_argument("--gap", type=float, default=0.35)
    ap.add_argument("--tail", type=float, default=6.0)
    ap.add_argument("--jitter", type=float, default=0.0, help="cong them uniform(0, jitter) giay moi lan goi")
    ap.add_argument("--out", default="api_sweep", help="tien to file ket qua trong data/")
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()
    methods = json.load(open(a.list))
    if a.limit: methods = methods[:a.limit]
    s = json.load(open(os.path.join(DATA, "session.json")))
    eid = bytes.fromhex(s["entityid"])
    auth = open(os.path.join(DATA, s["authmsg_file"]), "rb").read()
    # Chan resume bang authmsg cu: sid trong authmsg phai khop sid hien tai cua game
    # (tranh gui connect_server sai -> RECONNECT_FAILED, de lai dau vet dang nhap loi)
    import bson
    a_sid = bson.decode(auth).get("session")
    if a_sid != s.get("sid"):
        print("[!] authmsg.bson cu (sid khac phien hien tai). Chay grab_session.ps1 sau khi game tu reconnect.")
        return 1
    c = GateConn(s["gate_ip"], s["gate_port"], s["pubkey"], verbose=False)
    c.handshake()
    c.resume(s["deviceid"], eid, auth)
    rtype = None
    t0 = time.time()
    while time.time() - t0 < 10:
        n, m = c.recv_frame(timeout=10)
        if n == "connect_reply":
            rtype = m.type; break
    print("connect_reply", rtype)
    if rtype != 2:
        print("resume failed (session expired?)"); return 1

    allf = open(os.path.join(DATA, a.out + "_all.jsonl"), "w")
    results = {m: {"replies": [], "latency": None} for m in methods}
    sent_at = {}
    pending = list(methods)
    current = None

    def drain(until):
        nonlocal current
        while True:
            left = until - time.time()
            if left <= 0: return
            try:
                n, msg = c.recv_frame(timeout=left)
            except TimeoutError:
                return
            if n != "entity_message":
                continue
            mn = c.method_name(msg.method)
            p = c.decode_params(msg.parameters)
            allf.write(json.dumps({"t": time.time(), "after": current, "method": mn, "params": p}, default=jdefault, ensure_ascii=False) + "\n")
            # ghep reply: ten bat dau bang method da goi (method_cb, method_reply, method_result...)
            for req in sent_at:
                if mn == req or mn.startswith(req + "_") or mn.startswith(req.replace("get_", "") + "_cb"):
                    r = results[req]
                    if r["latency"] is None: r["latency"] = round(time.time() - sent_at[req], 3)
                    if len(r["replies"]) < 3:
                        r["replies"].append({"method": mn, "params": json.loads(json.dumps(p, default=jdefault))})
                    break

    drain(time.time() + 3)  # bo qua dot sync khi vao phien
    for i, m in enumerate(pending):
        current = m
        sent_at[m] = time.time()
        c.entity_call(eid, m, {})
        drain(time.time() + a.gap + random.uniform(0, a.jitter))
        if i % 20 == 0:
            print("JCODE_PROGRESS {\"current\":%d,\"total\":%d,\"unit\":\"rpc\"}" % (i, len(pending)), flush=True)
    current = None
    drain(time.time() + a.tail)
    allf.close()
    json.dump(results, open(os.path.join(DATA, a.out + "_results.json"), "w"), ensure_ascii=False, indent=1, default=jdefault)
    ok = [m for m, r in results.items() if r["replies"]]
    print("called %d, replied %d, silent %d" % (len(methods), len(ok), len(methods) - len(ok)))
    return 0

if __name__ == "__main__":
    sys.exit(main())
