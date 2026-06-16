#!/usr/bin/env python3
"""onmyoji.interface.mcp_server - MCP server (interface adapter cho jcode/Claude).

Day la 1 "interface adapter" (cung cap voi cli.py), expose cac use case ra
ngoai duoi dang MCP tool de harness agent (jcode/Claude) goi truc tiep.

NGUYEN TAC KIEN TRUC (Clean Architecture):
- File nay CHI duoc phep di qua Container -> UseCase -> Port.
- KHONG import cv2, world_model, vectordb, perception, control_client, scripts/,
  automation/. Tat ca chi tiet do nam sau Port, do Container wiring.
- Doi tang EYE (python/rust/fake) chi sua Container, file nay khong doi.

Container la singleton (1 instance/process, lazy) de tranh reimport cv2/sklearn
(~3s) moi tool call. Server giu state qua nhieu request.

Dung:
    # voi game that (Windows + game chay)
    .venv/bin/python -m onmyoji.interface.mcp_server

    # test offline khong can game
    ONMYOJI_EYE=fake .venv/bin/python -m onmyoji.interface.mcp_server

Chon impl Eye qua env ONMYOJI_EYE (python | rust | fake), mac dinh "python".
"""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from mcp.server.fastmcp import FastMCP

from onmyoji.domain.entities import Action
from onmyoji.interface.container import Container

mcp = FastMCP("onmyoji")

# --- Container singleton (lazy, 1 instance/process) ---------------------------
_container: Container | None = None


def get_container() -> Container:
    """Tra ve Container dung chung (tao lan dau, sau do tai su dung).

    Lazy de viec import nang (cv2/sklearn) chi xay ra 1 lan trong vong doi
    process, khong lap lai moi tool call.
    """
    global _container
    if _container is None:
        _container = Container()
    return _container


# --- MCP tools ----------------------------------------------------------------
# Moi tool di qua Container -> UseCase -> Port. KHONG truy cap chi tiet ben duoi.


def _dhash_bitdiff(a: str | None, b: str | None) -> int:
    """So bit khac giua 2 dhash (chuoi '0'/'1' cung do dai). 999 neu khong so duoc.
    Dung de doi man ON DINH (dhash ngung doi) - khong import perception (Clean Arch)."""
    if not a or not b or len(a) != len(b):
        return 999
    return sum(1 for x, y in zip(a, b) if x != y)


def _wait_settle(eye, need: int = 3, max_poll: int = 18, poll_s: float = 0.35):
    """Doi man ON DINH (dhash ngung doi <=2 bit qua `need` lan lien tiep) roi tra
    Observation cuoi. Tranh bat trung giua animation chuyen canh (cong xoay sang
    KHAC is_loading man toi). Tra (obs, settled)."""
    import time as _t
    prev = None
    stable = 0
    obs = None
    observe_fn = eye.observe_nav if hasattr(eye, "observe_nav") else eye.observe
    for _ in range(max_poll):
        obs = observe_fn()
        dh = getattr(obs, "dhash", None)
        if prev is not None and _dhash_bitdiff(dh, prev) <= 2:
            stable += 1
        else:
            stable = 0
        prev = dh
        if stable >= need:
            return obs, True
        _t.sleep(poll_s)
    return obs, False


@mcp.tool()
def observe() -> dict:
    """Chup + phan tich man hinh game HIEN TAI, tra ve Observation.

    Dung khi can biet dang o man hinh nao, co nhung button nao, toa do button,
    trang thai loading/alive, tai nguyen (gold/ap/jade). Day la buoc DAU TIEN
    truoc khi quyet dinh click gi.

    Tra ve dict Observation: {ts, state_id, loading, size{w,h},
    buttons[{x,y,w,h,score,text}], alive, resources{gold,ap,jade}, frame_path}.
    """
    ctx = get_container().perceive().execute()
    return ctx.observation.to_dict()


@mcp.tool()
def wait_stable() -> dict:
    """Doi man hinh ON DINH (het loading + du button) roi tra Observation.

    Dung NGAY SAU mot hanh dong lam chuyen man (click vao/loading), de chac chan
    man hinh moi da load xong truoc khi doc button hay click tiep. Tranh click
    nham trong luc dang loading.

    Tra ve dict Observation (giong observe()).
    """
    obs = get_container().wait_stable().execute()
    return obs.to_dict()


