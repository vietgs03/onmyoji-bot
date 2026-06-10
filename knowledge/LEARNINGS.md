# TỔNG KẾT KIẾN THỨC - Onmyoji Bot (cập nhật 2026-06-04)

> Tài liệu tổng hợp MỌI thứ đã học để bot/người tiếp tục. Nguồn sự thật duy nhất
> (single source of truth) cho hệ thống. Đọc file này trước khi làm bất cứ gì.

---

## 0. BỐI CẢNH
- Game: **陰陽師 Onmyoji** bản **Global/EN**, chạy như **cửa sổ Steam PC** (KHÔNG phải emulator).
- Agent chạy WSL/Linux, điều khiển game Windows qua `powershell.exe` + Win32 API.
- Cửa sổ game: **1152x679**, process `Client`, title khớp `Onmyoji|陰陽師|阴阳师`.
- Mục tiêu: bot **tự học** toàn bộ chức năng game (graph + ngữ nghĩa + tri thức),
  rồi **tự động hóa** các tác vụ (daily, farm soul, summon...). KHÔNG hardcode kiểu OAS.

## 1. HẠ TẦNG ĐIỀU KHIỂN (đã chạy ổn)
- **Server PowerShell thường trú** (`ps/server.ps1`) deploy ở `C:\Users\Public\onmyoji_server.ps1`.
  - Lệnh: `ping | info | bgshot <path> | bgclick x y | fgclick x y | pmclick x y | restore | quit`.
  - `control_client.py` tự sync server.ps1 sang Windows theo mtime, spawn server mới mỗi Controller().
- **BÀI HỌC LỚN: `bgclick` (PostMessage nền) KHÔNG hoạt động trên modal/popup.**
  Đã chuyển `bgclick` -> **foreground click thật** (`Do-FgClick`: SetForegroundWindow +
  SetCursorPos theo GetWindowRect + mouse_event). Tin cậy trên MỌI popup. Đánh đổi: cướp chuột/focus.
- **Auto-restore**: bgshot tự `ShowWindow(SW_RESTORE)` nếu cửa sổ bị minimize (rect quá nhỏ).
- bgshot ~1.2s (spawn PowerShell). Tối ưu tương lai: giữ 1 session pipe -> <0.3s.
- **TUYỆT ĐỐI KHÔNG click (1115,78)** = nút X cửa sổ game (tắt game!).
- Ảnh server lưu: `C:\Users\Public\onmyoji_srv.png`. Bash foreground timeout 120s.

## 2. KIẾN TRÚC 3 TẦNG (self-learning model)
### Tầng 1 - PERCEPTION (`scripts/perception.py`)
- `dhash(img)`: hash 4 **VÙNG TĨNH** (STABLE_REGIONS) -> state ID ổn định với animation.
  Tránh vùng nhân vật động + cây sakura + chat. Trả None nếu ảnh hỏng/rỗng (chống crash).
- `is_loading(img)`: màn loading/chuyển cảnh rất tối -> chờ qua.
- `detect_buttons(img)`: Hough circles + vùng saturation cao (nút cam/đỏ) + NMS -> nút ứng viên.
- `find_close_button(img)`: tìm nút X đóng popup (gồm white-X detection cho character showcase).

### Tầng 2 - WORLD MODEL (`scripts/world_model.py`)
- State = node (dhash), click -> transition = edge. Lưu `exploration/world.json`.
- `canonicalize`: gộp màn gần giống (hamming <= CANON_THR=12).
- `_logical(sid)` = `L:<label>` nếu có nhãn, ngược lại sid. **bfs_path chạy trên node LOGIC**
  (mọi state cùng nhãn share cạnh) -> navigate chính xác dù có nhiều biến thể HOME vật lý.
- `bfs_path(src,dst)`: đường click ngắn nhất, goto bất kỳ đâu.

### Tầng 3 - SEMANTICS (`scripts/label_states.py`, `build_graph.py`)
- AI vision gán label + desc cho mỗi state. `build_graph.py` gộp theo label -> graph logic + mermaid.
- KB (data/) cung cấp tên shikigami/soul/mode -> ánh xạ vào màn.

