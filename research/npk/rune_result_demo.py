#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
rune_result_demo.py - API GIA DINH de goi dungeon_rune_attack_result (de DOC CODE).

MUC DICH: cho thay trọn luồng rap payload result + gui qua gate, dua tren code game
da giai ma (DungeonMember.dungeon_rune_attack_result) va GateConn co san.

MAC DINH = DRY-RUN: chi in payload va msgpack bytes, KHONG ket noi, KHONG gui.
Muon gui that phai them --send (chi dung tren server staging/QA, KHONG production).

Luong goc trong game (research/npk/src_decompiled/avatarmembers/DungeonMember.py):

    def dungeon_rune_attack(self, dungeon_id):
        self.callServerMethod('dungeon_rune_attack', {'dungeon_id': dungeon_id})

    def dungeon_rune_attack_return(self, dungeon_id, rewardId, copy_skin_id):
        self.dungeon_reward['dungeon_rune'] = rewardId      # luu khoa server cap

    def dungeon_rune_attack_result(self, dungeon_id, result, heroes):
        if dungeon_id > 10:           # <-- guard: chi tang 1-10 di duong nay
            return
        result['rewardId'] = self.dungeon_reward['dungeon_rune']
        self.callServerMethodDeprecated('dungeon_rune_attack_result', {
            'dungeon_id': dungeon_id,
            'result': result,         # {'iswin': bool, 'rewardId': <server cap>}
            'heroes': heroes,         # localBattleEngine.controllers[0].fightHeroUids
            'buff':  helpers.getSkinBuffList()})   # battle_ext_buff[camp1], thuong {}