@mcp.tool()
def observe_marked() -> dict:
    """Chup man hinh + danh so cac element clickable (Set-of-Mark) cho BAN NHIN.

    Dung khi can NHIN man hinh de quyet dinh click gi (man moi/la, hoac observe()
    khong du). Tra ve:
      - marked_path: duong dan anh DA DANH SO (mo anh nay de NHIN cac so tren nut).
      - marks: [{id, cx, cy, w, h, score, label?}] - id tren anh -> toa do (cx,cy).
        Mark co 'label' = DA HOC tu lan truoc (ve mau XANH tren anh) -> tin cao,
        click thang. Mark khong label = CV ung vien (mau DO) -> verify truoc.
      - state_id, page, loading, size nhu observe().

    LUU Y QUAN TRONG: CV marks (do) CO THE SOT (vd nut Explore/Summon phuc tap)
    HOAC co RAC. Hay MO anh marked_path de NHIN, doi chieu:
      - Mark XANH (da hoc) -> click_mark(id) ngay.
      - Mark DO dung element -> click_mark(id).
      - Element BI SOT (khong co so) -> click_at(x,y) (tu snap) + learn_element de
        LAN SAU khong sot nua (he thong KHOANH VUNG nho lai).
      - Mark la RAC -> bo qua.
    """
    obs = get_container().eye.observe_som(with_page=True)
    return _merge_verified(obs)


def _merge_verified(obs) -> dict:
    """Gop verified elements (da hoc) vao ket qua SoM: them marks (co 'label') +
    ve box XANH cho chung tren anh marked. Tra DICT cho agent.

    QUAN TRONG (tranh khoanh vung tum lum): CHI gop verified khi man duoc XAC NHAN
    chac chan:
      - dhash match 1 state da hoc (hamming<=12), HOAC
      - page detector ra 1 page (landmark robust).
    Man LA (dhash khong match + page=none, vd popup) -> KHONG gop verified (state
    moi/dong khong dang tin) + bao agent 'man la, hay NHIN'. Tranh element 'mo coi'
    khoanh sai cho."""
    d = obs.to_dict()
    world = get_container().world
    # NEO man theo do ben nhat: dhash match -> page->label->node -> (LA: confirmed
    # False). Page (landmark) khong troi nhu dhash man dong -> verified KHONG phan manh.
    if world is None:
        d["screen_confirmed"] = False
        return d
    sid, confirmed = world.canonical_state(obs.dhash, obs.state_id, obs.page)
    d["screen_confirmed"] = confirmed
    if not confirmed:
        # man LA -> bao agent NHIN, KHONG gop verified (tranh khoanh sai)
        d["screen_hint"] = ("Man LA (dhash chua hoc + khong khop page nao). "
                            "Hay NHIN anh marked de nhan dien; element CV la UNG VIEN.")
        return d
    learned = world.elements_for(sid)
    if not learned:
        return d
    marks = list(d.get("marks", []))
    next_id = max((m["id"] for m in marks), default=0) + 1
    added = []
    for e in learned:
        cx, cy = int(e["cx"]), int(e["cy"])
        dup = next((m for m in marks
                    if abs(m["cx"] - cx) <= 18 and abs(m["cy"] - cy) <= 18), None)
        if dup is not None:
            dup["label"] = e.get("label", "")
            continue
        m = {"id": next_id, "cx": cx, "cy": cy, "x": cx - 22, "y": cy - 22,
             "w": 44, "h": 44, "score": 1.0, "label": e.get("label", "")}
        marks.append(m)
        added.append(m)
        next_id += 1
    d["marks"] = marks
    if added and d.get("marked_path"):
        _draw_verified(d["marked_path"], added)
    return d


