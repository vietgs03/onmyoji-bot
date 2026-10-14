#!/usr/bin/env python3
"""build_sweep2.py - Lap danh sach sweep dot 2 (chi API DOC, khong tham so, chua sweep).

Nguon: data/rpc_catalog.json. Loc 2 lop:
  1. class == read, no_params, chua co trong sweep_list.json
  2. class == unknown, no_params, ten bat dau bang tien to doc (get_/query_/ask_/check_/is_/...)
Sau do loai bang DENY regex (tu khoa thay doi trang thai) + DENY_EXACT (da xem tay source).
Ghi data/sweep_list2.json va in ly do loai de nguoi duyet.
"""
import json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")

READ_PREFIX = re.compile(r"^(get_|query_|ask_|check_|is_|req_get|reqGet|.*_get_|.*_query_|.*_ask_|.*_check_)")
DENY = re.compile(
    r"(clear|remove|delete|save|set_|trigger|sign|share|click|bail|giveup|give_up|logout|exit|release|"
    r"downgrade|impeach|recycle|convert|light|pray|commit|done|ready|enqueue|signup|sign_up|unreg|unsub|"
    r"take_on|take_off|select|choose|recover|invoke|combine|browse|one_key|hand_up|puzzle|call_|"
    r"draw|buy|use_|reward|recieve|receive|claim|award|bet|vote|guess_|donate|feed|upload|report|log$|"
    r"auth|token|bind|migrate|url|login|face_|identity|epay|pay|mall_|nft|h5|bbs|survey|wx_|huawei|phone|"
    r"link|notify|cdtime|kill|attack|battle|fight|challenge)", re.I)
# Da xem tay: ten nghe nhu doc nhung co tac dung phu, hoac lo token/thong tin nhay cam
DENY_EXACT = {
    "hero_growth_clear_no_include_record", "clear_hero_set_record", "guild_remove_auto_beg_info",
    "save_newest_video_data", "req_trigger_plot_chip_day_progress", "get_migrate_code",
    "get_guild_yuyue_token", "get_bbs_token", "get_huawei_little_token", "query_bind_phone",
    "query_epay_bind_info", "check_wx_bind", "get_lbs_exchange_url", "get_h5_share_url",
    "get_new_machine_share_url", "get_winter_share_url", "get_vote_share_url", "get_big_thing_share",
    "get_urs_xinyi_survey", "player_once_day_sign", "aw_sign", "lbs_sign_query",
    # duyet tay 2026-10-14: get_event_from_set = lay 1 su kien Fengmo tu pool (Quick Done dung de lam
    # nhiem vu, tieu luot EVENING_EVENT_COUNT); invitation code = ma moi ca nhan, khong can.
    "get_event_from_set", "reqGetSelfInvitationCode", "reqGetRegistedInvitationCode",
}


SRC = os.path.join(HERE, "src_decompiled")
# Dau hieu trong callback/ham goi cho thay API nay NHAN THUONG hoac DOI TRANG THAI
# (bai hoc: 'get' trong game hay nghia la 'nhan', vd cx_get_free_blue, guild_get_day_funds_bonus)
CB_DENY = re.compile(
    r"(reward|RookieRewardPanel|onBuy|rewardlst|rewardlist|show_reward|setCurDiscount|"
    r"LoadingLayer\.startLayer|addItem|getReward|award|has_free_|privilege|_rand_|rand_heroes)", re.I)


def _func_body(path, name, n=25):
    p = os.path.join(SRC, path)
    if not os.path.exists(p):
        return ""
    L = open(p, encoding="utf-8", errors="replace").read().split("\n")
    for i, l in enumerate(L):
        if re.match(r"\s*def %s\(" % re.escape(name), l):
            out = [L[i]]
            for l2 in L[i + 1:i + n]:
                if re.match(r"\s*def |# line", l2):
                    break
                out.append(l2)
            return "\n".join(out)
    return ""


def cb_flags(name, v):
    """Tra ve tu khoa nguy hiem tim thay trong ham goi + callback, hoac None."""
    texts = [_func_body(f, fn) for f, fn in v.get("sites", [])[:2]]
    for cf in v.get("cb_files", [])[:2]:
        for suf in ("_cb", "_callback", "_return", "_reply", "_result"):
            texts.append(_func_body(cf, name + suf))
    m = CB_DENY.search("\n".join(texts))
    return m.group(0) if m else None


def main():
    cat = json.load(open(os.path.join(DATA, "rpc_catalog.json")))
    done = set(json.load(open(os.path.join(DATA, "sweep_list.json"))))
    keep, rejected = [], []
    for name, v in sorted(cat.items()):
        if name in done or not v.get("no_params"):
            continue
        cls = v.get("class")
        if cls == "read":
            src = "read"
        elif cls == "unknown" and READ_PREFIX.match(name):
            src = "unknown+prefix"
        else:
            continue
        if name in DENY_EXACT:
            rejected.append((name, "deny_exact")); continue
        m = DENY.search(name)
        if m:
            rejected.append((name, "deny:" + m.group(0))); continue
        f = cb_flags(name, v)
        if f:
            rejected.append((name, "cb:" + f)); continue
        keep.append((name, src))
    out = [n for n, _ in keep]
    json.dump(out, open(os.path.join(DATA, "sweep_list2.json"), "w"), indent=1)
    print("KEEP %d" % len(out))
    for n, s in keep:
        print("  + %-45s %s" % (n, s))
    print("REJECT %d" % len(rejected))
    for n, r in rejected:
        print("  - %-45s %s" % (n, r))


if __name__ == "__main__":
    sys.exit(main())
