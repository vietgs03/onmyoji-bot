# PROMPT cho Agent Opus: Mo rong Bot Onmyoji sang Battle/Farm + Kien truc Hoc qua Ma tran Da chieu + Graph Memory

> Doc ky toan bo truoc khi lam. Tra loi tieng Viet. Co quyen tu chu, persist den xong.
> Khong hardcode toa do. Validate bang so lieu thuc, khong tuyen bo suong.

---

## 0. BOI CANH (doc `knowledge/LEARNINGS.md` + `MEMORY_TREE.json` truoc)

Bot dieu khien game **Onmyoji Global/EN** (Steam PC, NeoX engine) tu WSL/Linux qua
PowerShell server (`ps/server.ps1`) + Win32. Man hinh 1152x679.

**Da lam duoc (validated):**
- Dieu khien: 3 loai click `sendclick`(SendMessage, nav thuong) / `politeclick`(real
  mouse, tin cay nhat cho modal nhan thuong) / `fgclick`. NeoX BO QUA PostMessage.
- `automation/state_solver.py`: StateSolver giai man huong-dich (goal predicate) bang
  search + Q-learning. **VUA SUA loi chi mang**: state-key truoc dung dhash+OCR bat ky
  -> moi frame 1 key (Q vo dung). Gio `ui_tokens()` (chi nhan UI on dinh) + `match_state()`
  Jaccard >=0.5 -> cung man = cung state-id. Do: 8 frame HOME -> 1 state-id (truoc 6/6).
- `automation/screen_map.py`: ScreenMap.explore() kham pha vet can 1 man (liet ke
  affordance, thu, ghi tac dung). **CHU Y**: `screen_key()` cua no VAN CON loi dhash
  giong solver cu -> can sua giong (dung ui_tokens + Jaccard).
- `tasks/run.py`: claim_dolls (nhan qua doll san HOME, khong hardcode), claim_home
  (quet badge do), daily (doc `knowledge/daily_tasks.json`).
- `scripts/perception.py`: dhash, detect_red_badges, detect_courtyard_dolls, detect_buttons.

**Tai nguyen tham khao (CHI doc, dung copy code CN):**
- `research/OAS/` = OnmyojiAutoScript (bot CN lon nhat). 60 task. Dung TEMPLATE matching
  + page-graph (`ui_goto`) + image assets. Ta KHAC: OCR-semantic + state-matrix + learn.
- `knowledge/oas_features.json` = 52 task da trich (options + script_methods). DUNG file
  nay de biet game co MODE gi va MOI mode lam gi.
- `knowledge/oas_pagegraph.json` = 38 page + canh nav cua OAS (tham khao topology game).
- `knowledge/screen_graph.json` = 24 node nav tay (identify/exits) ta da dung.

---

## 1. MUC TIEU (3 phan, lam tuan tu)

### PHAN A — Khao sat: game co nhung TASK/BATTLE gi
Tu `oas_features.json` + `oas_pagegraph.json`, lap **danh sach day du cac che do battle/farm**
quan trong (uu tien core farming): **Exploration (farm soul + chapter), RealmRaid (突破),
Orochi/Sougenbi/EternitySea (Soul Zones - farm御魂), AreaBoss, Hunt, Duel, DemonEncounter,
BondlingFairyland, WantedQuests...**. Voi MOI mode ghi: muc tieu (farm gi), flow chinh
(cac buoc/man), dieu kien thang/thua, reward. Luu ra `knowledge/game_tasks.json` co cau truc.

### PHAN B — Kien truc HOC qua MA TRAN DA CHIEU (cot loi, theo yeu cau user)
User nhan manh: **moi screen KHONG phai 1 chieu. Phai mo ta bang MA TRAN DA CHIEU** de
tranh bot "nhin sai khong gian" (game co khong gian rat rong). Hien `state_sig` chi la
1 vector tap-token (1 chieu ngu nghia). Phai nang cap thanh **ma tran dac trung nhieu chieu**:

Moi screen = mot **feature matrix** gom cac CHIEU (dimension) doc lap, vi du:
- **Chieu khong gian (spatial)**: chia man thanh luoi (vd 4x4 hoac 6x4 cell). Moi cell co
  dac trung: co text gi (OCR theo vung), co nut/icon gi (CV), mau chu dao, co badge do
  khong, co nhan vat/doll khong. -> Ma tran [rows x cols x features]. Day moi la "khong
  gian 2D" thay vi gom het thanh 1 bag-of-words.
- **Chieu ngu nghia (semantic)**: tap nhan UI on dinh (da co ui_tokens), tu khoa chuc nang.
- **Chieu cau truc (structural)**: layout dhash THEO VUNG (per-region, on dinh hon dhash
  toan man), co popup/modal khong (vung trung tam toi/sang), co thanh tab khong.
