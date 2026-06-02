#!/usr/bin/env python3
"""
UI State-Graph engine cho Onmyoji (Steam PC window, control qua WSL->PowerShell).

Khai niem:
- PAGE (node): 1 man hinh UI. Nhan dien bang >=1 ANCHOR (template ROI).
- EDGE: hanh dong (click) chuyen tu page A -> page B.
- detect_current(): bgshot -> match anchor cua moi page -> page hien tai.
- goto(target): BFS tren graph -> chuoi edge -> thuc thi + verify tung buoc.

Dinh nghia o ui_graph/pages.yaml + ui_graph/edges.yaml.
Assets template o assets/<PAGE>/*.png
"""
import json, os, subprocess, sys, time
from collections import deque

import cv2
import numpy as np
import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UI_DIR = os.path.join(ROOT, "ui_graph")
ASSET_DIR = os.path.join(ROOT, "assets")
CLI = os.path.join(ROOT, "scripts", "onmyoji.sh")
LATEST = os.path.join(ROOT, "captures", "_state.png")


# ---------- device layer (qua CLI bash) ----------
def bgshot(name="_state"):
    """Chup nen, tra ve duong dan PNG trong captures/."""
    out = subprocess.run([CLI, "bgshot", name], capture_output=True, text=True)
    path = out.stdout.strip().splitlines()[-1] if out.stdout.strip() else None
    return path

def bgclick(x, y):
    subprocess.run([CLI, "bgclick", str(int(x)), str(int(y))],
                   capture_output=True, text=True)

def load_image(path):
    img = cv2.imread(path)  # BGR
    return img


# ---------- template matching ----------
def match_anchor(image, tpl_path, roi, threshold):
    """Tra ve (score, cx, cy) neu khop, else None. roi=[x,y,w,h] hoac None (toan anh)."""
    tpl = cv2.imread(tpl_path)
    if tpl is None or image is None:
        return None
    if roi:
        x, y, w, h = [int(v) for v in roi]
        src = image[y:y+h, x:x+w]
        ox, oy = x, y
    else:
        src = image; ox, oy = 0, 0
    if src.shape[0] < tpl.shape[0] or src.shape[1] < tpl.shape[1]:
        return None
    res = cv2.matchTemplate(src, tpl, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(res)
    if max_val >= threshold:
        cx = ox + max_loc[0] + tpl.shape[1] // 2
        cy = oy + max_loc[1] + tpl.shape[0] // 2
        return (max_val, cx, cy)
    return None


# ---------- graph ----------
class UIGraph:
    def __init__(self):
        self.pages = self._load(os.path.join(UI_DIR, "pages.yaml")) or {}
        self.edges = self._load(os.path.join(UI_DIR, "edges.yaml")) or []
        self.adj = {}
        for e in self.edges:
            self.adj.setdefault(e["from"], []).append(e)

    @staticmethod
    def _load(p):
        if not os.path.exists(p):
            return None
        return yaml.safe_load(open(p, encoding="utf-8"))

    def detect_current(self, image=None):
        """Match anchor cua moi page, tra ve (page_name, score) cao nhat hoac (None,0)."""
        if image is None:
            path = bgshot()
            image = load_image(path)
        best, best_score = None, 0.0
        for name, pg in self.pages.items():
            if name.startswith("_"):
                continue
            anchors = pg.get("anchors", [])
            if not anchors:
                continue
            scores = []
            for a in anchors:
                tpl = os.path.join(ASSET_DIR, a["asset"])
                r = match_anchor(image, tpl, a.get("roi"),
                                 a.get("threshold", 0.8))
                scores.append(r[0] if r else 0.0)
            # page match neu MOI anchor deu pass (AND) -> diem = min
            page_score = min(scores) if scores else 0.0
            require = pg.get("match", "all")
            if require == "any":
                page_score = max(scores) if scores else 0.0
            if page_score > best_score:
                best_score, best = page_score, name
        thr = 0.8
        if best_score >= thr:
            return best, best_score
        return None, best_score

    def shortest_path(self, src, dst):
        """BFS tra ve list edge tu src->dst, hoac None."""
        if src == dst:
            return []
        q = deque([(src, [])])
        seen = {src}
        while q:
            node, path = q.popleft()
            for e in self.adj.get(node, []):
                nxt = e["to"]
                if nxt in seen:
                    continue
                npath = path + [e]
                if nxt == dst:
                    return npath
                seen.add(nxt)
                q.append((nxt, npath))
        return None

    def exec_edge(self, e):
        act = e.get("action", {})
        if act.get("type") == "click":
            bgclick(act["x"], act["y"])
        time.sleep(e.get("wait", 1.2))

    def goto(self, target, max_steps=20):
        """Di chuyen den page target, verify tung buoc, replan neu lac."""
        for _ in range(max_steps):
            cur, sc = self.detect_current()
            print(f"  at: {cur} ({sc:.2f})")
            if cur == target:
                return True
            if cur is None:
                if not self._recover():
                    return False
                continue
            path = self.shortest_path(cur, target)
            if not path:
                print(f"  ! no path {cur}->{target}")
                return False
            self.exec_edge(path[0])  # 1 buoc roi detect lai (robust)
        return False

    def _recover(self):
        """UNKNOWN: thu cac nut thoat chung de ve node da biet."""
        commons = self.pages.get("_common", {}).get("recover_clicks", [])
        for c in commons:
            bgclick(c[0], c[1]); time.sleep(1.0)
            cur, _ = self.detect_current()
            if cur:
                return True
        return False


if __name__ == "__main__":
    g = UIGraph()
    cmd = sys.argv[1] if len(sys.argv) > 1 else "detect"
    if cmd == "detect":
        name, sc = g.detect_current()
        print(f"current page: {name} (score {sc:.3f})")
    elif cmd == "goto":
        ok = g.goto(sys.argv[2])
        print("OK" if ok else "FAILED")
    elif cmd == "list":
        print("PAGES:", list(g.pages.keys()))
        print("EDGES:", [(e['from'], e['to']) for e in g.edges])