## 3. EXPLORER (`scripts/explorer.py`) - vòng lặp tự khám phá
Chiến lược chống kẹt đã hoạt động:
- **Frontier-based**: hết nút ở màn này -> BFS tới màn gần nhất còn nút chưa thử (không chỉ về HOME).
- **Logical BFS**: dùng `_logical` khắp nơi cho is_home/frontier/home compare.
- **HOME auto-label**: nhiều biến thể HOME vật lý (~13, animation) -> auto gán nhãn "HOME".
- **Anti-loop**: oscillation guard (12 state gần cycling <=2 -> nhảy frontier), unreachable blacklist,
  `deep_escape` cho màn 3D/animation/summon, `home_fails>=2` -> deep_escape.
- **AN TOÀN TRẬN ĐẤU** (mới): `is_battle()` phát hiện hộp thoại "leave battle"/màn kết quả Failed/Win;
  `handle_battle()` tự Confirm rời trận / tap-to-continue; né nút Challenge (x>980,y>540).
- **Robust**: ảnh hỏng -> retry 5 lần (không crash/dừng hẳn).

## 4. KẾT QUẢ KHÁM PHÁ HIỆN TẠI
- **105 state vật lý, 185 edge**, gộp thành **18+ chức năng game logic**:
  HOME, Event, Explore, Town, Summon, Shikigami, Shrine Pass, Shop, Settings, Friends, World,
  Mentor, Select Champion, Create Float, Character Showcase, Event Overview, Animation, Loading.
- 130 screenshots ở `exploration/screens/`. 17 state mới chưa label.
- **Dữ liệu training**: `exploration/observations.jsonl` = **594 click samples**
  (205 transition + 389 noop + 19 new_state). Đây là vàng cho ML affordance.

## 5. CÁC MÀN GAME ĐÃ PHÁT HIỆN (qua vision)
- HOME (sân nhà): Explore/Town/Summon + footer 11 nút (Collection/Traveler's Stop/Warehouse/
  Team/Guild/Shop/Talisman Pass/Friends/Onmyoji/Shikigami) + Event/Yard + side icons.
- Explore: bản đồ chương (ch 26-28), quest locations, stage challenge (Doujo boss) -> CÓ NÚT Challenge (vào trận!).
- Town: Arena, Demon Parade, Mystic Trader; Character Showcase.
- Summon: Summon Room (Normal/Free/Jade), animation rút thẻ.
- Shikigami Collection: footer Cos/Shiki/Soul/Boss/Skin/Area/Pet/Paper Doll/Portfolio/Dance.
- Shrine Pass/Mystic Scroll (battle pass), Event Overview (skin shop), Spring Parade event,
  Wisdom Ignited story, Frozen Treasure, Wanted Quests, Return Benefits.
- Settings (Audio/account/birthday/avatar frame), Mailbox, Friends/chat, World chat.
- **Illumination Path** = màn boss challenge (nút Challenge -> battle). Battle result "Failed/Win" + "Tap to continue".

## 6. KNOWLEDGE BASE (`data/fandom/*.json`, tra cứu `scripts/kb.py`)
- **269 shikigami** (SP48/SSR82/SR68/R38/N30): id, name_en/cn/jp/gl, rarity, skill, evolve.
- **69 souls/御魂**: type, combo2, combo4 (set bonus). Hệ trang bị cốt lõi để farm.
- **26 game modes**: Exploration, Realm Raid, Soul zones (Orochi/Sougenbi/Sea of Eternity),
  Secret Zone, Area Boss, Bondling, Hunt, Demon Encounter, Hyakki Yakou, Duel, Kekkai, Totem...
- Nguồn: onmyoji.fandom.com (API OK). guidemyoji/huijiwiki bị Cloudflare chặn.

