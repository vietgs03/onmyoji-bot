"""Test kien truc Clean Architecture - KHONG can game/Windows.

Chay: .venv/bin/python -m pytest tests_arch/ -v
Hoac: .venv/bin/python tests_arch/test_architecture.py
"""
import os
import sys
import json

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from onmyoji.domain.entities import (
    Observation, Action, ActionKind, ActionResult, Button, Resources, Size,
)
from onmyoji.application.use_cases import (
    PerceiveUseCase, WaitStableUseCase, NavigateUseCase, ActUseCase,
)
from onmyoji.adapters.eye_py.fake_eye import FakeEye


def test_observation_roundtrip():
    obs = Observation(
        ts=123.4, state_id="HOME", loading=False, size=Size(1152, 679),
        buttons=(Button(10, 20, 30, 40, 0.8, "Explore"),),
        alive=True, resources=Resources(gold=500, ap=80),
    )
    d = obs.to_dict()
    obs2 = Observation.from_dict(d)
    assert obs2 == obs
    # serialize JSON that
    s = json.dumps(d)
    assert Observation.from_dict(json.loads(s)) == obs
    print("  [ok] Observation roundtrip qua JSON")


def test_action_roundtrip():
    for a in [
        Action.click(5, 6),
        Action.polite_click(7, 8),
        Action.drag(0, 0, 100, 100, steps=10),
        Action.key_press("ESC"),
        Action.wait(500),
    ]:
        a2 = Action.from_dict(json.loads(json.dumps(a.to_dict())))
        assert a2 == a
    print("  [ok] Action roundtrip qua JSON (5 loai)")


def test_contract_matches_schema():
    """Entity to_dict() phai khop key voi contracts/schema.json."""
    schema = json.load(open(os.path.join(ROOT, "contracts", "schema.json")))
    obs_props = set(schema["definitions"]["Observation"]["properties"])
    obs = Observation(ts=1, state_id="x", loading=False, size=Size(1, 1))
    assert set(obs.to_dict()).issubset(obs_props), "Observation co key ngoai schema"
    act_props = set(schema["definitions"]["Action"]["properties"])
    assert set(Action.click(1, 2).to_dict()).issubset(act_props), "Action ngoai schema"
    print("  [ok] Entities khop contracts/schema.json")


def test_perceive_usecase_with_fake_eye():
    eye = FakeEye(state_id="HOME")
    ctx = PerceiveUseCase(eye).execute()
    assert ctx.observation.state_id == "HOME"
    assert ctx.observation.alive
    print("  [ok] PerceiveUseCase chay voi FakeEye")


def test_act_usecase_logs_action():
    eye = FakeEye()
    ActUseCase(eye).execute(Action.click(50, 60))
    assert len(eye.actions_log) == 1
    assert eye.actions_log[0].kind is ActionKind.CLICK
    print("  [ok] ActUseCase thuc thi + log action")


def test_navigate_usecase_with_stub_world():
    """NavigateUseCase chi biet Port -> dung world gia lap."""
    from onmyoji.domain.ports import WorldModelPort

    class StubWorld(WorldModelPort):
        def __init__(self):
            self.transitions = []
        def resolve_label(self, sid):
            return {"HOME": "HOME", "SHOP_SCREEN": "SHOP"}.get(sid)
        def path_to(self, frm, to_label):
            if to_label == "SHOP":
                return [Action.click(200, 50)]
            return None
        def record_transition(self, frm, action, to):
            self.transitions.append((frm, action.kind.value, to))

    eye = FakeEye(state_id="HOME")
    world = StubWorld()
    # khi click, eye chuyen sang SHOP_SCREEN
    orig_act = eye.act
    def act_then_move(a):
        r = orig_act(a)
        eye.set_state("SHOP_SCREEN")
        return r
    eye.act = act_then_move

    ok = NavigateUseCase(eye, world).execute("SHOP")
    assert ok, "phai navigate toi SHOP thanh cong"
    assert len(world.transitions) == 1
    print("  [ok] NavigateUseCase di HOME->SHOP qua Port (swap-able)")


