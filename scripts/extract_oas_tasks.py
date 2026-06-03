#!/usr/bin/env python3
"""
extract_oas_tasks.py - Trich CHUC NANG GAME tu OAS de hoc game co gi + cach tu dong hoa.

OAS (research/OAS) la bot Onmyoji CN lon nhat. Moi thu muc tasks/<X> = 1 che do/hoat dong game.
Ta trich:
  - ten task + mo ta (tu config.py description / README)
  - cac TUY CHON (Field) -> cho biet che do co gi cau hinh
  - so buoc/template -> do phuc tap
  - flow (tu script_task.py docstring/comment neu co)

Ra: knowledge/oas_features.json  (de nap vao KB + vector DB)
"""
import os, re, json, glob, ast

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OAS = os.path.join(ROOT, "research", "OAS", "tasks")
OUT = os.path.join(ROOT, "knowledge", "oas_features.json")

# OAS lan code AzurLane - loai cac task khong phai Onmyoji
SKIP = {"Component", "Utils", "Script", "GameUi", "General", "base_task.py",
        "GotoMain", "Restart"}

# map ten task -> ten game de hieu (EN, theo wiki Global)
NICE = {
    "Exploration": "Exploration / Soul farming (探索)",
    "RealmRaid": "Realm Raid (突破)",
    "SoulsTidy": "Souls / Mitama auto-sort & sell (御魂整理)",
    "GoryouRealm": "Goryou Realm (御灵)",
    "Duel": "Duel / Hyakki Yakou battles? (斗技/演武)",
    "AbyssShadows": "Abyss Shadows (业原火)",
    "Hunt": "Wanted/Hunt (狩猎/觅契)",
    "FrogBoss": "Frog Boss betting (青蛙boss)",
    "Dokan": "Dokan / Area Boss (道馆)",
    "EternitySea": "Eternity Sea (永生之海)",
    "EvoZone": "Evolve Zone (觉醒副本)",
    "Secret": "Secret Zone (秘闻副本)",
    "SixRealms": "Six Realms (永生之海/月之海 marks)",
    "TrueOrochi": "True Orochi (真八岐大蛇)",
    "Orochi": "Orochi (八岐大蛇)",
    "OrochiMoans": "Orochi groan/assist",
    "DemonEncounter": "Demon Encounter (鬼王)",
    "DemonRetreat": "Demon Retreat",
    "AreaBoss": "Area Boss (地域鬼王)",
    "GoldYoukai": "Gold Youkai (黄金妖怪)",
    "ExperienceYoukai": "Experience Youkai (经验妖怪)",
    "RealmRaid2": "Realm Raid",
    "Pets": "Pets feeding (宠物)",
    "Quiz": "Daily Quiz (逢魔密信/答题)",
    "WantedQuests": "Wanted Quests (悬赏封印)",
    "DailyTrifles": "Daily tasks (日常)",
    "WeeklyTrifles": "Weekly tasks (周常)",
    "CollectiveMissions": "Collective/Guild missions",
    "GuildBanquet": "Guild Banquet (寮宴会)",
    "GuildActivityMonitor": "Guild activity monitor",
    "Delegation": "Delegation (式神委派)",
    "KekkaiActivation": "Kekkai/Barrier activation (结界突破)",
    "KekkaiUtilize": "Kekkai utilize (结界寄养)",
    "RealmRaidPVP": "Realm Raid PvP",
    "BondlingFairyland": "Bonding Fairyland (契灵之境)",
    "FallenSun": "Fallen Sun event",
    "Sougenbi": "Sougenbi (草原火/festival)",
    "Nian": "Nian event",
    "Tako": "Tako event",
    "FloatParade": "Float Parade (花车巡游)",
    "Hyakkiyakou": "Hyakkiyakou (百鬼夜行)",
    "RichMan": "Rich Man / shopping (富豪/商店)",
    "MysteryShop": "Mystery Shop (神秘商店)",
    "KittyShop": "Kitty Shop (猫店/集市)",
    "MemoryScrolls": "Memory Scrolls (绘卷)",
    "TalismanPass": "Talisman Pass (御札任务/daily)",
    "DyeTrials": "Dye Trials (染色)",
    "MetaDemon": "Meta Demon",
    "RyouToppa": "Ryou Toppa / Liao breakthrough",
    "HeroTest": "Hero Test (式神觉醒材料)",
    "ActivityShikigami": "Activity Shikigami (活动式神)",
    "FindJade": "Find Jade (勾玉/友情邀请)",
    "AutoCheckinBigGod": "Auto check-in (神社签到)",
    "GlobalGame": "Global server helpers (国际服)",
}


def parse_fields(py):
    """Lay cac Field(...) trong config.py: ten + title + description."""
    fields = []
    for m in re.finditer(r"(\w+)\s*:\s*[\w\[\]]+\s*=\s*Field\((.*?)\)", py, re.S):
        name, args = m.group(1), m.group(2)
        title = re.search(r"title=['\"](.+?)['\"]", args)
        desc = re.search(r"description=['\"](.+?)['\"]", args)
        default = re.search(r"default=([^,)]+)", args)
        fields.append({
            "field": name,
            "title": title.group(1) if title else None,
            "desc": desc.group(1) if desc else None,
            "default": default.group(1).strip() if default else None,
        })
    return fields


def task_summary(tdir):
    name = os.path.basename(tdir)
    cfg = os.path.join(tdir, "config.py")
    fields = parse_fields(open(cfg, encoding="utf-8", errors="ignore").read()) if os.path.exists(cfg) else []
    # so template / ocr region
    n_img = sum(len(json.load(open(p))) for p in glob.glob(f"{tdir}/**/image.json", recursive=True)) if glob.glob(f"{tdir}/**/image.json", recursive=True) else 0
    n_ocr = sum(len(json.load(open(p))) for p in glob.glob(f"{tdir}/**/ocr.json", recursive=True)) if glob.glob(f"{tdir}/**/ocr.json", recursive=True) else 0
    n_png = len(glob.glob(f"{tdir}/**/*.png", recursive=True))
    # script flow: lay ten cac def trong script_task.py
    steps = []
    st = os.path.join(tdir, "script_task.py")
    if os.path.exists(st):
        src = open(st, encoding="utf-8", errors="ignore").read()
        steps = re.findall(r"def (\w+)\(self", src)
    return {
        "task": name,
        "name": NICE.get(name, name),
        "options": [f for f in fields if f["title"] or f["desc"]],
        "templates": n_img, "ocr_regions": n_ocr, "images": n_png,
        "script_methods": steps[:30],
    }


def main():
    out = []
    for d in sorted(glob.glob(f"{OAS}/*")):
        if not os.path.isdir(d):
            continue
        name = os.path.basename(d)
        if name in SKIP:
            continue
        try:
            out.append(task_summary(d))
        except Exception as e:
            print("  err", name, e)
    json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"trich {len(out)} chuc nang game -> {OUT}\n")
    for t in sorted(out, key=lambda z: -z["templates"]):
        print(f"  {t['name']:45} | {t['templates']:>3} tmpl, {t['ocr_regions']:>2} ocr, {len(t['options'])} opt")


if __name__ == "__main__":
    main()