def _draw_verified(path, added):
    """Ve box XANH + label cho cac element da hoc len anh marked (cv2)."""
    try:
        import cv2
        img = cv2.imread(path)
        if img is None:
            return
        for m in added:
            cv2.rectangle(img, (m["x"], m["y"]), (m["x"] + m["w"], m["y"] + m["h"]),
                          (0, 220, 0), 2)
            cv2.putText(img, f"{m['id']}:{m.get('label','')}",
                        (m["x"], max(12, m["y"] - 4)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 220, 0), 2)
        cv2.imwrite(path, img)
    except Exception:  # noqa: BLE001
        pass


@mcp.tool()
def click_mark(mark_id: int) -> dict:
    """Click vao element theo SO (mark id) tu observe_marked().

    Tien loi + CHINH XAC: ban chi can chon SO nhin thay tren anh marked, he thong
    tu tra toa do tam (cx,cy) chinh xac de click. Tranh phai uoc luong pixel.

    Tham so:
        mark_id: so tren anh marked (tu observe_marked().marks[].id).
    Tra ve dict Observation MOI sau click. Loi neu mark_id khong ton tai (hay
    observe_marked() lai roi chon so dung).
    """
    eye = get_container().eye
    obs = eye.observe_som()
    mark = next((m for m in obs.marks if m.id == mark_id), None)
    if mark is None:
        ids = [m.id for m in obs.marks]
        return {"error": f"mark_id {mark_id} khong ton tai. Cac id co: {ids}",
                "marks": [m.__dict__ if hasattr(m, "__dict__") else m for m in obs.marks]}
    return get_container().act().execute(Action.click(mark.cx, mark.cy)).to_dict()


@mcp.tool()
def click_at(x: int, y: int, snap: bool = True, screen: str = "") -> dict:
    """Click tai toa do (x,y) ban UOC LUONG tu anh, voi SNAP tu dong (mac dinh).

    Dung khi element BI SOT (khong co mark trong observe_marked) -> ban nhin anh,
    uoc toa do tho, goi click_at(x,y). He thong tu SNAP ve tam element gan nhat
    (trong ban kinh ~40px) -> click chinh xac du ban uoc hoi lech. snap=False de
    click dung (x,y) khong chinh.

    GHI EDGE (ban do): click_at tu dong ghi canh "o man <screen/nguon> click (x,y)
    -> toi man <dich>" vao world graph (neu CA HAI dau nhan dien duoc) -> goto()/
    bfs_path dung lai duong nay. Day la cach graph TU LON khi kham pha.

    Tham so:
        x, y: toa do uoc luong tu anh marked/goc.
        snap: True (mac dinh) = snap ve element gan nhat; False = click nguyen xy.
        screen: (tuy chon) ten man NGUON (vd 'RealmRaid') de neo edge chac chan khi
            man nguon DONG khong page. Bo trong -> tu xac dinh qua dhash/page.
    Tra ve dict Observation MOI sau click + 'edge' (neu ghi duoc).
    """
    c = get_container()
    eye = c.eye
    world = c.world
    sx, sy = x, y
    if snap and hasattr(eye, "snap"):
        sx, sy, _ = eye.snap(x, y)
    # NGUON: xac dinh canonical state truoc khi click (de ghi edge)
    src_sid = None
    if world is not None:
        try:
            src_obs = eye.observe_nav() if hasattr(eye, "observe_nav") else None
            if src_obs is None:
                src_obs = eye.observe()
            # neu agent khai bao screen -> neo qua label (man dong khong page)
            if screen and hasattr(world, "state_for_label"):
                src_sid = world.state_for_label(screen)
            if src_sid is None and hasattr(world, "canonical_state"):
                # can page de neo man dong -> observe co page
                src_pg = eye.observe_page() if hasattr(eye, "observe_page") else src_obs
                src_sid, _ = world.canonical_state(src_obs.dhash, src_obs.state_id,
                                                   getattr(src_pg, "page", None))
        except Exception:  # noqa: BLE001
            src_sid = None
    # CLICK
    obs_after = c.act().execute(Action.click(sx, sy))
    # DICH + ghi edge (chi khi ca hai nhan dien duoc -> tranh edge rac).
    # DOI man ON DINH truoc (animation chuyen canh sang -> observe ngay se bat
    # trung loading frame -> dst khong nhan dien -> mat edge). Sau on dinh moi
    # observe co page de neo dst chac chan + tra ve cho agent man THAT.
    d = obs_after.to_dict()
    edge = None
    if world is not None and hasattr(world, "record_transition"):
        try:
            _wait_settle(eye)
            dst_obs = eye.observe_page() if hasattr(eye, "observe_page") else obs_after
            d = dst_obs.to_dict()  # tra man da on dinh (khong phai loading frame)
            if src_sid is not None and hasattr(world, "canonical_state"):
                dst_sid, dst_conf = world.canonical_state(
                    dst_obs.dhash, dst_obs.state_id, getattr(dst_obs, "page", None))
                if dst_sid is not None and dst_conf and dst_sid != src_sid:
                    world.record_transition(src_sid, Action.click(sx, sy), dst_sid)
                    if hasattr(world, "save"):
                        world.save()
                    edge = {"from": src_sid, "click": [sx, sy], "to": dst_sid,
                            "from_label": world.resolve_label(src_sid) if hasattr(world, "resolve_label") else None,
                            "to_label": world.resolve_label(dst_sid) if hasattr(world, "resolve_label") else None}
        except Exception:  # noqa: BLE001
            edge = None
    if edge:
        d["edge"] = edge
    return d