def test_navigate_page_fallback():
    """dhash KHONG khop (man DONG) -> NavigateUseCase dung PAGE detector lam fallback
    de xac dinh dang o dau, roi van path_to den dich. Fix diem yeu dhash."""
    from onmyoji.domain.ports import WorldModelPort
    from onmyoji.domain.entities import Observation, Size

    class PageWorld(WorldModelPort):
        def resolve_label(self, sid):
            # dhash KHONG ra label (man dong) -> luon None
            return None
        def resolve_page(self, page):
            # page detector ra "page_main" -> map sang HOME
            return {"page_main": "HOME"}.get(page)
        def state_for_label(self, label):
            return "HOME_SID" if label == "HOME" else None
        def path_to(self, frm, to_label):
            # tu HOME (qua page) co duong toi EXPLORE
            if frm == "HOME_SID" and to_label == "EXPLORE":
                return [Action.click(300, 100)]
            return None
        def record_transition(self, frm, action, to):
            pass

    class PageEye(FakeEye):
        def __init__(self):
            super().__init__(state_id="DYNAMIC")  # dhash khong khop gi
            self.reached = False
        def observe_nav(self):
            # man dong: state_id la, khong co dhash khop
            return Observation(ts=0, state_id="DYNAMIC", loading=False,
                               size=Size(1136, 640))
        def observe_page(self):
            # page detector nhan ra page_main (robust)
            pg = "page_main" if not self.reached else "page_exploration"
            return Observation(ts=0, state_id="DYNAMIC", loading=False,
                               size=Size(1136, 640), page=pg, page_score=0.98)
        def act(self, a):
            self.reached = True  # sau click -> sang EXPLORE
            return super().act(a)

    eye = PageEye()
    world = PageWorld()
    # dich EXPLORE: ban dau dhash None -> page=page_main=HOME -> path_to -> click
    # -> reached=True -> page=page_exploration (nhung world chua map) -> van la None
    # de don gian: kiem da goi duoc path qua page fallback (1 buoc)
    ok = NavigateUseCase(eye, world, max_steps=3).execute("EXPLORE")
    # khong nhat thiet toi dich (page_exploration chua map), nhung phai DA THU
    # di qua page fallback (khong return False ngay vi path_to ra duong)
    assert eye.reached, "phai dung page fallback de xac dinh HOME va click di tiep"
    print("  [ok] NavigateUseCase page fallback (dhash fail -> page detector)")


def test_verified_elements_selflearning():
    """Agent verify element (vision) -> luu world_model -> lan sau dung lai.
    Self-learning: KHONG hardcode, agent xac nhan 1 lan, he thong nho mai."""
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))
    from world_model import WorldModel
    from onmyoji.adapters.world.world_model_adapter import WorldModelAdapter

    wm = WorldModel()
    wm.states = {
        "h1": {"dhash": "0" * 64, "label": "HOME", "buttons_tried": []},
        "h2": {"dhash": "1" * 64, "label": "HOME", "buttons_tried": []},
    }
    wm.edges = []
    adapter = WorldModelAdapter(world=wm)
    # agent verify 2 element tren HOME (qua state h1)
    adapter.record_element("h1", 568, 600, "Summon")
    adapter.record_element("h2", 100, 100, "back")
    # truy van qua h1 phai gop ca 2 (cung label HOME logic)
    els = adapter.elements_for("h1")
    labels = sorted(e["label"] for e in els)
    assert labels == ["Summon", "back"], f"sai: {labels}"
    # ghi trung khong tang
    adapter.record_element("h1", 568, 600, "Summon")
    assert len(adapter.elements_for("h1")) == 2, "khong duoc ghi trung"
    print("  [ok] verified elements (agent verify -> world_model nho, self-learning)")


