#!/usr/bin/env python3
"""daily_claim.py - Nhan thuong daily task QUA API (acc phu), MAC DINH dry-run.

CHI nhan thuong cho nhiem vu/moc DA HOAN THANH THAT tren server. KHONG gia lap tran,
KHONG bia iswin/record. Chi goi 3 RPC claim:
  daily_task_commit_score{id}        - nhan diem hoat dong cua 1 nhiem vu da xong
  daily_task_commit_reward{rid}      - nhan ruong moc diem (chi khi score>=nguong & chua nhan)
  daily_task_commit_act_reward{id}   - nhan thuong event

AN TOAN:
  - Mac dinh DRY-RUN: chi in RPC se gui, khong gui gi. Phai them --send moi gui that.
  - Doc trang thai that tu player1 (RAM) truoc khi claim; chi claim moc da du dieu kien.
  - Khong dong vai tran dau.

CACH DUNG:
  grab_session.ps1 (lay session)  roi:
  .venv-net/bin/python daily_claim.py            # dry-run, in ke hoach
  .venv-net/bin/python daily_claim.py --send     # thuc su gui (acc phu)
"""
import argparse, json, os, sys, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from onmyoji_netclient import DATA, GateConn

REWARD_TBL = json.load(open(os.path.join(DATA, "cdata", "cdata_en.daily_task_reward.json")))
REWARD_TBL = REWARD_TBL.get("data", REWARD_TBL)
# Uu tien bang nguong day du dump tu RAM runtime (co truong 'score')
_full = os.path.join(DATA, "daily_task_reward_full.json")
if os.path.exists(_full):
    try:
        REWARD_TBL = json.load(open(_full))
    except Exception:
        pass


def load_state():
    """Trang thai daily doc tu RAM game (player_state.json do grab_session ghi, neu co)."""
    p = os.path.join(DATA, "player_state.json")
    if not os.path.exists(p):
        return None
    return json.load(open(p))


def _unwrap(v):
    """PowerShell 5 ConvertTo-Json boc mang thanh {"value":[...],"Count":n}; go lop boc."""
    if isinstance(v, dict) and set(v) == {"value", "Count"}:
        return _unwrap(v["value"])
    if isinstance(v, list):
        out = []
        for x in v:
            x = _unwrap(x)
            out.extend(x if isinstance(x, list) else [x])
        return out
    return v


def plan(state):
    """Tra ve danh sach (rpc, params, ly_do) cho cac moc da du dieu kien va chua nhan."""
    todo = []
    score = state.get("day_active_score", 0)
    claimed = set(str(x) for x in _unwrap(state.get("daily_task_reward", [])))
    for rid, info in REWARD_TBL.items():
        if not isinstance(info, dict):
            continue
        need = info.get("score")
        if need is None:
            continue
        if rid in claimed:
            continue
        if score >= need:
            todo.append(("daily_task_commit_reward", {"rid": int(rid)},
                         "score %d >= nguong %d, moc %s chua nhan" % (score, need, rid)))
    # diem tung nhiem vu da hoan thanh nhung chua commit score
    for tid, tdata in state.get("daily_task", {}).items():
        if isinstance(tdata, dict) and tdata.get("finished") and not tdata.get("score_taken"):
            todo.append(("daily_task_commit_score", {"id": int(tid)},
                         "nhiem vu %s hoan thanh, chua nhan diem" % tid))
    return todo


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--send", action="store_true", help="THUC SU gui RPC (mac dinh chi dry-run)")
    ap.add_argument("--gap", type=float, default=2.0)
    a = ap.parse_args()

    state = load_state()
    if state is None:
        print("[!] Chua co data/player_state.json. Chay grab_session.ps1 (ban co dump daily_task) truoc.")
        print("    Dry-run khong co trang thai -> khong lap ke hoach duoc.")
        return 1

    todo = plan(state)
    print("=== KE HOACH (%d RPC) ===" % len(todo))
    for rpc, params, reason in todo:
        print("  %-28s %-22s  # %s" % (rpc, json.dumps(params), reason))
    if not todo:
        print("  (khong co moc nao du dieu kien de nhan)")
        return 0

    if not a.send:
        print("\n[DRY-RUN] Khong gui gi. Them --send de gui that (acc phu).")
        return 0

    # gui that
    s = json.load(open(os.path.join(DATA, "session.json")))
    eid = bytes.fromhex(s["entityid"])
    auth = open(os.path.join(DATA, s["authmsg_file"]), "rb").read()
    c = GateConn(s["gate_ip"], s["gate_port"], s["pubkey"], verbose=True)
    c.handshake(); c.resume(s["deviceid"], eid, auth)
    rtype = None; t0 = time.time()
    while time.time() - t0 < 10:
        n, m = c.recv_frame(10)
        if n == "connect_reply":
            rtype = m.type; break
    if rtype != 2:
        print("[!] resume that bai (type=%s). Dung lai." % rtype); return 1
    time.sleep(2)  # nhan dot sync
    for rpc, params, reason in todo:
        print("[>] %s %s" % (rpc, params))
        c.entity_call(eid, rpc, params)
        t_end = time.time() + a.gap
        while time.time() < t_end:
            try:
                n, m = c.recv_frame(max(0.1, t_end - time.time()))
            except Exception:
                break
            if n == "entity_message":
                mn = c.method_name(m.method)
                if mn.startswith("daily_task_commit"):
                    print("    <= %s %s" % (mn, c.decode_params(m.parameters)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