@mcp.tool()
def probe_scroll(amp: int = 200) -> dict:
    """KIEM TRA man hien tai co KEO/SCROLL duoc khong (ngang + doc) - active probe.

    Cach SENIOR (thay vi doan): EYE tu drag thu giua man ngang roi doc, do man
    DICH bao nhieu px, sau do tu KEO VE (khong lam xe dich man). Dung khi gap man
    co the con content AN ngoai khung: ban do Exploration (keo ngang/doc xem het
    chuong/khu vuc), list menu (Shop, Souls, Shikigami keo doc xem het muc).

    Tra ve:
      - movable: True neu man keo duoc (ngang HOAC doc).
      - can_x / can_y: keo duoc ngang / doc rieng.
      - dx, dy: man dich bao nhieu px khi keo (do lon = muc scroll).
      - dx_score, dy_score, diff: do tin cay.

    CACH DUNG: sau khi observe_marked 1 man la, neu nghi con content ngoai khung
    -> probe_scroll(). can_x/can_y=True -> drag(...) de lo content moi -> observe
    tiep -> hoc them element. Giup kham pha HET man thay vi bo sot.

    Tham so amp: bien do keo thu (px, mac dinh 200). Man nho dung 120-150.
    """
    eye = get_container().eye
    if not hasattr(eye, "probe"):
        return {"ok": False, "error": "EYE khong ho tro probe (chi RustEye)"}
    p = eye.probe(int(amp))
    if not p:
        return {"ok": False, "error": "probe that bai (game tat / khong drag duoc)"}
    p["ok"] = True
    # goi y hanh dong cho agent
    hints = []
    if p.get("can_x"):
        hints.append("keo NGANG duoc -> drag de xem content trai/phai")
    if p.get("can_y"):
        hints.append("keo DOC duoc -> drag de xem content tren/duoi")
    p["hint"] = ("; ".join(hints) if hints
                 else "man KHONG keo duoc (content vua khung) -> khong can scroll")
    return p