## 7. ƯU TIÊN TIẾP THEO (cho buổi học tối nay)
1. Label 17 state mới + chạy explorer phủ nốt game (deep sub-screens).
2. **Screen classifier ML**: train phân loại màn từ ảnh (thay/bổ trợ dhash) -> nhận diện cả màn chưa thấy.
3. **Affordance model**: từ 594 samples, học "click (x,y) ở màn X có dẫn đi đâu" -> explore thông minh hơn.
4. **OCR** nút/số liệu (tesseract có sẵn) -> label tự động, đọc AP/tiền/vé.
5. **Task automation**: navigate (BFS) + thực thi (daily sign-in, farm Exploration/Soul, summon).
6. **Reward/goal model**: mỗi mode gắn mục tiêu (Realm Raid=farm soul) từ KB.

## 8. QUY TẮC KỸ THUẬT (BẮT BUỘC)
- Dùng `.venv/bin/python` cho mọi script cv2/ML.
- Python stdout block-buffered khi redirect -> chạy explorer với `python -u`.
- Commit theo từng bước. `.pyc`, `.venv`, `research/OAS/`, `captures/*.png` gitignored.
- Người dùng giao tiếp tiếng Việt -> trả lời tiếng Việt.

## 9. DAILY TASK (hang ngay tren HOME) - LUU O knowledge/daily_tasks.json
Chay: `.venv/bin/python tasks/run.py daily --live` (hoac --dry de xem truoc).
Routine doc tu `knowledge/daily_tasks.json` (NGUON SU THAT, them task moi vao file la xong).

**Cac viec hang ngay da hoc:**
1. **claim_dolls** - cac con DOLL CAM QUA trong san HOME (KHONG hardcode toa do):
   - `perception.detect_courtyard_dolls()` nhan dien doll than trang cam vat pham
     (hop go 'Lot' = diem danh, the do = task/reward) bang dac trung anh.
   - Doll 'Lot' -> Daily Lot (rut omikuji, ~100 jade). Doll the do -> Claim Gifts
     (Exclusive Gifts: AR Amulet/Demon Parade Pass/AP50/Orochi Scale50...) hoac
     Claim Reward (10000 coin).
   - Bo qua: doll Interact/Wish/Decors (decor), Characters (nhan vat), Mentorship.
2. **claim_mail** - mail goc tren phai -> 'Claim All' -> dialog OK (fgclick/politeclick).
3. **claim_home_badges** - quet badge do `detect_red_badges(ui_only=True)` -> tap -> Claim.

**3 LOAI CLICK (rat quan trong, NeoX dac thu):**
- `sendclick` (SendMessage): dieu huong thuong. NeoX BO QUA PostMessage (`pmclick`).
- `politeclick`: real mouse + tra chuot ve cho user. TIN CAY NHAT cho modal nhan
  thuong (vd 'Claim' Exclusive Gifts). Dung ClientToScreen (chinh xac).
- `fgclick`: real mouse foreground. Cho modal cung, NHUNG doi khi tra OK ma popup
  khong dong -> uu tien politeclick.
- ClientToScreen thay GetWindowRect (GetWindowRect gom title bar -> lech ~30px).

## 10. Cay menu day du + PHAN LOAI node (screen_graph 40 node)
Da MERGE cau truc cha-con tu OAS pagegraph (38 page) vao `automation/screen_graph.py`
(truoc 24 node, gio 40). KHONG lam lai tu dau - cay dieu huong da co san (Dijkstra
goto/path/where/escape). Chi bo sung node thieu + them PHAN LOAI.

Moi node co 3 nhan moi (de agent HIEU ban chat, khong dieu huong mu):
- `kind`: "flat" (1 frame = tron man, da so) | "spatial" (khong gian rong hon man,
  pan lo them -> can panorama/SLAM; chi HOME/guild/fairyland/hyakkiyakou).
- `category`: hub|combat|pvp|event|util|social|idle -> gom nhom muc tieu.
- `verified`: True = identify/toa do kiem chung LIVE; False = suy tu OAS/ten game EN,
  bot PHAI tu xac minh & sua khi toi (16 node con False, vd goryou/kekkai/dokan).

Phan bo: kind={spatial:4, flat:36}, category={combat:15, util:12, event:4, hub:3,
social:3, pvp:2, idle:1}. 16 node chua kiem chung (toa do exit bo trong -> bot tim
qua OCR text khi den hub cha).

Quan trong: them man = them 1 entry DATA trong NODES (khong sua thuat toan). Node
moi verified=False -> khi bot toi noi & nhan dien dung thi nang len True (hoc dan).