"""
import argparse, json, os, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from onmyoji_netclient import GateConn, _msg, short  # tai dung transport/handshake co san


def build_result_payload(dungeon_id, iswin, reward_id, heroes, buff=None):
    """Rap dict params dung y het game. Khong gui gi."""
    if dungeon_id > 10:
        # giong guard trong game: result tang >10 bi bo, khong gui
        raise ValueError("dungeon_id > 10: tang nay khong di qua dungeon_rune_attack_result "
                         "(dung team_battle / RuneLevelLogic). Chi 1-10 hop le.")
    return {
        "dungeon_id": dungeon_id,
        "result": {"iswin": bool(iswin), "rewardId": reward_id},
        "heroes": list(heroes),
        "buff": buff if buff is not None else {},
    }


def main():
    ap = argparse.ArgumentParser(description="Demo doc code: goi dungeon_rune_attack_result")
    ap.add_argument("--session", default=os.path.join(HERE, "data", "session_live.json"))
    ap.add_argument("--dungeon-id", type=int, default=3)
    ap.add_argument("--iswin", type=int, default=1, help="1=thang, 0=thua")
    ap.add_argument("--reward-id", default="", help="ObjectId tu dungeon_rune_attack_return (cung tran)")
    ap.add_argument("--heroes", default="", help="danh sach uid, phan cach dau phay (fightHeroUids)")
    ap.add_argument("--buff", default="{}", help="JSON buff (getSkinBuffList), mac dinh {}")
    ap.add_argument("--attack-first", action="store_true",
                    help="goi dungeon_rune_attack truoc de tu lay rewardId that")
    ap.add_argument("--send", action="store_true",
                    help="GUI THAT len gate. Mac dinh KHONG gui (dry-run). Chi dung staging/QA.")
    ap.add_argument("--listen", type=float, default=15.0)
    a = ap.parse_args()

    heroes = [h.strip() for h in a.heroes.split(",") if h.strip()]
    buff = json.loads(a.buff)
    reward_id = a.reward_id

    # --- DRY-RUN: khong can session, chi rap va in ---
    if not a.send and not a.attack_first:
        if not reward_id:
            reward_id = "<rewardId tu dungeon_rune_attack_return>"
        payload = {
            "dungeon_id": a.dungeon_id,
            "result": {"iswin": bool(a.iswin), "rewardId": reward_id},
            "heroes": heroes or ["<fightHeroUids>"],
            "buff": buff,
        }
        print("=== DRY-RUN (khong gui gi) ===")
        print("method: dungeon_rune_attack_result")
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        if a.dungeon_id > 10:
            print("\n[!] dungeon_id > 10 -> game return som, khong gui. Chi 1-10 hop le.")
        try:
            import msgpack
            if "<" not in reward_id and heroes:
                print("\nmsgpack bytes =", len(msgpack.packb(payload, use_bin_type=True)))
        except Exception:
            pass
        print("\nMuon gui that: them --send (chi staging/QA). Can --reward-id va --heroes that.")
        return 0

    # --- SEND / ATTACK-FIRST: can ket noi ---
    s = json.load(open(a.session))
    entityid = bytes.fromhex(s["entityid"])
    authmsg = open(os.path.join(HERE, "data", s["authmsg_file"]), "rb").read()

    c = GateConn(s["gate_ip"], s["gate_port"], s["pubkey"])
    print("[*] gate %s:%s" % (s["gate_ip"], s["gate_port"]))
    c.handshake()
    c.resume(s["deviceid"], entityid, authmsg)

    # cho become_player roi moi goi
    ready = False
    t_end = time.time() + 60
    while time.time() < t_end:
        try:
            name, msg = c.recv_frame(timeout=max(0.1, t_end - time.time()))
        except TimeoutError:
            break
        if name == "connect_reply":
            print("[*] connect_reply type =", msg.type)
            if msg.type != 2:
                print("[!] resume that bai"); return 1
        elif name == "entity_message":
            mn = c.method_name(msg.method)
            if mn == "become_player":
                ready = True
                break
            if a.attack_first and mn == "dungeon_rune_attack_return":
                p = c.decode_params(msg.parameters)
                reward_id = p.get("rewardId")
                print("[REWARD] rewardId =", reward_id)
        elif name == "reg_md5_index":
            c.dyn_index[msg.index] = c.md5_names.get(msg.md5, msg.md5.hex())
    if not ready:
        print("[!] chua thay become_player"); return 1

    # buoc attack-first: lay rewardId that cua chinh tran nay
    if a.attack_first and not reward_id:
        print("[>] dungeon_rune_attack", {"dungeon_id": a.dungeon_id})
        c.entity_call(entityid, "dungeon_rune_attack", {"dungeon_id": a.dungeon_id})
        te = time.time() + 15
        while time.time() < te:
            try:
                name, msg = c.recv_frame(timeout=max(0.1, te - time.time()))
            except TimeoutError:
                break
            if name == "entity_message" and c.method_name(msg.method) == "dungeon_rune_attack_return":
                reward_id = c.decode_params(msg.parameters).get("rewardId")
                print("[REWARD] rewardId =", reward_id)
                break

    if not reward_id:
        print("[!] chua co rewardId (truyen --reward-id hoac dung --attack-first)"); return 1
    if not heroes:
        print("[!] chua co heroes (truyen --heroes uid1,uid2,... tu fightHeroUids RAM)"); return 1

    payload = build_result_payload(a.dungeon_id, a.iswin, reward_id, heroes, buff)
    print("=== PAYLOAD result ===")
    print(json.dumps(payload, ensure_ascii=False, indent=2))

    if not a.send:
        print("\n[dry-run] khong gui. Them --send de gui that (staging/QA).")
        return 0

    # CANH BAO: gui that
    print("\n[!!!] GUI dungeon_rune_attack_result len", s["gate_ip"])
    c.entity_call(entityid, "dungeon_rune_attack_result", payload)
    # nghe phan hoi (dungeon_client_attack_return co reward noi dung)
    te = time.time() + a.listen
    while time.time() < te:
        try:
            name, msg = c.recv_frame(timeout=max(0.1, te - time.time()))
        except TimeoutError:
            break
        if name == "entity_message":
            mn = c.method_name(msg.method)
            p = c.decode_params(msg.parameters)
            if any(k in mn for k in ("attack", "reward", "day_limit", "currency", "freeze")):
                print("[<]", mn, short(p, 240))
    return 0


if __name__ == "__main__":
    sys.exit(main())