@mcp.tool()
def learn_element(label: str, x: int, y: int, screen: str = "") -> dict:
    """GHI NHO 1 element ban DA XAC NHAN bang mat (vision) cho man hinh hien tai.

    Self-learning: sau khi ban NHIN anh (observe_marked) va xac dinh "cho (x,y) la
    nut <label>", goi ham nay de luu vao ban do. LAN SAU gap lai man nay, he thong
    biet ngay <label> o dau - KHONG can CV/ban nhin lai. Day la cach bot tu hoc
    game thay vi hardcode.

    Tham so:
        label: ten ngu nghia (vd 'Summon', 'Explore', 'Shop', 'back').
        x, y: toa do element (nen lay tu mark.cx/cy hoac sau khi snap).
        screen: (KHUYEN DUNG cho man DONG khong co page) ten man chua element nay
            (vd 'Town', 'Exploration'). Neu da learn_screen(screen) truoc do,
            element se neo vao DUNG node logic do - tranh PHAN MANH khi dhash man
            dong troi giua cac lan goi. Bo trong -> neo theo dhash/page (du cho
            man tinh hoac man co page anchor nhu HOME/Soul).
    Tra ve: {ok, state_id, label, learned: [cac element da hoc cho man nay]}.
    """
    c = get_container()
    world = c.world
    if world is None:
        return {"ok": False, "error": "WorldModel khong kha dung"}
    # NEO ON DINH (tranh phan manh) theo thu tu do BEN nhat:
    #   1. screen (agent khai bao ro) -> node co label do (man dong khong page van
    #      hoi tu - vd Town). Day la neo MANH NHAT vi agent chu dong dạy.
    #   2. canonical_state: dhash-match -> page->label->node (HOME/Soul co page).
    # Man dong KHONG page (Town): dhash troi 30-40 bit moi frame -> screen anchor
    # la cach duy nhat dung (dhash threshold se nham man).
    obs = c.eye.observe_som(with_page=True)
    sid = None
    if screen and hasattr(world, "state_for_label"):
        sid = world.state_for_label(screen)
    if sid is not None:
        confirmed = True  # agent khai bao man -> tin
    else:
        sid, confirmed = world.canonical_state(obs.dhash, obs.state_id, obs.page)
    # snap toa do ve element that cho chuan
    sx, sy = x, y
    if hasattr(c.eye, "snap"):
        sx, sy, _ = c.eye.snap(x, y)
    world.record_element(sid, sx, sy, label, dhash=obs.dhash)
    # neo node theo page-label (neu co) de cac frame sau hoi tu -> recall on dinh
    page_label = world.resolve_page(obs.page) if obs.page else None
    if page_label and hasattr(world, "label_state"):
        cur = world.resolve_label(sid) if hasattr(world, "resolve_label") else None
        if not cur:
            world.label_state(sid, page_label, dhash=obs.dhash)
    if hasattr(world, "save"):
        world.save()
    out = {"ok": True, "state_id": sid, "page": obs.page, "label": label,
           "saved_at": [sx, sy], "screen_confirmed": confirmed,
           "learned": world.elements_for(sid)}
    if not confirmed:
        out["warning"] = ("Man chua xac nhan (dhash moi + page=none, vd popup dong). "
                          "Da luu nhung dhash co the khong lap lai -> element co the "
                          "khong xuat hien lai. Nen hoc o man ON DINH (co page/da biet).")
    return out


@mcp.tool()
def click(x: int, y: int) -> dict:
    """Click chuot trai tai toa do (x, y) tren man hinh game.

    Dung de bam vao button/diem da biet toa do (vd tu observe()). Tra ve
    Observation MOI ngay sau khi click de biet ket qua.

    Tham so:
        x, y: toa do pixel trong khung game (goc tren-trai = 0,0).
    Tra ve dict Observation.
    """
    obs = get_container().act().execute(Action.click(x, y))
    return obs.to_dict()


@mcp.tool()
def polite_click(x: int, y: int) -> dict:
    """Click "lich su" tai (x, y): co do tre/nguoi-hoa de tranh bi phat hien.

    Giong click() nhung mo phong thao tac nguoi that (timing/jitter) - dung khi
    can an toan hon cho cac hanh dong lap lai. Tra ve Observation MOI.

    Tham so:
        x, y: toa do pixel trong khung game.
    Tra ve dict Observation.
    """
    obs = get_container().act().execute(Action.polite_click(x, y))
    return obs.to_dict()


@mcp.tool()
def drag(x0: int, y0: int, x1: int, y1: int) -> dict:
    """Keo (drag) chuot tu (x0, y0) toi (x1, y1).

    Dung de cuon danh sach, keo thanh truot, hay di chuyen vat the trong game.
    Tra ve Observation MOI sau khi keo.

    Tham so:
        x0, y0: diem bat dau keo.
        x1, y1: diem ket thuc keo.
    Tra ve dict Observation.
    """
    obs = get_container().act().execute(Action.drag(x0, y0, x1, y1))
    return obs.to_dict()