- **Chieu thoi gian/dong (temporal)**: cai gi DANG dong (animation, dem nguoc, battle) -
  giup phan biet "dang trong tran" vs "man tinh".

> **INSIGHT SLAM (user dat ra + DA CHUNG MINH THUC NGHIEM session nay):**
> Mot so screen (vd HOME courtyard) la KHONG GIAN RONG HON MAN HINH. Camera = cua so truot;
> PAN 4 huong lo "cac buc tuong xung quanh" (Forum/Support trai, doll, icon...). Mo hinh
> 1-chieu/1-frame=1-state thi MOI lan pan ra 1 state moi -> "sweep nhin sai khong gian".
> Giai dung = **SLAM/panorama mosaic** (chinh la y "ma tran 4 chieu" cua user):
> - chieu 1,2 = toa do camera (cx,cy) tren mat phang screen, uoc luong dich chuyen giua 2
>   frame lien tiep bang ORB/optical-flow tren VUNG TINH (courtyard giua dong nhieu -> MASK,
>   chi match top-bar/footer/cot icon phai).
> - chieu 3 = ban do affordance toa do TUYET DOI tren panorama (khong doi theo camera).
> - chieu 4 = tach lop DONG (sakura/nhan vat/doll) khoi lop UI TINH.
> Da do thuc te: pan -> ORB do duoc dx=-285px (Explore dich 795->453px) => CUNG 1 khong gian
> khac goc nhin. State HOME on dinh = panorama. Muon bam 1 affordance -> tra toa do tuyet doi
> -> pan camera den khi no vao khung -> bam. Phan loai screen: **spatial (can SLAM, vd
> courtyard) vs flat (1 frame=full state, vd menu battle)**. Anh test luu o /tmp/pan{0,1}.png.

So khop 2 screen = so khop ma tran (vd weighted similarity tung chieu), KHONG phai chi
Jaccard 1 vector. Thiet ke sao cho: 2 frame cung man (du animation/chat doi) -> match;
2 man khac nhau (vd Orochi vs RealmRaid) -> KHONG match du co the chia nhieu token chung.
=> Validate: do confusion (frame cung man match, frame khac man khong match) tren bo anh thuc.

### PHAN C — GRAPH MEMORY + FEATURE + INDEX (theo yeu cau user "graph feat graph memory va index")
Xay **bo nho dang DO THI (graph)** lam tang tren state-matrix:
- **Node** = 1 state (screen) dac trung boi feature-matrix o PHAN B. Node luu: feature
  matrix dai dien, nhan ngu nghia (label, vd 'orochi_layer_select'), affordance da hoc
  (tu screen_map), so lan ghe tham, gia tri (gan goal nao).
- **Edge** = chuyen trang thai: (node_A) --[action]--> (node_B), co xac suat/chi phi/so
  lan thanh cong. Action mo ta NGU NGHIA (tap:'Challenge', back, swipe:left...) khong toa do.
- **Feature index**: de tim node nhanh khi quan sat 1 frame moi -> dung **index** (vd
  vector embedding cua feature-matrix -> nearest neighbor, hoac LSH/ball-tree) thay vi
  quet tuyen tinh O(n) qua moi node (se cham khi game co hang tram man).
- **Graph feature**: tinh dac trung dua tren VI TRI trong do thi (vd: node nay cach HOME
  may buoc, co bao nhieu loi ra, co thuoc cum 'battle' khong) -> giup dieu huong + hoc.

Bo nho graph luu `knowledge/screen_graph_memory.json` (hoac SQLite/networkx pickle neu
lon). Phai co API: `observe()->node_id`, `add_transition(a,action,b)`, `path(a,b)` (BFS/
Dijkstra tren graph de dieu huong toi 1 man bat ky), `nearest(frame)->node_id` (qua index).

---

## 2. NGUYEN TAC THIET KE (BAT BUOC)

1. **Khong hardcode toa do.** Toa do chi tinh tai-thoi-diem tu OCR/CV. Bo nho luu NGU
   NGHIA (text, vung tuong doi, loai affordance) + ma tran dac trung, khong luu (x,y) cung.
2. **Ma tran DA CHIEU, khong 1 chieu.** (Yeu cau cot loi cua user.)
3. **Hoc duoc + tai su dung.** Validate: cung man -> cung node qua nhieu lan; Q/edge tich luy.
4. **Co INDEX.** Tim node O(log n) hoac tot hon, khong O(n) tuyen tinh.
5. **Tu duy reproduce + metric.** Truoc khi sua, do baseline. Sau khi sua, do lai. Vi du:
   - State stability: N frame cung man -> bao nhieu node? (muc tieu = 1)
   - Cross-screen confusion: ma tran similarity giua cac man khac nhau (muc tieu: trong-cum
     cao, ngoai-cum thap, tach bach ro).
   - Navigation success: tu man X bat ky, `path()` dua ve HOME / toi mode Y, ti le thanh cong.
