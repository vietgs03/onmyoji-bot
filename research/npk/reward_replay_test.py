#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
reward_replay_test.py - Kiem tra co "ep"/tai dung rewardId duoc khong (replay test).
Chi 1 phien resume. Gui dungeon_rune_attack_result voi:
  - CASE reuse: rewardId CU da dung (--reuse-id)
  - CASE fake : rewardId BIA (objectid ngau nhien)
KHONG goi attack moi. Quan sat server chap nhan (reward+day_limit) hay tu choi (err).
Dump het ra --dump. Dung tren tai khoan dev test.
"""
import argparse, json, os, sys, time, binascii, random

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from onmyoji_netclient import GateConn, short


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--session", default=os.path.join(HERE, "data", "session_live.json"))
    ap.add_argument("--dungeon-id", type=int, default=3)
    ap.add_argument("--reuse-id", default="6ad04a456051644c2b3a21ff",
                    help="rewardId cu da dung o tran truoc")
    ap.add_argument("--heroes", default="5f025569d8459fd8d4bc337c,5f025569d8459fd8d4bc337b,5f0bd6c1ce06853ba8880e90,5e3232384e8e6879c8cf2a53,5f900c59d8459f7fd78b2323,60b39933d8459fb53ad17011,5f025e88d8459fd8d4bc4ac0")
    ap.add_argument("--dump", default=os.path.join(HERE, "data", "replay_test.jsonl"))
    ap.add_argument("--listen", type=float, default=12.0)
    ap.add_argument("--send", action="store_true", help="GUI THAT. Mac dinh dry-run.")
    a = ap.parse_args()

    heroes = [h.strip() for h in a.heroes.split(",") if h.strip()]
    fake_id = binascii.hexlify(bytes([random.randint(0, 255) for _ in range(12)])).decode()

    cases = [
        ("reuse_old_id", a.reuse_id),
        ("fabricated_id", fake_id),
    ]

    if not a.send:
        print("=== DRY-RUN ===")
        for name, rid in cases:
            print(name, "-> dungeon_rune_attack_result", json.dumps(
                {"dungeon_id": a.dungeon_id, "result": {"iswin": True, "rewardId": rid},
                 "heroes": heroes, "buff": {}}, ensure_ascii=False))
        print("\nThem --send de gui that (tai khoan dev test).")
        return 0

    s = json.load(open(a.session))
    entityid = bytes.fromhex(s["entityid"])
    authmsg = open(os.path.join(HERE, "data", s["authmsg_file"]), "rb").read()
    dumpf = open(a.dump, "w")

    def log(obj):
        dumpf.write(json.dumps(obj, default=lambda o: o.hex() if isinstance(o, bytes) else str(o), ensure_ascii=False) + "\n")
        dumpf.flush()

    c = GateConn(s["gate_ip"], s["gate_port"], s["pubkey"])
    print("[*] gate %s:%s" % (s["gate_ip"], s["gate_port"]))
    c.handshake()
    c.resume(s["deviceid"], entityid, authmsg)

    # cho become_player + bat day_limit_pc tu create_entity (counter TRUOC)
    ready = False
    counter_before = None
    t_end = time.time() + 60
    while time.time() < t_end:
        try:
            name, msg = c.recv_frame(timeout=max(0.1, t_end - time.time()))
        except TimeoutError:
            break
        if name == "connect_reply":
            print("[*] connect_reply type =", msg.type)
            if msg.type != 2:
                print("[!] resume fail"); return 1
        elif name == "create_entity":
            p = c.decode_params(getattr(msg, "info", b""))
            if isinstance(p, dict):
                counter_before = p.get("day_limit_pc")
                print("[before] day_limit_pc =", counter_before)
                log({"ev": "counter_before", "day_limit_pc": counter_before})
        elif name == "entity_message":
            if c.method_name(msg.method) == "become_player":
                ready = True
                break
        elif name == "reg_md5_index":
            c.dyn_index[msg.index] = c.md5_names.get(msg.md5, msg.md5.hex())
    if not ready:
        print("[!] khong thay become_player"); return 1

    # gui tung case, nghe phan hoi
    for case_name, rid in cases:
        payload = {"dungeon_id": a.dungeon_id,
                   "result": {"iswin": True, "rewardId": rid},
                   "heroes": heroes, "buff": {}}
        print("\n===== CASE %s  rewardId=%s =====" % (case_name, rid))
        log({"ev": "send", "case": case_name, "payload": payload})
        c.entity_call(entityid, "dungeon_rune_attack_result", payload)
        te = time.time() + a.listen
        got = False
        while time.time() < te:
            try:
                name, msg = c.recv_frame(timeout=max(0.1, te - time.time()))
            except TimeoutError:
                break
            if name == "entity_message":
                mn = c.method_name(msg.method)
                p = c.decode_params(msg.parameters)
                if any(k in mn for k in ("attack", "reward", "day_limit", "currency", "freeze", "err", "lock")):
                    print("  [<]", mn, short(p, 240))
                    log({"ev": "reply", "case": case_name, "method": mn, "params": p})
                    if "dungeon_client_attack_return" in mn or "day_limit" in mn:
                        got = True
            elif name == "reg_md5_index":
                c.dyn_index[msg.index] = c.md5_names.get(msg.md5, msg.md5.hex())
        print("  => %s: %s" % (case_name, "SERVER CHAP NHAN (co reward/day_limit)" if got else "khong co reward reply (co the bi tu choi)"))
        log({"ev": "verdict", "case": case_name, "accepted": got})

    dumpf.close()
    print("\n[dump] ->", a.dump)
    return 0


if __name__ == "__main__":
    sys.exit(main())
