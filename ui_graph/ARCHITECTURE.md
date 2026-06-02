# Kien truc UI State Graph (giai phap cho "qua nhieu UI")

> Muc tieu: bot LUON biet dang o UI nao, va tu dong tim duong di/ve giua bat ky UI nao.
> Lay cam hung tu Alas/OAS nhung don gian hoa cho ban EN + control PC window.

## Y tuong cot loi
Game = mot **do thi huong (directed graph)**:
- **Node (Page)** = 1 man hinh UI (vd: HOME, EXPLORE, REALM_RAID, SOUL, SHOP_KITTY...).
  Moi node duoc NHAN DIEN bang 1+ "anchor" (template ROI dac trung chi xuat hien o UI do).
- **Edge** = hanh dong chuyen tu node A -> node B (thuong la 1 click vao 1 nut).
  Co the kem dieu kien (vd nut "back", "close X", "go to town").

Khi chay: bot **bgshot -> nhan dien node hien tai** (match anchor cua tat ca node).
Muon den node X: chay **BFS/Dijkstra** tren graph -> ra chuoi edge -> thuc thi tung click,
sau moi click bgshot lai de xac nhan da sang node mong doi (retry neu chua).

## Cau truc thu muc
```
ui_graph/
  pages.yaml        # dinh nghia tat ca node: anchor (asset+roi), loai UI
  edges.yaml        # dinh nghia canh: from, to, action(click x,y / asset), back?
  graph.py          # load yaml, build graph, detect_current(), goto(target)
assets/
  <PAGE>/           # anh template cho moi page
    anchor_xxx.png
    btn_yyy.png
```

## Schema pages.yaml (vi du)
```yaml
HOME:
  desc: "San nha chinh / courtyard"
  anchors:                # match TAT CA (hoac >=1 tuy mode) de xac nhan dang o HOME
    - asset: HOME/explore_btn.png
      roi: [560, 150, 110, 80]   # x,y,w,h vung tim
      threshold: 0.8
  is_root: true           # node goc, moi duong "ve nha" huong toi day

EXPLORE:
  desc: "Ban do chuong (Realms Gates)"
  anchors:
    - asset: EXPLORE/realms_gates_label.png
      roi: [10, 410, 160, 40]
  close_to: HOME          # nut back/X cua page nay dan ve dau
```

## Schema edges.yaml (vi du)
```yaml
- from: HOME
  to: EXPLORE
  action: { type: click, x: 612, y: 188 }   # nut Explore
- from: EXPLORE
  to: HOME
  action: { type: click, x: 28, y: 70 }     # nut back goc tren trai
- from: EXPLORE
  to: SOUL
  action: { type: click, x: 168, y: 615 }   # nut Soul (御魂)
```

## detect_current()
1. bgshot.
2. Voi moi PAGE, match toan bo anchors (template matching, threshold).
3. Tra ve page co diem khop cao nhat / thoa man. Neu khong khop -> UNKNOWN.
   - UNKNOWN xu ly: thu cac nut "thoat chung" (close X goc phai, back goc trai, tap vung trong)
     de ve mot node da biet (recovery).

## goto(target)
1. cur = detect_current().
2. neu cur == target: xong.
3. duong = shortest_path(cur, target) tren graph.
4. for edge in duong: thuc thi action; cho; bgshot; assert detect_current()==edge.to (retry N lan).
5. neu lac (detect ra node khac): replan tu node hien tai.

## Vi sao mo hinh nay giai quyet van de cua ban
- "Nhieu UI co nut tat/an/thoat/ve sanh/ra town khac nhau" => moi cai la 1 EDGE rieng,
  khai bao 1 lan, dung lai mai. Khong can nho thu cong.
- "Kho thao tac & nho" => bot tu nhan dien (anchor) + tu tim duong (graph search).
- Mo rong: them UI moi = them 1 node + vai edge, khong dung code logic.

## Lo trinh xay
1. [ ] Viet graph.py (load yaml, template match qua cv2, detect_current, goto/BFS).
2. [ ] Map dan cac node CHINH bang bgshot, cat anchor asset, dien pages/edges.yaml.
3. [ ] Test goto giua vai node (HOME<->EXPLORE<->SOUL...).
4. [ ] Mo rong dan toan bo cay UI.
EOF