## 11. Toi uu THUC THI nav (sau action dai do hieu qua) - 2026-06-04
Chay nav_tour.py (action dai giong scheduler OAS) phat hien 3 diem yeu THUC THI
(graph dung nhung cham/fail). Da fix het, do duoc:

1. **OCR la nut that** (~5-7s/lan, goi nhieu lan/hop). FIX: cache OCR theo hash
   noi dung anh (ml/ocr.py `_OCR_CACHE` LRU 16). Cung anh OCR lai: 7.68s -> 0.012s.
2. **Footer HOME (Friends/Shop/Guild/Shikigami) KHONG nhan SendMessage** -> can
   politeclick (chuot that). FIX: Agent.click(polite=True) + danh dau exit footer
   `"polite": True`. Bo `text` o footer (tap_text click trung label cho khac).
3. **goto lap 12 hop vo ich khi ket** (click khong doi man). FIX: phat hien stuck
   (di canh ma cur==src cu) -> lan dau doi cach click (center), >=3 lan -> phat cost
   nang + escape re-plan. Bo som thay vi 170s.
4. **Bug nhan dien**: man Shikigami THAT co tu 'Showcase/Promote/Liking' trung
   overlay char_showcase -> bi dismiss oan -> loop. FIX: char_showcase avoid
   'Preset'/'Shikigami'. (Tuong tu friends: identify cu sai, doi sang Co-op/Send/Online.)

KET QUA tour daily 6 chang (truoc/sau):
  truoc fix: 1/3 toi dich, ~138s/chang, friends treo 165s.
  sau fix:   6/6 toi dich. exploration 42s, town 34s, friends 16s, shop 13s,
             summon 21s, shikigami 21s. TB ~24s/chang.
=> Bai hoc: graph/cay menu dung la chua du - tang THUC THI (click type dung, cache
OCR, thoat ket som, identify khong trung overlay) moi cho bot chay task dai on dinh.

## 12. Action dai 'full' (11 chang) lan 2 - bug NHAN DIEN + cau truc cay - 2026-06-04
Chay tour 'full' (sau khi co OCR cache + footer politeclick) lo them 5 bug. Da fix het:

1. **identify cum 2 tu KHONG BAO GIO match** (anh huong 21 node). OCR tach
   'Soul Zones'->'Soul'+'Zones', nhung identify luu nguyen cum -> node con cua
   exploration (soul_zones, realm_raid...) loop 200-250s. FIX: `_expand_identify()`
   tach moi cum thanh tu don luc import (NODES+OVERLAYS). soul_zones 204s-FAIL -> 42s-OK.
2. **overlay 1-token-fuzzy false-positive**: group_buying['Group','Buying'] khop oan
   rac OCR o HOME (conf 0.5 = 1/2 token) -> resolve thay vi click footer -> friends
   loop 147s. FIX: detect_overlay yeu cau >=2 token khop (field `min_hits`, default 2
   cho overlay >=2 token; =1 cho bien the cung tu nhu Privilege/Privileges).
   friends 147s -> 18s.
3. **node generic CUOP dich**: man Summon co 'shrine'+'Scrolls' -> shrine_pass
   (identify Shrine/Pass/Mystic/Scroll) khop 2/4 = thang summon 2/2 vi depth sau hon.
   FIX: them COVERAGE (hits/len_identify) vao rank `_match`:
   (hits, verified, coverage, depth). Node khop HET thang node khop 1 phan.
   summon 179s-FAIL(lac shrine_pass) -> 29s-OK.
4. **fuzzy 0.80 qua long**: 'Friends'~'Friendly'=0.80 khop oan. FIX: has() default
   fuzzy 0.80 -> 0.86 (van dung sai OCR 1 ky tu: 'Realm'~'Realmm'=0.91).