@mcp.tool()
def key(key: str) -> dict:
    """Nhan 1 phim (key) tren ban phim (vd "esc", "enter", "space").

    Dung khi can dong dialog (esc), xac nhan (enter)... thay vi click. Tra ve
    Observation MOI sau khi nhan phim.

    Tham so:
        key: ten phim (chuoi), vd "esc", "enter", "space", "f1".
    Tra ve dict Observation.
    """
    obs = get_container().act().execute(Action.key_press(key))
    return obs.to_dict()


@mcp.tool()
def goto(label: str) -> dict:
    """Tu dong dieu huong toi man hinh co nhan (label) cho truoc.

    Dung path da hoc trong WorldModel de di tu man hien tai toi man dich (vd
    "HOME", "SHOP"). Tu dong click qua cac buoc. Dung khi muon "ve trang chu"
    hay "toi cua hang" ma khong can biet duong di cu the.

    Tham so:
        label: nhan logic cua man hinh dich.
    Tra ve {"goto": label, "ok": bool} - ok=True neu toi noi.
    """
    ok = get_container().navigate().execute(label)
    return {"goto": label, "ok": ok}


@mcp.tool()
def ask_kb(query: str, k: int = 5) -> list[dict]:
    """Tra cuu tri thuc game (knowledge base / vector search) bang ngon ngu tu nhien.

    Dung khi can biet luat choi/meta/huong dan (vd "lam sao farm soul nhanh",
    "cong thuc ghep thuc than X"). Tra ve cac doan tri thuc lien quan nhat.

    Tham so:
        query: cau hoi/tu khoa tieng Viet hoac tieng Anh.
        k: so luong ket qua mong muon (mac dinh 5).
    Tra ve list dict document lien quan.
    """
    return get_container().ask_knowledge().execute(query, k=k)


@mcp.tool()
def learn_screen(label: str, function: str, farms: str = "", note: str = "") -> dict:
    """DAY HE THONG ve man hinh hien tai (sau khi BAN da NHIN va hieu no la gi).

    Self-learning cot loi: khi gap man MOI (observe_marked tra screen_confirmed=
    False), ban NHIN anh -> hieu "day la man gi, lam gi, farm gi" -> goi ham nay.
    He thong luu 2 noi:
      1. NGU NGHIA -> vector DB (lan sau ask_kb tim duoc 'man X lam gi/farm gi').
      2. NHAN DIEN -> world_model gan label cho dhash man nay (lan sau observe
         tu biet dang o '<label>', screen_confirmed=True).
    -> Lan sau gap lai KHONG can NHIN/hoi lai nua, thich nghi tot hon.

    Tham so:
        label: ten ngan cho man (vd 'Soul Zone', 'Courtyard Affairs').
        function: chuc nang man lam gi (vd 'nhan thuong daily', 'farm ngoc hon').
        farms: (tuy chon) farm/thu duoc gi o day (vd 'ngoc hon, kim tien').
        note: (tuy chon) ghi chu them (nut quan trong, luu y).
    Tra ve: {ok, label, state_id, doc_id, learned_kb}.
    """
    c = get_container()
    world = c.world
    knowledge = c.knowledge
    # 1) xac dinh state hien tai + NEO ON DINH (page anchor) de gan label nhan dien.
    # Man dong dhash troi -> canonical_state hoi tu cac frame ve cung node logic.
    obs = c.eye.observe_som(with_page=True)
    sid, _confirmed = world.canonical_state(obs.dhash, obs.state_id, obs.page) if world else (obs.state_id, False)
    # CHONG ALIAS (review thuat toan): neu man nay da co label CHUAN (qua page anchor
    # hoac dhash da hoc) KHAC voi `label` agent dua -> dung ten CHUAN da co, tranh
    # tao 2 ten cho 1 man (lam dut mach bfs_path). Bao agent biet da chuan hoa.
    canon_label = None
    if world is not None:
        if obs.page and hasattr(world, "resolve_page"):
            canon_label = world.resolve_page(obs.page)
        if not canon_label and hasattr(world, "resolve_label"):
            canon_label = world.resolve_label(sid)
    aliased_from = None
    if canon_label and canon_label != label:
        aliased_from = label
        label = canon_label  # dung ten chuan da ton tai
    # 2) NGU NGHIA -> vector DB (doc_id theo label de cap nhat duoc)
    text = f"Man hinh game '{label}': {function}."
    if farms:
        text += f" Farm/thu duoc: {farms}."
    if note:
        text += f" Ghi chu: {note}."
    doc_id = f"screen:{label.lower().replace(' ', '_')}"
    learned_kb = {}
    if knowledge is not None:
        learned_kb = knowledge.learn(title=label, text=text, doc_type="screen",
                                     doc_id=doc_id, meta={"state_id": sid, "farms": farms})
    # 3) NHAN DIEN -> world_model gan label cho dhash (tao node neu chua co)
    if world is not None and hasattr(world, "label_state"):
        world.label_state(sid, label, desc=function, dhash=obs.dhash)
        if hasattr(world, "save"):
            world.save()
    return {"ok": True, "label": label, "state_id": sid, "doc_id": doc_id,
            "function": function, "farms": farms,
            "learned_kb": bool(learned_kb),
            **({"normalized_from": aliased_from,
                "note_alias": f"Man nay da co ten chuan '{label}' -> dung ten do (bo '{aliased_from}') de khong dut mach ban do."}
               if aliased_from else {})}


