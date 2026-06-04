# THUAT TOAN & MAU HOC CHO BOT - DE XUAT (2026-06-04)

Tai lieu nay de xuat cach bot HOC tot hon, dua tren bang chung tu 44-node map.
Khong noi chung chung: moi de xuat gan voi 1 van de da DO duoc.

## A. VAN DE DA DO DUOC (tu data)

| Van de | Bang chung | Tac dong |
|---|---|---|
| Loading screen tao node rac | 8-10/44 node "onmyoj*" cands=0 | Phong graph, lac duong |
| Menu chinh (footer text) NOOP | summon/town/team/shop click -> noop | KHONG vao duoc tab chinh |
| Window off-screen 4047,-72 | politeclick footer that bai | Goc man duoi/tren khong click duoc |
| same_screen ko gop loading | onmyojil/onmg vs onmyojil/nmyg = 2 node | Trung lap |
| frontier loop chua chay manh | explore Home ngon het action | Khong lan toi vung xa |
| Khong biet node nao "huu ich" | tat ca node can bang nhau | Phi cong kham pha popup vo nghia |

## B. DE XUAT THUAT TOAN (uu tien theo ROI)

### B1. STATE = (screen_class, affordances) thay vi text_signature tho
Hien tai node = chu ky OCR tho -> nhay cam nhieu + loading.
DE XUAT: phan loai man thanh LOAI (home/menu/battle/popup/loading/reward/dialog)
bang luat + template, roi node = (loai, tap affordance chinh). Loading/popup
gop chung 1 lop -> KHONG phong node.
  - reward/popup: co nut "Confirm/OK/Claim/Tap to continue" -> auto-dismiss,
    KHONG coi la diem den dang hoc.
  - battle: co thanh HP + "Auto" -> trang thai farm, KHONG explore.

### B2. CLICK ROBUST: thu DAY DU 3 method + verify (giai quyet footer noop)
Hien noop-retry chi thu 2 method. Window off-screen khien politeclick fail.
DE XUAT thu tu fallback cho MOI click quan trong:
  1. bgclick (SendMessage) -> nhanh, nav thuong
  2. politeclick (mouse that) -> can foreground
  3. TRUOC politeclick: di chuyen window ve man chinh (SetWindowPos 0,0) +
     SetForegroundWindow, click, tra lai. (Hien restore khong move window!)
  4. fgclick / double-tap
Moi buoc verify bang same_screen; dung khi man doi. -> footer menu se an.
  => DAY la fix goc cho ca nut Bonus lan summon/town footer.

### B3. EXPLORATION = UCB/novelty thay vi DFS thuan
DFS thu het cand 1 node moi sang node khac -> phi thoi gian o popup.
DE XUAT diem uu tien moi cand:
  score = w1*novelty(man dich uoc luong moi?) + w2*menu_word + w3*(1-popup_prob)
          - w4*lan_da_thu_that_bai
Chon cand diem cao nhat toan cuc (priority queue), KHONG DFS cung node.
  - novelty: cand dan toi text_signature chua tung thay -> diem cao.
  - epsilon-greedy: 10% chon ngau nhien de khong ket cuc bo.

### B4. AFFORDANCE LEARNING: hoc "loai nut" tu hau qua
Ghi cho moi cand: (vung man, mau, hinh dang) -> ket qua (nav/noop/popup/back).
Sau N mau, train luat nhe (decision tree) du doan: "icon goc phai-tren =
banner 85% -> bo qua". Bot tu hoc skip rac thay vi hardcode MENU_WORDS.

### B5. GOAL-CONDITIONED: hoc duong DEN muc tieu (vd "farm soul")
Map hien la kham pha mu. DE XUAT them lop nhiem vu:
  - dinh nghia goal bang OCR-predicate (vd reach screen co "soul"+"realm"+"challenge")
  - dung graph da hoc + BFS de tu navigate toi goal (da co _bfs_path!)
  - neu chua co duong -> explore co dinh huong (frontier gan goal nhat).

## C. MAU HOC (data schema de tich luy & train sau)

### C1. Transition samples (da co 1 phan trong jsonl)
Moi action ghi: {from_fp, cand:(x,y,label,src,region,color,shape),
                 method, result, to_fp, to_class, dt_ms}
-> dataset du doan "cand nay click se di dau / co noop khong".

### C2. Screen samples
Moi man: {fp, class(nhan tay/luat), shot_path, affordances[], is_terminal}
-> train phan loai man (B1).

### C3. Episode/trajectory cho goal
Chuoi (screen, action, reward) toi khi dat goal -> sau nay RL/imitation.

## D. LO TRINH THUC TE (lam gi truoc)
1. B2 (click robust + move window) - GO BO TRAN GOC, footer/Bonus se an. CAO NHAT.
2. B1 (screen_class + auto-dismiss popup) - giam node rac, sach graph.
3. B3 (novelty/UCB ordering) - kham pha hieu qua hon DFS.
4. C1+C2 (ghi sample co cau truc) - chuan bi train affordance (B4).
5. B5 (goal-conditioned) - chuyen tu "ban do" sang "lam viec" (farm/daily).

Ghi chu: B2 quan trong nhat - hien NHIEU nut menu chinh noop CHI vi window
off-screen. Sua xong se mo khoa phan lon game ma cac fix khac khong lam duoc.