5. **cau truc cay OAS sai**: (a) kekkai_toppa = TEN NHAT cua chinh Realm Raid (突破結界
   PvP) -> node TRUNG -> xoa. (b) demon_encounter: canh town->demon text 'Encounter'
   tro vao NHAN TINH trong Town, click khong mo -> ha verified=False, ghi survey.
   => Bai hoc: node verified=False tu OAS CO THE bia/trung/sai parent. Action dai la
   cach DUY NHAT phat hien (goto loop dai = co bug). Da them survey node chua verified
   vao nav_tour (logs/node_survey.jsonl) de tu hoc token that.

KET QUA: 6/6 chang daily OK ~20-29s. Node con exploration (soul_zones/realm_raid) OK.
39 node (sau xoa kekkai). 16 node con verified=False can kiem chung tiep.

## 13. Farm engine - may trang thai battle qua OCR (automation/farm.py) - 2026-06-04
Build engine farm GENERIC (khong hardcode toa do): moi vong doc OCR -> nhan TRANG
THAI battle -> chon HANH DONG (data-driven ACTIONS). 5 trang thai chung moi che do:
  SELECT (co Challenge/Lineup/Rewards Preview) -> tap Challenge vao tran
  PREPARE (Ready/Start) -> tap Ready
  FIGHTING (Surrender; dang danh) -> CHO (None state cung = dang danh -> wait)
  RESULT (Tapto/continue/ClearTime) -> tap qua, DEM +1 tran
  BLOCKED (No more/tickets left) -> DUNG

BUG QUAN TRONG khi build (do bang OCR that, KHONG doan):
1. 'Tap to continue' OCR doc DINH thanh 'Tapto'+'continue' -> keyword phai bat ca 2.
2. man CHON co nut 'Skills'/'Lineup'/'Rewards Preview' -> 'Skill' lam FIGHTING nham
   man chon thanh dang-danh -> khong bao gio tap Challenge -> battles=0 mai.
   FIX: SELECT uu tien TRUOC FIGHTING; FIGHTING chi dung 'Surrender' (dac trung
   tuyet doi, chi co khi dang danh); bo 'Skill'/'Victories' (co ca o man chon).
3. man dang danh detect None la BINH THUONG (it keyword on dinh) -> action None=wait
   (KHONG tap center, keo bo lo man RESULT). None>5 vong moi tap pha ket.
4. Soul Zones co man LIST truoc man battle -> MODE_ENTRY['soul_zones'] tap realm
   (Orochi...) de mo man co Challenge. Mode 1-man (Realm Raid) khong can entry.
5. 'Reward'/'Stamina' generic (co o man chon/thanh tai nguyen) -> bo khoi RESULT/BLOCKED.

DA VERIFY LIVE 1 tran day du (logs): SELECT(3)->tap Challenge->None x4 (timer 0:05
->0:15, Auto bat tu danh)->RESULT(ClearTime 00:18). May trang thai DUNG.

HA TANG: ps server hay BUSY/tranh chap khi co 2+ process python cung chay (jsonl
trong, shot None, etime cho thay process cu chua chet). LUON pkill SACH + doi
server hoi (shot True) TRUOC khi chay process moi. Tranh chay 2 farm/debug song song.

## 14. AUTO-EXPLORER vet can + GRAPH TICH LUY + PHA TRAN - 2026-06-04

Pivot lon: bo "doan toa do nut Bonus" -> xay thuat toan VET CAN tu phat trien
(automation/auto_explore.py). Bot KHONG dung toa do cung; no LANG nghe man hinh
(OCR + CV blob) roi click thu tat ca, ghi graph toi dau.

### 14.1 Nhan dien man hinh (fingerprint)
- fingerprint(reader,img) = (text_signature, dhash).
  text_signature = set token OCR tappable da chuan hoa, BO token nhieu so
  (HP/timer/coin: digits>=50% do dai bi loai) -> chi giu NGHIA.
  dhash = perceptual hash 64-bit (CHUOI HEX, dung _ham int(x,16) so sanh).
- same_screen(fp1,fp2): "cung man" neu Jaccard>=0.6 HOAC >=8 token chung
  (chiu noise OCR tren man nhieu chu nhu Home), HOAC dhash hamming<=12 khi
  it chu. inter/union<0.30 -> chac chan khac.

