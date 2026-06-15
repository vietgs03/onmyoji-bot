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
    # xac nhan man: chi dung sid khi dhash THUC SU match (khong fallback raw id)
    sid = world.match_state(obs.dhash, obs.state_id) if world else None
    confirmed = sid is not None or bool(obs.page)
    d["screen_confirmed"] = confirmed
    if not confirmed:
        # man LA -> bao agent NHIN, KHONG gop verified (tranh khoanh sai)
        d["screen_hint"] = ("Man LA (dhash chua hoc + khong khop page nao). "
                            "Hay NHIN anh marked de nhan dien; element CV la UNG VIEN.")
        return d
    if sid is None:
        return d  # co page nhung chua co node dhash -> khong co verified de gop
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
def click_at(x: int, y: int, snap: bool = True) -> dict:
    """Click tai toa do (x,y) ban UOC LUONG tu anh, voi SNAP tu dong (mac dinh).

    Dung khi element BI SOT (khong co mark trong observe_marked) -> ban nhin anh,
    uoc toa do tho, goi click_at(x,y). He thong tu SNAP ve tam element gan nhat
    (trong ban kinh ~40px) -> click chinh xac du ban uoc hoi lech. snap=False de
    click dung (x,y) khong chinh.

    Tham so:
        x, y: toa do uoc luong tu anh marked/goc.
        snap: True (mac dinh) = snap ve element gan nhat; False = click nguyen xy.
    Tra ve dict Observation MOI sau click.
    """
    eye = get_container().eye
    sx, sy = x, y
    if snap and hasattr(eye, "snap"):
        sx, sy, _ = eye.snap(x, y)
    return get_container().act().execute(Action.click(sx, sy)).to_dict()


@mcp.tool()
def learn_element(label: str, x: int, y: int) -> dict:
    """GHI NHO 1 element ban DA XAC NHAN bang mat (vision) cho man hinh hien tai.

    Self-learning: sau khi ban NHIN anh (observe_marked) va xac dinh "cho (x,y) la
    nut <label>", goi ham nay de luu vao ban do. LAN SAU gap lai man nay, he thong
    biet ngay <label> o dau - KHONG can CV/ban nhin lai. Day la cach bot tu hoc
    game thay vi hardcode.

    Tham so:
        label: ten ngu nghia (vd 'Summon', 'Explore', 'Shop', 'back').
        x, y: toa do element (nen lay tu mark.cx/cy hoac sau khi snap).
    Tra ve: {ok, state_id, label, learned: [cac element da hoc cho man nay]}.
    """
    c = get_container()
    world = c.world
    if world is None:
        return {"ok": False, "error": "WorldModel khong kha dung"}
    # Xac dinh man hien tai cho CHAC (tranh hoc vao state dong/khong on dinh ->
    # element 'mo coi' khoanh sai cho). Uu tien dhash match (state da hoc), neu
    # khong thi page (landmark robust). Man LA hoan toan -> tu tao node tu dhash
    # NHUNG canh bao agent (dhash man dong co the khong lap lai).
    obs = c.eye.observe_som(with_page=True)
    matched = world.match_state(obs.dhash, obs.state_id)
    sid = matched or obs.state_id
    # snap toa do ve element that cho chuan
    sx, sy = x, y
    if hasattr(c.eye, "snap"):
        sx, sy, _ = c.eye.snap(x, y)
    world.record_element(sid, sx, sy, label, dhash=obs.dhash)
    if hasattr(world, "save"):
        world.save()
    confirmed = matched is not None or bool(obs.page)
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


def main() -> None:
    """Chay MCP server qua stdio (transport mac dinh cho jcode/Claude)."""
    mcp.run()


if __name__ == "__main__":
    main()