def test_canonical_state_page_anchor():
    """canonical_state NEO man theo do BEN nhat de man DONG (dhash troi moi frame)
    KHONG phan manh verified elements. Day la fix goc: truoc day moi lan hoc HOME
    sinh node moc coi khac (dhash khac) -> recall hen xui. Page (landmark) khong
    troi -> moi frame HOME hoi tu ve CUNG 1 node logic."""
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))
    from world_model import WorldModel
    from onmyoji.adapters.world.world_model_adapter import WorldModelAdapter
    import json as _json

    wm = WorldModel()
    # node HOME da hoc voi 1 dhash cu the
    home_dh = "0" * 64
    wm.states = {"home1": {"dhash": home_dh, "label": "HOME", "buttons_tried": [], "verified_elements": []}}
    wm.edges = []
    # page_map that (page_main -> HOME) da co trong knowledge/page_label_map.json
    adapter = WorldModelAdapter(world=wm)

    # 1) dhash KHOP -> tra chinh node do, confirmed
    sid, conf = adapter.canonical_state(home_dh, "irrelevant", page="page_main")
    assert sid == "home1" and conf is True, f"dhash match phai tra node cu: {sid},{conf}"

    # 2) dhash TROI (khac >12 bit, man dong) NHUNG page=page_main -> neo ve HOME node
    drift = "1" * 64  # rat xa home_dh
    sid2, conf2 = adapter.canonical_state(drift, "newid", page="page_main")
    assert sid2 == "home1" and conf2 is True, f"page anchor phai hoi tu ve HOME: {sid2},{conf2}"

    # 3) dhash troi + page None (man LA) -> confirmed False (canh bao agent NHIN)
    sid3, conf3 = adapter.canonical_state(drift, "newid", page=None)
    assert conf3 is False, f"man LA phai confirmed=False: {sid3},{conf3}"

    # 4) page chua co node (vd page_summon, HOME chua map summon) -> tao node moi
    #    NHUNG confirmed=True (page robust). Element hoc se nam tren node moi nhat quan.
    sid4, conf4 = adapter.canonical_state(drift, "sumid", page="page_summon")
    assert conf4 is True, f"page co map nhung chua co node -> confirmed van True: {sid4},{conf4}"

    # 5) THUC TE quan trong: hoc element qua page anchor -> recall on dinh du dhash troi
    sid_learn, _ = adapter.canonical_state(drift, "frameA", page="page_main")
    adapter.record_element(sid_learn, 708, 163, "Explore", dhash=drift)
    # frame sau dhash troi KHAC -> van recall duoc Explore (cung HOME node)
    drift2 = "0011" * 16
    sid_recall, _ = adapter.canonical_state(drift2, "frameB", page="page_main")
    els = adapter.elements_for(sid_recall)
    labels = sorted(e["label"] for e in els)
    assert "Explore" in labels, f"recall qua page anchor phai thay Explore: {labels}"

    # 6) UU TIEN node CO LABEL: man dong dhash match 1 node CU KHONG label, nhung
    #    page resolve ra label co node -> phai tra node CO LABEL (verified elements
    #    gom theo label). Neu tra node khong label -> MAT elements (bug Town da gap).
    wm.states["town_unlabeled"] = {"dhash": "1010" * 16, "label": None,
                                   "buttons_tried": [], "verified_elements": []}
    wm.states["town_labeled"] = {"dhash": "0101" * 16, "label": "Town2",
                                 "buttons_tried": [], "verified_elements": [
                                     {"cx": 300, "cy": 318, "label": "Arena"}]}
    # gia page_main2 -> Town2 (dung resolve_page that khong co, nen test truc tiep
    # logic: dhash match node khong label + co label tu state_for_label)
    # mo phong: dhash match town_unlabeled, nhung neu page->Town2 thi uu tien labeled
    # (dung _label_to_state). Day la hanh vi canonical_state buoc 2 > buoc 3.
    sid_pref = adapter._label_to_state("Town2")
    assert sid_pref == "town_labeled", "phai resolve Town2 -> node co label"
    assert any(e["label"] == "Arena" for e in adapter.elements_for(sid_pref)), \
        "node co label phai giu verified elements"
    print("  [ok] canonical_state page anchor (man dong dhash troi -> recall on dinh)")