### 14.2 ICON-BLOB detector (DOT PHA - bat nut KHONG co chu)
- _icon_blobs: CV contour (Otsu + morph + loc aspect/fill) tim nut sang gon
  KHONG phai text. Day la kha nang OCR bo sot. candidates() = OCR tappable
  (source=text) + icon blob (source=icon). Loc title-bar (y<34) + nut close
  cua so (x 1100-1152, y<34) de KHONG tat game.

### 14.3 GRAPH TICH LUY qua nhieu run (explore_graph_global.json)
- _load_global nap ky uc cu vao self.nodes, KHOI PHUC fp tu sig+dhash ->
  observe() match duoc man da biet + tried tai dung (KHONG thu lai cand cu).
- cand_sig(label,x,y) = "label@<o luoi 40px>" lam khoa "da thu" BEN VUNG qua
  run (idx OCR doi moi run nen TUYET DOI khong dung idx lam khoa).
- merge_global() serialize lai toan bo (global cu + node moi). Luu 'cands'
  da quan sat -> tinh FRONTIER = node con cand CHUA thu.
- Bug da fix: dhash luu HEX string, _load_global cu ep int() -> crash IM
  trong __init__ (os._exit(0) o finally nuot exception -> launch "im lang
  chet"). Luon chay FOREGROUND ra file de bat loi init.

### 14.4 PHA TRAN: thu dong 23 node -> chu dong 38 node (do bang DATA)
HAN CHE map_loop thu dong (8 phien): TRAN o 23 node, frontier->0 tu phien 4.
Nguyen nhan do duoc:
  (1) bot bi hut vao summon/event popup, KHONG tu ve Home -> ket goc nho;
  (2) noop danh dau VINH VIEN -> duong "chet" gia (nut that su an bang
      politeclick nhung bgclick noop);
  (3) frontier=0 la GIA (con Soul/Exploration/Shop chua cham, chi khong
      reachable tu cho ket).
3 CAI TIEN pha tran (live 23->30->38 node, 28 edge):
  - _escape_to_home(): dau moi phien bam back/dismiss ve HUB (Home nhan dien
    qua HOME_TOK = explore/town/shikigami/summon/shop, >=3 token). at_home=true
    ngay phien dau. Xu ly dialog confirm-quit (Summon ket vong -> bam Confirm).
  - noop-retry: truoc khi bo cand, thu method NGUOC lai (polite<->bg).
  - frontier-driven: _pick_frontier_node (node nhieu cand chua thu nhat) +
    _bfs_path (duong di qua edges da biet tu Home) + _navigate_to.

### 14.5 ROOT-CAUSE moi treo: control_client._readline
timeout DUOC KHAI BAO nhung KHONG dung -> blocking readline() treo vo han khi
PS server busy. Fix: select.select([fd],[],[],remain), tra None khi het gio.
Day la nguyen nhan GOC cua MOI "process treo mai" toan du an.

### 14.6 CONG CU & PATTERN
- scripts/run_explore.sh: launcher tin cay (Bash tool hay NUOT setsid trong
  compound command). Doc tien do qua logs/explore_run.log + jsonl, KHONG qua stdout.
- scripts/map_loop.sh N BUDGET ACTIONS DEPTH: lap N phien, merge global, in tom tat.
- python automation/auto_explore.py --show-frontier: in node con duong chua
  kham pha (KHONG can game).
- Watchdog: --budget-sec + deadline kiem moi vong (backtrack/escape/nav deu
  ton trong deadline) -> KHONG treo qua gio.
- Ban do tich luy artifact: knowledge/maps/game_map.json (38 node, commit duoc;
  logs/ bi gitignore).

### 14.7 CON DANG DO
- Window OFF-SCREEN (rect 4047,-72, man phu tren man chinh) -> nghi SetForeground
  fail -> politeclick header/footer hay khong an (nut Bonus noop moi cach click).
- frontier loop chua kich hoat manh: explore Home dung het action truoc khi vao
  loop. Tang budget/action hoac uu tien frontier som hon de loop chay.
- 'unreached' danh dau cand khi nav fail -> co the bo sot khi sau nay reachable.
- Tiep: chay them phien day len 50+ node; HOAC tich hop graph vao screen_graph.py.

## 15. BUG STALE SCREENSHOT (2026-06-10, fix scripts/control_client.py)
Game KHONG chay nhung bot van "nhin thay" man hinh va click lia lia:
- server tra `OK 0x0 pw=False` (PrintWindow fail, w=h=0) nhung bgshot() chi
  check prefix "OK" roi imread FILE ANH CU con tren disk (onmyoji_srv.png).
- Trieu chung nhan biet: dong ho OCR DUNG YEN (Thur.10:49 EST mai), frame
  diff giua 2 lan chup = 0.0 tuyet doi, info tra `rect 0 0 0 0`.
- Fix: parse kich thuoc trong reply bgshot, w<=0 hoac h<=0 -> return None.
- BAI HOC: moi experiment live PHAI sanity-check "the gioi con song khong"
  truoc (clock doi? frame diff > 0? rect hop le?) roi moi tin ket qua click.

## 16. STATE-MATRIX DA CHIEU + GRAPH MEMORY (2026-06-10, PHAN B+C cua prompt)
- automation/state_matrix.py: moi man = 3 chieu doc lap
  (1) SEMANTIC ui_tokens, (2) SPATIAL luoi 6x4 token-theo-cell,
  (3) STRUCTURAL dhash tung cell. TRONG SO THICH NGHI: it/khong token
  (loading, man toi) -> don trong so sang struct, vi Jaccard 2 tap rong = 1.0 AO
  (day chinh la loi khien matcher cu gop moi man loading lam mot).
- VALIDATE quan trong: KHONG dung state-id explorer cu lam ground truth -
  no tach nham >= 5 cap (cung man pixel-diff < 7 van ra 2 id do OCR jitter).
  Dung pixel-diff (mean abs < 12) lam GT khach quan tren anh tinh.
  Ket qua 91 anh / 4095 cap: AUC 0.9997, @0.72 TPR 33/38 FP 0/4057.
- automation/graph_memory.py: node=FeatureMatrix, edge=action ngu nghia
  (ok/fail dem rieng), path=Dijkstra 1/reliability (tu ne canh hay fail),
  index = inverted token + LSH banding cell-dhash -> nearest 0.84ms.
  Import 91 anh -> 70 node, precision .946 / recall .921 vs pixel-GT.
- Buoc sau: noi observe() cua auto_explore vao GraphMemory (thay fingerprint
  rieng), ghi add_transition tu cac log explore_*.jsonl cu de co edge.

## 17. PHIEN DUPLEX MENTOR/OPERATOR: BUG LECH CLICK +8,+31 (2026-06-10)
Kien truc 2 agent (mentor co thi giac doc anh + operator tay OCR/click,
noi chuyen qua automation/agent_bus.py) DA CHAY THAT va tim ra bug lon:
- PrintWindow chup CA WINDOW: title bar ~31px (mau ~249 sang) + border 8px.
  Moi click (bgclick lParam, politeclick/fgclick ClientToScreen) dung toa
  do CLIENT -> toa do lay tu ANH (OCR box, CV contour) lech +8,+31.
- Trieu chung lich su: "nut Attack modal khong an", "Bonus noop", click
  cham me nut. Cang nut NHO cang de truot (lech 31px doc > nua chieu cao nut).
- Kiem chung: tru offset (x-8,y-31) -> bgclick an PERFECT tren modal
  RealmRaid, thang 2 tran live lien tiep (ve 30->28, doi thu KO).
- FIX GOC o ps/server.ps1 Do-BgShot: GetClientRect + ClientToScreen(0,0)
  -> cat bitmap ve client area. Anh moi 1136x640 (truoc 1152x679).
- HE QUA: cac toa do hardcode cu theo anh-window (45,68 back-arrow...)
  gio phai hieu la toa do client; cac fingerprint/dhash cu chup theo anh
  window cu se KHAC anh moi (kich thuoc doi) -> graph cu can rebuild dan.
- Realm Raid flow hoc duoc: Explore -> RealmRaid footer -> tap o doi thu
  -> dialog Attack (vi tri nut Attack DOI theo vi tri o, doc OCR moi lan)
  -> battle auto ~60s -> ve man luoi, o doi thu thanh KO.
