# Review pathfinding trong he sinh thai onmyoji-bot

## Hien trang: 5 implementation pathfinding RIENG BIET (truoc khi refactor)

| File | Ham | Thuat toan | Trang thai | Dung boi |
|---|---|---|---|---|
| `onmyoji/.../world_model_adapter.py` -> `scripts/world_model.py` | `bfs_path` | BFS theo node LOGIC (gop cung label) | DUNG (unweighted) | **Clean Arch (production moi)** |
| `automation/screen_graph.py` | `path` | Dijkstra theo cost canh | DUNG (chuan) | he automation cu |
| `automation/graph_memory.py` | `path` | Dijkstra theo do-tin-cay | **LOI** (return-on-discover) | he automation cu |
| `automation/maze_sim.py` | `path` | A*/Dijkstra tren grid | DUNG (chuan) | mo phong me cung (khong phai nav UI) |
| `scripts/graph.py` | `shortest_path` | BFS tren edge UI | DUNG (unweighted) | thu nghiem cu (UIGraph) |

## Phat hien (data-driven)

### BUG: graph_memory.path Dijkstra return-on-discover
```python
if to == dst: return nt   # SAI: tra ngay khi DISCOVER, chua chac toi uu
```
Dijkstra co weight phai return khi **POP** dst khoi PQ (da chac chi phi nho nhat).
Da chung minh: do thi A->B(dat) vs A->C->B(re), ham tra duong DAT (1 buoc) thay vi
duong RE (2 buoc) -> pha huy muc dich weight do-tin-cay. (screen_graph.path lam DUNG.)

### Trung lap chuc nang
- world_model.bfs_path va graph.shortest_path: ca 2 deu BFS tren do thi UI, gan
  giong het. graph.py la ban thu nghiem cu (UIGraph), khong dung trong Clean Arch.
- graph_memory.path va screen_graph.path: ca 2 Dijkstra weighted tren do thi UI,
  khac cong thuc cost (reliability vs edge_cost), 1 cai loi.

## Quyet dinh (senior)

**KHONG build moi.** Clean Arch da co duong di qua `WorldModelPort.path_to` ->
`world_model.bfs_path` (BFS dung). Day la path DUY NHAT dung trong production moi.

Hanh dong:
1. **Giu** `world_model.bfs_path` lam path chinh cua Clean Arch (da dung, da test).
2. **Sua bug** `graph_memory.path` (return-on-pop) - he cu van dung file nay.
3. **Nang cap** Clean Arch path_to: hien BFS unweighted. Game co edge "hay fail"
   (vd modal chan) -> nen co tuy chon weight do-tin-cay nhu graph_memory. Can
   nhac them sau, KHONG gap (BFS dung cho do thi UI on dinh).
4. **KHONG dung** graph.py/UIGraph (legacy thu nghiem) - de nguyen, khong dau tu.
5. maze_sim.py la mo phong me cung (research), KHONG lien quan nav UI - de nguyen.

## Tang 2 (OAS navigation) lam gi tiep
- Da co BFS dung trong Clean Arch. KHONG can viet thuat toan moi.
- Viec con lai: dung PAGE DETECTOR (landmark, da toi uu 25ms) lam nguon "dang o
  dau" cho navigate THAY dhash (dhash fail tren man dong - da chung minh 0/15).
  -> sua NavigateUseCase: match page -> resolve label -> path_to (BFS) -> act.
- Co the so do thi world_model (105 state) voi OAS page graph (38 page, 66 link)
  de phat hien edge thieu/sai, nhung do la viec data, khong phai thuat toan.