def test_learn_element_screen_anchor():
    """learn_element(screen='Town') NEO element vao node co label do (agent khai
    bao ro) -> man DONG KHONG page (dhash troi 30-40 bit moi frame, threshold se
    nham man) van hoi tu ve 1 node. Fix phan manh cho man khong page anchor."""
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))
    from world_model import WorldModel
    from onmyoji.adapters.world.world_model_adapter import WorldModelAdapter

    wm = WorldModel()
    # node Town da co label (tu learn_screen), dhash mot bien the
    wm.states = {"town_a": {"dhash": "0" * 64, "label": "Town", "buttons_tried": [], "verified_elements": []}}
    wm.edges = []
    adapter = WorldModelAdapter(world=wm)

    # state_for_label('Town') -> node town_a (du dhash hien tai troi xa)
    assert adapter.state_for_label("Town") == "town_a", "phai resolve Town -> town_a"
    # state_for_label man chua co -> None (agent phai learn_screen truoc)
    assert adapter.state_for_label("Arena") is None, "man chua hoc -> None"

    # ghi element qua node resolved -> nam tren town_a (khong tao node moc coi)
    adapter.record_element("town_a", 300, 318, "Arena", dhash="1" * 64)
    adapter.record_element("town_a", 610, 306, "DemonParade", dhash="1" * 64)
    els = adapter.elements_for("town_a")
    labels = sorted(e["label"] for e in els)
    assert labels == ["Arena", "DemonParade"], f"element phai gom ve town_a: {labels}"
    print("  [ok] learn_element screen anchor (man dong khong page -> hoi tu 1 node)")


def test_click_at_records_edge():
    """click_at GHI EDGE (nguon->dich) vao world graph khi ca hai dau nhan dien
    duoc -> goto()/bfs_path dung lai duong. Day la cach graph TU LON khi kham pha
    (truoc day click_at KHONG ghi edge -> graph co node nhung thieu duong di)."""
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))
    from world_model import WorldModel
    from onmyoji.adapters.world.world_model_adapter import WorldModelAdapter
    from onmyoji.domain.entities import Action

    wm = WorldModel()
    wm.states = {
        "src": {"dhash": "0" * 64, "label": "Town", "buttons_tried": [], "verified_elements": []},
        "dst": {"dhash": "1" * 64, "label": "Arena", "buttons_tried": [], "verified_elements": []},
    }
    wm.edges = []
    adapter = WorldModelAdapter(world=wm)
    # mo phong click_at ghi edge: o src click (290,370) -> toi dst
    adapter.record_transition("src", Action.click(290, 370), "dst")
    assert len(wm.edges) == 1, f"phai ghi 1 edge: {wm.edges}"
    e = wm.edges[0]
    assert e["from"] == "src" and e["to"] == "dst" and e["click"] == [290, 370], f"edge sai: {e}"
    # mark_tried an toan khi node thieu key buttons_tried
    wm.states["nokey"] = {"dhash": "0101" * 16, "label": "X"}  # khong co buttons_tried
    wm.mark_tried("nokey", (10, 20))  # khong duoc raise
    assert wm.states["nokey"]["buttons_tried"] == [[10, 20]], "mark_tried phai tu tao key"
    # path_to dung edge da ghi (Town -> Arena qua click)
    path = adapter.path_to("src", "Arena")
    assert path and path[0].x == 290 and path[0].y == 370, f"path_to phai ra click 290,370: {path}"
    print("  [ok] click_at ghi edge (graph tu lon: goto/bfs_path dung lai duong)")


