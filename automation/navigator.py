#!/usr/bin/env python3
"""
navigator.py - [DEPRECATED] Dung automation/screen_graph.py thay the.

Module nay gio chi la WRAPPER MONG tro ve ScreenGraph (graph dieu huong hop nhat,
nguon su that duy nhat). Giu lai de code cu khong vo. Code MOI dung:

    from screen_graph import ScreenGraph
    nav = ScreenGraph(agent)
    nav.goto('realm_raid')
    nav.where()
    nav.escape()

Ly do gop: tranh 2 he dieu huong song song (phan tan). Toan bo flow/coords da
chuyen vao NODES trong screen_graph.py (DATA thuan). Xem docs/navigation_architecture.md
"""
import warnings
from screen_graph import ScreenGraph


class Navigator:
    """[DEPRECATED] Vo boc mong cua ScreenGraph. Hay dung ScreenGraph truc tiep."""

    def __init__(self, agent):
        warnings.warn(
            "Navigator da deprecated -> dung screen_graph.ScreenGraph",
            DeprecationWarning, stacklevel=2,
        )
        self._g = ScreenGraph(agent)

    def goto(self, target, **kw):
        return self._g.goto(target, **kw)

    @property
    def current(self):
        return self._g.where()[0]          # where() tra (node, conf)

    def __getattr__(self, name):
        # uy quyen het cho ScreenGraph
        return getattr(self._g, name)
