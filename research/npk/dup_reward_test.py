#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
dup_reward_test.py - Kiem tra gui CUNG 1 rewardId nhieu lan co nhan thuong nhieu lan khong.
Do THAT su: currency ban dau (tu create_entity) + onUpdateCurrency + dungeon_client_attack_return
sau moi lan gui. Trong 1 phien. Dung tren tai khoan dev test. Dump ra --dump.
"""
import argparse, json, os, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from onmyoji_netclient import GateConn, short


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--session", default=os.path.join(HERE, "data", "session_live.json"))
    ap.add_argument("--dungeon-id", type=int, default=3)
    ap.add_argument("--reward-id", default="6ad04a456051644c2b3a21ff", help="1 rewardId dung lai cho moi lan")
    ap.add_argument("--times", type=int, default=3)
    ap.add_argument("--heroes", default="5f025569d8459fd8d4bc337c,5f025569d8459fd8d4bc337b,5f0bd6c1ce06853ba8880e90,5e3232384e8e6879c8cf2a53,5f900c59d8459f7fd78b2323,60b39933d8459fb53ad17011,5f025e88d8459fd8d4bc4ac0")
    ap.add_argument("--dump", default=os.path.join(HERE, "data", "dup_test.jsonl"))
    ap.add_argument("--per-listen", type=float, default=8.0)
    ap.add_argument("--send", action="store_true")
    a = ap.parse_args()
    heroes = [h.strip() for h in a.heroes.split(",") if h.strip()]

    if not a.send:
        print("DRY-RUN: se gui dungeon_rune_attack_result %d lan voi CUNG rewardId=%s" % (a.times, a.reward_id))
        print("Them --send de chay that (dev test).")
        return 0

    s = json.load(open(a.session))
    entityid = bytes.fromhex(s["entityid"])
    authmsg = open(os.path.join(HERE, "data", s["authmsg_file"]), "rb").read()
    dumpf = open(a.dump, "w")
    def log(o): dumpf.write(json.dumps(o, default=lambda x: x.hex() if isinstance(x, bytes) else str(x), ensure_ascii=False) + "\n"); dumpf.flush()

    c = GateConn(s["gate_ip"], s["gate_port"], s["pubkey"])
    print("[*] gate %s:%s" % (s["gate_ip"], s["gate_port"]))
    c.handshake(); c.resume(s["deviceid"], entityid, authmsg)

    cur0 = {}
    ready = False
    t_end = time.time() + 60
    while time.time() < t_end:
        try:
            name, msg = c.recv_frame(timeout=max(0.1, t_end - time.time()))
        except TimeoutError:
            break
        if name == "connect_reply":
            print("[*] connect_reply", msg.type)
            if msg.type != 2: print("[!] resume fail"); return 1
        elif name == "create_entity":
            p = c.decode_params(getattr(msg, "info", b""))
            if isinstance(p, dict):
                cur0 = dict(p.get("currency", {}) or {})
                print("[before] day_limit_pc =", p.get("day_limit_pc"), " #currency keys =", len(cur0))
                log({"ev": "before", "day_limit_pc": p.get("day_limit_pc"), "currency": cur0})
        elif name == "entity_message" and c.method_name(msg.method) == "become_player":
            ready = True; break
        elif name == "reg_md5_index":
            c.dyn_index[msg.index] = c.md5_names.get(msg.md5, msg.md5.hex())
    if not ready: print("[!] no become_player"); return 1

    reward_hits = 0
    cur_now = dict(cur0)
    for i in range(1, a.times + 1):
        payload = {"dungeon_id": a.dungeon_id, "result": {"iswin": True, "rewardId": a.reward_id}, "heroes": heroes, "buff": {}}
        print("\n===== LAN %d/%d  (cung rewardId=%s) =====" % (i, a.times, a.reward_id))
        log({"ev": "send", "n": i, "rewardId": a.reward_id})
        c.entity_call(entityid, "dungeon_rune_attack_result", payload)
        te = time.time() + a.per_listen
        while time.time() < te:
            try:
                name, msg = c.recv_frame(timeout=max(0.1, te - time.time()))
            except TimeoutError:
                break
            if name == "entity_message":
                mn = c.method_name(msg.method); p = c.decode_params(msg.parameters)
                if mn == "onUpdateCurrency" and isinstance(p, dict):
                    cid = str(p.get("cid")); cur_now[cid] = p.get("cnt")
                    print("  [$] cid=%s -> %s" % (cid, p.get("cnt")))
                    log({"ev": "currency", "n": i, "cid": cid, "cnt": p.get("cnt")})
                elif "dungeon_client_attack_return" in mn:
                    reward_hits += 1
                    print("  [REWARD] ", short(p, 300))
                    log({"ev": "reward", "n": i, "params": p})
                elif "day_limit_update" in mn:
                    print("  [limit]", short(p, 120)); log({"ev": "limit", "n": i, "params": p})
            elif name == "reg_md5_index":
                c.dyn_index[msg.index] = c.md5_names.get(msg.md5, msg.md5.hex())

    # diff currency
    print("\n===== CURRENCY DELTA (server-reported) =====")
    for cid in sorted(set(cur0) | set(cur_now)):
        a0 = cur0.get(cid); a1 = cur_now.get(cid)
        if a0 != a1:
            print("  cid=%s: %s -> %s  (delta %s)" % (cid, a0, a1, (a1 - a0) if (isinstance(a0,(int,float)) and isinstance(a1,(int,float))) else "?"))
            log({"ev": "delta", "cid": cid, "before": a0, "after": a1})
    print("\n[reward replies] =", reward_hits, " / ", a.times)
    log({"ev": "summary", "reward_hits": reward_hits, "times": a.times})
    dumpf.close()
    print("[dump] ->", a.dump)
    return 0


if __name__ == "__main__":
    sys.exit(main())