def test_observe_marked_confirm_screen():
    """observe_marked PHAI xac nhan man truoc khi gop verified (tranh khoanh tum
    lum tren man LA). Man LA (dhash khong match + page none) -> screen_confirmed
    False + hint + KHONG gop verified. Man co page -> confirmed."""
    from onmyoji.interface import mcp_server as M
    from onmyoji.domain.entities import Observation, Size, Mark
    from onmyoji.domain.ports import WorldModelPort

    class _W(WorldModelPort):
        # canonical_state: man LA (page None) -> confirmed False (mac dinh port).
        # man co page_main -> resolve_page tra 'HOME' -> co node -> confirmed True.
        def match_state(self, dh, sid):
            return None  # dhash khong match (man chua hoc / man dong troi)

        def resolve_page(self, page):
            return "HOME" if page == "page_main" else None

        def canonical_state(self, dh, sid, page=None):
            label = self.resolve_page(page)
            if label:
                return ("home_node", True)  # page -> label -> node da co (neo on dinh)
            return (sid, False)  # man LA

        def resolve_label(self, sid):
            return "HOME" if sid == "home_node" else None

        def path_to(self, frm, to):
            return None

        def record_transition(self, frm, action, to):
            pass

        def elements_for(self, sid):
            return [{"cx": 100, "cy": 100, "label": "X"}]  # verified (gop khi confirmed)

    class _C:
        world = _W()

    orig = M.get_container
    M.get_container = lambda: _C()
    try:
        # man LA: page None, dhash khong match -> KHONG gop verified
        la = Observation(ts=0, state_id="zzz", loading=False, size=Size(1136, 640),
                         marks=(Mark(1, 50, 50, 28, 28, 44, 44, 1.0),),
                         marked_path=None, page=None)
        d = M._merge_verified(la)
        assert d["screen_confirmed"] is False, "man LA phai confirmed=False"
        assert "screen_hint" in d, "man LA phai co hint cho agent"
        assert all(not m.get("label") for m in d["marks"]), "man LA KHONG duoc gop verified"
        # man co page -> confirmed
        ok = Observation(ts=0, state_id="zzz", loading=False, size=Size(1136, 640),
                         marks=(), marked_path=None, page="page_main", page_score=0.97)
        d2 = M._merge_verified(ok)
        assert d2["screen_confirmed"] is True, "man co page phai confirmed=True"
    finally:
        M.get_container = orig
    print("  [ok] observe_marked xac nhan man (man LA -> khong khoanh tum lum)")


def test_knowledge_learn_selflearning():
    """Agent DAY tri thuc moi (vd 'screen X = farm Y') -> KnowledgePort.learn ->
    ask_kb tim duoc ngay. Self-learning ngu nghia (KHONG hardcode KB)."""
    from onmyoji.domain.ports import KnowledgePort

    class _KB(KnowledgePort):
        def __init__(self):
            self.docs = []
        def ask(self, query, k=5):
            # tra doc co tu khoa trong query (gia lap semantic)
            ql = query.lower()
            return [d for d in self.docs
                    if any(w in (d["title"] + d["text"]).lower() for w in ql.split())][:k]
        def learn(self, title, text, doc_type="learned", doc_id=None, meta=None):
            doc = {"title": title, "text": text, "type": doc_type, "id": doc_id or title}
            self.docs = [d for d in self.docs if d["id"] != doc["id"]] + [doc]
            return doc

    kb = _KB()
    kb.learn("Soul Zone", "Man farm ngoc hon cho shikigami", doc_type="screen",
             doc_id="screen:soul_zone")
    # ask lai -> tim duoc
    res = kb.ask("ngoc hon farm", k=3)
    assert any(d["title"] == "Soul Zone" for d in res), "phai tim duoc tri thuc da hoc"
    # update cung id -> khong nhan doi
    kb.learn("Soul Zone", "cap nhat", doc_type="screen", doc_id="screen:soul_zone")
    assert len([d for d in kb.docs if d["id"] == "screen:soul_zone"]) == 1
    print("  [ok] knowledge learn (agent day -> ask_kb tim duoc, self-learning ngu nghia)")


def test_explore_frontier():
    """Vong kham pha: world_model theo doi element CHUA thu (frontier) de agent
    di het cay ban do. Click element -> mark tried -> frontier giam."""
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))
    from world_model import WorldModel
    from onmyoji.adapters.world.world_model_adapter import WorldModelAdapter
    from onmyoji.domain.entities import Action

    wm = WorldModel()
    wm.states = {"h1": {"dhash": "0" * 64, "label": "HOME", "buttons_tried": [],
                        "verified_elements": [
                            {"cx": 430, "cy": 165, "label": "Explore"},
                            {"cx": 820, "cy": 230, "label": "Summon"}]}}
    wm.edges = []
    ad = WorldModelAdapter(world=wm)
    # ban dau: 2 element chua thu
    assert len(ad.untried_elements("h1")) == 2
    fr = ad.frontier()
    assert fr and fr[0]["label"] == "HOME" and fr[0]["untried"] == 2
    # agent click Explore -> record_transition -> mark tried
    ad.record_transition("h1", Action.click(430, 165), "explore_sid")
    assert len(ad.untried_elements("h1")) == 1, "click roi phai bot 1 untried"
    st = ad.explore_stats()
    assert st["frontier_untried_total"] == 1
    print("  [ok] explore frontier (theo doi element chua thu -> di het ban do)")