@mcp.tool()
def explore_status() -> dict:
    """Tong quan tien do KHAM PHA ban do game + GOI Y di dau tiep.

    Dung de kham pha co he thong (di het cay man hinh tu HOME). Tra ve:
      - stats: {states, labeled, described, edges, frontier_screens,
                frontier_untried_total} - da map bao nhieu, con bao nhieu.
      - current: man hien tai {state_id, label, untried_here:[{cx,cy,label}]}.
      - frontier: [{label, sid, untried}] - cac man CON element chua thu (sap
        theo so element chua di giam dan). Di toi day de map tiep.
      - suggestion: goi y hanh dong tiep theo.

    CACH DUNG (vong kham pha):
      1. explore_status() -> xem current.untried_here.
      2. Neu CON untried_here: click element do (click_mark/click_at) -> sang man
         moi -> observe_marked -> NHIN -> learn_screen + learn_element.
      3. Neu HET untried_here: goto(frontier[0].label) roi lam tiep.
      4. Lap den khi frontier rong = da phu het ban do.
    """
    c = get_container()
    world = c.world
    if world is None:
        return {"ok": False, "error": "WorldModel khong kha dung"}
    # man hien tai
    obs = c.eye.observe_som(with_page=True)
    sid, _confirmed = world.canonical_state(obs.dhash, obs.state_id, obs.page)
    label = world.resolve_label(sid) if hasattr(world, "resolve_label") else None
    untried_here = world.untried_elements(sid)
    frontier = world.frontier()
    stats = world.explore_stats()
    if untried_here:
        sug = (f"Man nay con {len(untried_here)} element chua thu -> click 1 cai "
               f"(click_at theo cx,cy) de map tiep.")
    elif not label:
        sug = ("Man nay CHUA hoc -> observe_marked + NHIN + learn_screen/learn_element "
               "truoc khi di tiep.")
    elif frontier:
        sug = (f"Man nay da het element -> goto('{frontier[0]['label']}') "
               f"(con {frontier[0]['untried']} element chua thu) de map tiep.")
    else:
        sug = "Frontier rong -> da phu het ban do da nhan dien. Tiep tuc tim man moi neu can."
    return {"ok": True, "stats": stats,
            "current": {"state_id": sid, "label": label, "untried_here": untried_here},
            "frontier": frontier[:8], "suggestion": sug}


# ============================================================================
# AUTONOMY tools (4 tang). Xem AUTONOMY_DESIGN.md.
# ============================================================================


@mcp.tool()
def verify_outcome() -> dict:
    """KIEM TRA ket qua man hien tai (thang/thua/loading/reward) - tang feedback.

    Dung sau khi danh xong de biet ket qua (vd kiem tra battle VICTORY/DEFEAT).
    Dua page detector (landmark robust) + trang thai loading. Tra Verdict:
    {outcome, confidence, detail, resources}. outcome:
      victory/defeat/in_battle/loading/reward/no_resource/unknown.
    LUU Y: can co page template man Victory/Defeat (add_live_page) de nhan dien
    chac. Chua co -> tra unknown (an toan, khong doan bua)."""
    return get_container().verify().classify().to_dict()