6. **An toan battle.** Khi cham toi farm that: mac dinh DRY (chi doc/mo ta flow). Chi danh
   tran that khi co co `--live`. KHONG tieu jade/ve/skey tru khi user mo. Log moi tran.
7. **Commit theo buoc**, conventional-commit, comment/commit tieng Viet khong dau.
8. Dung `.venv/bin/python`, chay script voi `python -u`. Doc `knowledge/LEARNINGS.md` muc 8-9.

---

## 3. THU TU LAM (de xuat)

1. Doc LEARNINGS.md, MEMORY_TREE.json, state_solver.py, screen_map.py, perception.py,
   screen_graph.json, oas_features.json. Hieu da co gi.
2. **PHAN A**: trich `knowledge/game_tasks.json` (cac mode battle/farm + flow + goal).
3. **PHAN B**: thiet ke + cai `automation/state_matrix.py` (feature-matrix da chieu +
   ham similarity). Validate confusion tren anh thuc (chup nhieu man: HOME, Explore,
   Orochi, RealmRaid, battle prepare...). Sua `screen_map.py` dung chung (bo loi dhash).
4. **PHAN C**: cai `automation/graph_memory.py` (node/edge/index/path/nearest). Tich hop
   vao StateSolver (thay match_state 1-chieu bang nearest tren graph da-chieu).
5. **Tich hop battle**: viet 1 task farm THAT (vd Orochi hoac RealmRaid) dung graph de
   dieu huong toi man, dung state-matrix de nhan biet dang o dau (chon team / dang danh /
   thang-thua / nhan reward). Test DRY truoc, roi --live 1-2 tran co log.
6. Cap nhat `knowledge/LEARNINGS.md` + `daily_tasks.json` + MEMORY_TREE. Commit.

---

## 4. CACH VALIDATE (vi du cu the, lam thuc su dung chi tuyen bo)

```python
# State stability: cung man -> 1 node
ids = [solver.observe()[-1] for _ in range(8)]   # chup 8 lan man dung yen
assert len(set(ids)) == 1, f"khong on dinh: {len(set(ids))} node"

# Cross-screen: man khac nhau -> node khac, similarity thap
sim_home_orochi = matrix_similarity(feat(home_img), feat(orochi_img))
assert sim_home_orochi < 0.5

# Navigation: tu man bat ky ve HOME qua graph.path
ok = navigate(graph, target='HOME'); assert ok
```

Tao bo anh test trong `tests/screens/` (chup that tu game): home, explore, orochi_*,
realmraid_*, battle_prepare, battle_win, soul_reward... De do confusion lap lai duoc.

---

## 5. LUU Y KY THUAT (da hoc, dung lap lai loi)

- `ocr_words(img, min_conf=40)` tra list (text, (x,y,w,h), conf). Conf cao = it jitter.
- OCR jitter: 'Onmyoji'/'Onmyojt', 'Friends'/'Fhienas'. Dung conf>=70 + fuzzy/Jaccard.
- Token NHIEU phai loai khoi chu ky: dong chat the gioi (cau dai >15 ky tu, nhieu tu),
  dong ho (co so/':'), ten nguoi choi, currency. (Xem `_NOISE_WORDS`, `_TIME_RE`.)
- dhash TOAN MAN nhieu vi animation. Neu dung, dung **per-region dhash** (perception.dhash
  co tham so per_region) chi o vung UI tinh.
- Footer HOME 11 nut: Collection/Traveler's Stop/Warehouse/Team/Guild/Shop/Talisman Pass/
  Friends/Onmyoji/Shikigami. HOME signature on dinh: Explore+Summon+Town+Seal+Guild+Shop.
- Vao Exploration tu HOME: tap 'Explore'. Trong Exploration co Realm Raid/Soul Zones/Area
  Boss (xem screen_graph.json node 'exploration').
- Battle flow chung (tu OAS GeneralBattle): prepare-highlight -> danh -> 'Failed'/'Win' ->
  'Tap to continue' -> reward. Soul reward man co the random-click de nhan.

---

## 6. KET QUA MONG DOI

- `knowledge/game_tasks.json`: ban do cac mode battle/farm + goal + flow.
- `automation/state_matrix.py`: feature-matrix da chieu + similarity, co test confusion.
- `automation/graph_memory.py`: graph node/edge + index + path + nearest, co test.
- `screen_map.py` + `state_solver.py` dung chung state-matrix (bo het loi dhash 1-chieu).
- It nhat 1 task farm THAT (Orochi/RealmRaid) dieu huong bang graph, nhan biet bang matrix,
  test DRY + 1-2 tran live co log + so lieu.
- LEARNINGS.md cap nhat. Commit tung buoc.

Bat dau bang viec doc cac file o muc 0 va in ra hieu biet + ke hoach cu the truoc khi code.