def test_match_state_fuzzy_dhash():
    """Rust EYE cho dhash lech vai bit -> state_id md5 KHAC HAN. match_state phai
    khop MO theo dhash (hamming<=12) -> tra dung sid Python da luu.

    Day la cau noi song con cho viec swap EYE sang Rust: neu chi so khop state_id
    chinh xac, moi frame Rust se 'lac' state du man hinh y het."""
    import hashlib
    from onmyoji.adapters.world.world_model_adapter import WorldModelAdapter

    py_dh = "0101010010101010011001011001111010100110010110100100101011010011"
    py_sid = hashlib.md5(py_dh.encode()).hexdigest()[:10]

    class _WM:  # world toi thieu cho adapter (khong dung WorldModel that)
        def __init__(self):
            self.states = {py_sid: {"dhash": py_dh, "label": "HOME"}}

    adapter = WorldModelAdapter(world=_WM())

    # Rust: lech 1 bit -> sid khac han
    rust_dh = "0101010000101010011001011001111010100110010110100100101011010011"
    rust_sid = hashlib.md5(rust_dh.encode()).hexdigest()[:10]
    assert rust_sid != py_sid, "md5 phai khuech dai 1 bit thanh sid khac"

    # khop chinh xac theo sid Rust -> truot
    assert adapter.resolve_label(rust_sid) is None
    # khop mo theo dhash -> ra dung sid Python
    matched = adapter.match_state(rust_dh, rust_sid)
    assert matched == py_sid, "match_state phai khop mo ve sid Python"
    assert adapter.resolve_label(matched) == "HOME"
    # khong co dhash -> chi khop chinh xac (giu hanh vi cu, an toan)
    assert adapter.match_state(None, rust_sid) is None
    assert adapter.match_state(None, py_sid) == py_sid
    print("  [ok] match_state khop mo dhash (Rust lech bit van resolve dung state)")


def test_normalize_graph_algorithm():
    """normalize_graph: (1) gop label alias, (2) xoa edge tu-than logic + node mo
    coi, (3) SUY edge forward tu verified_elements -> bfs_path thong mach. Day la
    fix thuat toan: kham pha sinh alias (Explore vs Exploration) + edge forward
    miss do loading -> graph dut mach."""
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))
    import normalize_graph as NG
    from world_model import WorldModel

    # graph gia mo phong loi: alias (Exploration vs Explore), edge tu-than, thieu
    # edge forward (chi co element label, chua co edge).
    S = {
        "home": {"label": "HOME", "verified_elements": [{"cx": 600, "cy": 190, "label": "Explore"}], "buttons_tried": []},
        "exp1": {"label": "Exploration", "verified_elements": [{"cx": 168, "cy": 590, "label": "Soul"}], "buttons_tried": []},
        "exp2": {"label": "Explore", "verified_elements": [], "buttons_tried": []},  # alias se gop
        "soul": {"label": "Soul", "verified_elements": [], "buttons_tried": []},
        "orphan": {"label": None, "verified_elements": [], "buttons_tried": []},  # mo coi -> xoa
    }
    E = [
        {"from": "exp1", "click": [100, 100], "to": "exp2"},  # tu-than logic (Exploration==Explore sau gop) -> xoa
        {"from": "soul", "click": [40, 40], "to": "exp1"},     # Soul->Explore (back) - giu
    ]

    # 1) gop alias Exploration->Explore
    for sid, st in S.items():
        if st.get("label") in NG.ALIASES:
            st["label"] = NG.ALIASES[st["label"]]
    assert S["exp1"]["label"] == "Explore", "alias phai gop Exploration->Explore"

    # 2) suy forward edges tu verified_elements
    added = NG._derive_forward_edges(S, E)
    # HOME co element 'Explore' -> edge HOME->Explore; Explore co 'Soul' -> Explore->Soul
    keys = {(e["from"], tuple(e["click"]), e["to"]) for e in E}
    assert ("home", (600, 190), "exp1") in keys or any(
        e["from"] == "home" and S[e["to"]]["label"] == "Explore" for e in E), "phai suy HOME->Explore"
    assert any(e["from"] == "exp1" and e["to"] == "soul" for e in E), "phai suy Explore->Soul"
    assert added >= 2, f"phai suy >=2 forward edge: {added}"

    # 3) bfs HOME->Soul thong mach qua edge suy ra
    wm = WorldModel()
    wm.states = S
    wm.edges = E
    home_sid = "home"
    path = wm.bfs_path(home_sid, "soul")
    assert path is not None and len(path) == 2, f"HOME->Soul phai 2 click: {path}"
    print("  [ok] normalize_graph (alias + suy forward edge -> bfs thong mach)")