@mcp.tool()
def do_task(goal_screen: str, action: str = "challenge", element: str = "",
            repeat: int = 1, ap_cost: int = 0, stop_on: str = "no_resource") -> dict:
    """LAM TRON 1 NHIEM VU tu dong: dieu huong + lap + verify + dung dung luc.

    Tang Task Executor - bien nhan dien thanh TU DONG HOA that. He thong tu:
      1. goto(goal_screen) qua world graph (bfs_path da hoc).
      2. lap `repeat` lan: click element hanh dong -> (neu challenge) xu ly chuoi
         battle (Ready -> Auto -> cho ket qua) -> verify VICTORY/DEFEAT.
      3. dung khi het luot/het tai nguyen (stop_on) hoac du repeat.

    Tham so:
        goal_screen: man dich (label da hoc, vd 'SoulBattle', 'SpiritVenture').
        action: 'challenge' (vao danh), 'collect' (nhan thuong), 'navigate' (chi di toi).
        element: (tuy chon) label nut can click (vd 'Challenge'). "" -> tu suy.
        repeat: so lan lap (vd 10 tran).
        ap_cost: AP ton moi lan (de dung khi het AP). 0 = khong biet/khong chan.
        stop_on: Outcome dung (mac dinh 'no_resource').
    Tra TaskResult: {ok, goal_screen, done_count, requested, stopped_reason, verdicts}.

    QUAN TRONG: chi dieu huong bang element DA HOC (khong hardcode). Neu thieu
    duong/element -> tra ro 'chua map duong' / 'chua hoc element' (de explore truoc)."""
    from onmyoji.domain.entities import TaskSpec, Outcome
    c = get_container()
    if c.world is None:
        return {"ok": False, "error": "WorldModel khong kha dung"}
    try:
        stops = tuple(Outcome(s.strip()) for s in stop_on.split(",") if s.strip())
    except ValueError:
        stops = (Outcome.NO_RESOURCE,)
    spec = TaskSpec(goal_screen=goal_screen, action=action,
                    element=element or None, repeat=int(repeat),
                    stop_on=stops or (Outcome.NO_RESOURCE,), ap_cost=int(ap_cost))
    return c.execute_task(settle=_wait_settle).execute(spec).to_dict()


@mcp.tool()
def plan_daily() -> dict:
    """LEN LICH cong viec daily tu knowledge/daily_plan.json (data) + trang thai.

    Tang Daily Planner: doc plan (man nao farm gi, uu tien) -> LOC chi giu man DA
    MAP (co duong tu HOME) -> sap theo priority -> tra list TaskSpec. Dung run_daily
    de chay tuan tu, hoac goi do_task tung cai.
    Tra ve: {ok, tasks: [TaskSpec], skipped_unmapped: [...] }."""
    c = get_container()
    specs = c.plan_daily().plan()
    return {"ok": True, "count": len(specs),
            "tasks": [s.to_dict() for s in specs]}


@mcp.tool()
def run_daily(max_tasks: int = 20) -> dict:
    """CHAY toan bo daily routine: plan_daily -> thuc thi tuan tu tung TaskSpec.

    Tu choi (autonomous): tu lam het cac viec daily da map. Tra tong ket moi task.
    Tham so max_tasks: tran an toan (so task toi da chay)."""
    c = get_container()
    if c.world is None:
        return {"ok": False, "error": "WorldModel khong kha dung"}
    specs = c.plan_daily().plan()[:max_tasks]
    executor = c.execute_task(settle=_wait_settle)
    results = []
    for s in specs:
        r = executor.execute(s)
        results.append(r.to_dict())
    return {"ok": True, "ran": len(results), "results": results}


def main() -> None:
    """Chay MCP server qua stdio (transport mac dinh cho jcode/Claude)."""
    mcp.run()


if __name__ == "__main__":
    main()