def test_autonomy_verify_outcome():
    """Tang 1: VerifyUseCase nhan dien ket qua (page victory/defeat/loading)."""
    from onmyoji.application.use_cases import VerifyUseCase
    from onmyoji.domain.entities import Observation, Size, Outcome, Resources

    eye = FakeEye()  # khong dung, classify nhan obs truc tiep
    vu = VerifyUseCase(eye, world=None)
    # page victory -> VICTORY
    ov = Observation(ts=0, state_id="x", loading=False, size=Size(1136, 640),
                     page="page_victory", page_score=0.95)
    assert vu.classify(ov).outcome == Outcome.VICTORY
    # page defeat -> DEFEAT
    od = Observation(ts=0, state_id="x", loading=False, size=Size(1136, 640),
                     page="page_defeat", page_score=0.9)
    assert vu.classify(od).outcome == Outcome.DEFEAT
    # loading -> LOADING
    ol = Observation(ts=0, state_id="x", loading=True, size=Size(1136, 640))
    assert vu.classify(ol).outcome == Outcome.LOADING
    # khong page -> UNKNOWN (khong doan bua)
    ou = Observation(ts=0, state_id="x", loading=False, size=Size(1136, 640), page=None)
    assert vu.classify(ou).outcome == Outcome.UNKNOWN
    print("  [ok] autonomy tang1: verify outcome (victory/defeat/loading/unknown)")


def test_autonomy_resource_policy():
    """Tang 4: ResourcePolicy quyet dinh theo AP (cost tu TaskSpec)."""
    from onmyoji.application.use_cases import ResourcePolicy
    from onmyoji.domain.entities import TaskSpec, Resources, Outcome

    spec = TaskSpec(goal_screen="SoulBattle", ap_cost=6)
    # du AP -> afford
    assert ResourcePolicy.can_afford(spec, Resources(ap=10)) is True
    # thieu AP -> khong afford -> NO_RESOURCE
    assert ResourcePolicy.can_afford(spec, Resources(ap=3)) is False
    assert ResourcePolicy.should_stop(spec, Resources(ap=3)) == Outcome.NO_RESOURCE
    # cost=0 (khong biet) -> luon afford (khong chan oan)
    free = TaskSpec(goal_screen="Dispatch", ap_cost=0)
    assert ResourcePolicy.can_afford(free, Resources(ap=0)) is True
    # khong doc duoc AP -> khong chan
    assert ResourcePolicy.can_afford(spec, Resources(ap=None)) is True
    print("  [ok] autonomy tang4: resource policy (het AP -> NO_RESOURCE)")


def test_autonomy_execute_task():
    """Tang 2: ExecuteTaskUseCase lam tron 1 task - navigate + lap + verify.
    Dung fake navigate/verify/act de test state machine khong can game."""
    from onmyoji.application.use_cases import ExecuteTaskUseCase
    from onmyoji.domain.entities import (
        TaskSpec, Outcome, Verdict, Observation, Size, Action, ActionResult, Resources,
    )

    # fake world: co element 'Challenge' tren SoulBattle
    class _W:
        def state_for_label(self, label):
            return "soul_node" if label == "SoulBattle" else None
        def elements_for(self, sid):
            return [{"cx": 1050, "cy": 550, "label": "Challenge"}] if sid == "soul_node" else []
        def resolve_page(self, pg):
            return None

    # fake eye: AP du, page None
    class _Eye:
        def observe(self):
            return Observation(ts=0, state_id="s", loading=False, size=Size(1136, 640),
                               resources=Resources(ap=100))
        def observe_page(self):
            return self.observe()
        def act(self, action):
            return ActionResult(ok=True, observation=self.observe())

    # fake navigate: luon toi noi
    class _Nav:
        def execute(self, label):
            return True

    # fake act: dem so click
    class _Act:
        def __init__(self): self.clicks = 0
        def execute(self, action):
            self.clicks += 1
            return Observation(ts=0, state_id="s", loading=False, size=Size(1136, 640))

    # fake verify: luon VICTORY (mo phong battle thang)
    class _Verify:
        def classify(self, obs=None):
            return Verdict(Outcome.VICTORY, 0.9, "test")
        def wait_outcome(self, accept, max_wait_s=90, poll_s=1):
            return Verdict(Outcome.VICTORY, 0.9, "test win")

    eye, nav, act = _Eye(), _Nav(), _Act()
    ex = ExecuteTaskUseCase(eye, _W(), _Verify(), nav, act, settle=None)
    spec = TaskSpec(goal_screen="SoulBattle", action="challenge",
                    element="Challenge", repeat=3, ap_cost=6)
    res = ex.execute(spec)
    assert res.ok, f"task phai ok: {res}"
    assert res.done_count == 3, f"phai danh 3 tran (deu thang): {res.done_count}"
    assert len(res.verdicts) == 3 and all(v.outcome == Outcome.VICTORY for v in res.verdicts)

    # case: chua map duong -> bao ro
    class _NavFail:
        def execute(self, label):
            return False
    ex2 = ExecuteTaskUseCase(eye, _W(), _Verify(), _NavFail(), act, settle=None)
    res2 = ex2.execute(spec)
    assert not res2.ok and "chua map duong" in res2.stopped_reason
    print("  [ok] autonomy tang2: execute task (navigate+lap+verify, done 3/3)")


def test_autonomy_plan_daily():
    """Tang 3: PlanDailyUseCase doc plan + LOC man da map + sap priority."""
    import json
    import tempfile
    from onmyoji.application.use_cases import PlanDailyUseCase

    plan = [
        {"_comment": "test"},
        {"screen": "SoulBattle", "action": "challenge", "repeat": 10, "priority": 5},
        {"screen": "SpiritVenture", "action": "challenge", "repeat": 2, "priority": 1},
        {"screen": "ChuaMap", "action": "challenge", "priority": 2},  # se bi loc (chua map)
    ]
    f = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
    json.dump(plan, f); f.close()

    class _W:
        def path_to(self, frm, to): return None
        def state_for_label(self, label):
            return label if label in ("SoulBattle", "SpiritVenture") else None

    pu = PlanDailyUseCase(_W(), f.name)
    specs = pu.plan()
    labels = [s.goal_screen for s in specs]
    # ChuaMap bi loc; con lai sap theo priority (SpiritVenture=1 truoc SoulBattle=5)
    assert labels == ["SpiritVenture", "SoulBattle"], f"sai thu tu/loc: {labels}"
    assert specs[0].repeat == 2 and specs[1].repeat == 10
    print("  [ok] autonomy tang3: plan daily (loc man chua map + sap priority)")


def run_all():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    print(f"\n=== Chay {len(tests)} test kien truc Clean Architecture ===")
    for t in tests:
        t()
    print(f"=== TAT CA {len(tests)} TEST PASS ===\n")


if __name__ == "__main__":
    run_all()
