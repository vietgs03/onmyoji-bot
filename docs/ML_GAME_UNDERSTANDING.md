# BOT ML HỌC GAME ONMYOJI - Kiến trúc hiểu game

> Mục tiêu: bot tự học chơi Onmyoji. Cần bot hiểu 4 thứ:
> (1) game LÀ GÌ, (2) ẢNH trên màn hình là gì, (3) TỌA ĐỘ ở đâu, (4) CHỨC NĂNG nút là gì.
> Ngày: 2026-10-13. Nguồn: đục source game (NPK) + code bot hiện có.

## 1. Ta đang có gì (đã verify)

### Từ source game (đục NPK)
- `res.npk` đã dump đủ: **56.116 file** -> `research/fx/out/full_res/`
  - **2.189 layout màn hình** (Cocos widgetTree) = CÂY UI có tọa độ đầy đủ
  - **8.981 sprite plist** = tọa độ CẮT ảnh trong sheet
  - **93.531 node / 22.178 phần tử touch** -> đã lập chỉ mục ở `buttons.tsv`
  - 5 bảng tên-node (39092.json...): đường dẫn panel -> thuộc tính hiển thị
- Mỗi nút trong layout có: `name`, `classname`, `x/y`, `w/h`, `anchor`, `text`,
  `touchAble`, và **ảnh tham chiếu** (`normalData.path` + `plistFile`).
  => vd `strengthenBtn` -> ảnh `common/btn_tyanniu01_normal.png` (plist `common.plist`)

### Chuỗi liên kết ĐÃ KIỂM CHỨNG (đây là điểm mấu chốt)
```
layout  --(tên ảnh + tên plist)-->  plist (tọa độ cắt)  -->  sheet ảnh (tex_res.npk)
   |                                                              |
   +--> tọa độ nút trên màn hình                                  +--> pixel thật của nút
```
=> Từ source ta dựng được bộ ba **(ảnh nút, tọa độ, chức năng)** TỰ ĐỘNG, không gán tay.

### Còn thiếu
- **Ảnh UI thật**: nằm ở `tex_res.npk` (**82.876 ảnh**: 60.954 KTX + 21.914 DDS), CHƯA dump.
- **Bảng dịch tên hiển thị** CN -> EN (để hiểu "Challenge" = 挑战 = gì).
- **Logic game** (`script.npk`, bytecode mã hóa) - chưa giải mã.

### ML hiện có (yếu, cần thay)
- `affordance.pkl`, `screen_clf.pkl` train từ **613 lần click mò** trong
  `exploration/observations.jsonl` (event new_state/transition/noop).
- Nhãn kiểu "click có đổi màn không" -> AUC ~0.77. Thiếu nhãn thật về CHỨC NĂNG.
- **Vấn đề cốt lõi: học từ click mò thì không bao giờ hiểu nút để làm gì.**

## 2. Kiến trúc đề xuất: 4 tầng hiểu

```
TẦNG 4  CHỨC NĂNG   "nút này làm gì"     <- name + text + ngữ cảnh panel + quan sát
TẦNG 3  ĐỊNH VỊ     "nút ở đâu"          <- layout x/y + plist + calibration
TẦNG 2  ẢNH         "trông thế nào"       <- sprite thật từ tex_res + plist cắt
TẦNG 1  CẤU TRÚC    "game có màn gì"      <- cây layout + panel + quan hệ cha-con
```

Dữ liệu chảy từ dưới lên. Ba tầng dưới lấy TRỰC TIẾP từ source game (chính xác
tuyệt đối). Chỉ tầng 4 (chức năng) mới cần học từ quan sát.

## 3. Kế hoạch làm

### Bước 1 (làm ngay): Dựng "UI Knowledge Base" từ dump
- Dump `tex_res.npk` -> lấy 82.876 ảnh (KTX/DDS).
- Giải mã KTX/DDS -> PNG (đã có `tex2png.py`, `ktx_meta.json` từ trước).
- Ghép: layout -> plist -> ảnh, xuất 1 file JSON cho mỗi nút:
  `{path, name, text, screen_xy, w, h, image_png, panel_chain}`
- => Bộ dataset (ảnh, tọa độ, đường dẫn chức năng) cho ~22.000 nút.

### Bước 2: Calibration tọa độ (cần game chạy 1 lần)
- Layout là 1136x640 (gốc dưới-trái). Cần hệ số + viền cho cửa sổ thật.
- Mốc đã có: `btnChallenge` canvas (979,91) <-> screen (1063,580) [verify live].
- Cần thêm 2-3 mốc nữa -> giải hệ phương trình ra (scale, offset) chính xác.
- => Từ đó suy ra tọa độ MỌI nút mà không cần đo tay.

### Bước 3: Nhãn chức năng
- Suy từ: tên node (`strengthenBtn`), text trong nút, tên panel cha
  (`panel_chain`), và KB đã có (269 shikigami, 69 soul, 26 mode).
- Với nút mơ hồ -> dùng quan sát live (click -> màn đổi thành gì).
- => Dataset gán nhãn: ảnh nút -> chức năng (phân loại) + tọa độ (hồi quy).

### Bước 4: Model
- `screen_clf`: phân loại màn hình từ ảnh THẬT (không phải ảnh chụp nhiễu).
- `ui_detector`: phát hiện nút trong ảnh chụp live -> khớp về layout đã biết.
- `affordance`: nút này có bấm được / dẫn đi đâu.
- Validate chéo: layout nói nút ở (x,y) -> bot chụp màn -> kiểm ảnh có khớp.

## 4. Nguyên tắc
- Ưu tiên dữ liệu GỐC từ game hơn ảnh chụp tự gán nhãn.
- Mọi thứ phải verify được offline trước khi cần game chạy.
- Không đoán tọa độ: lấy từ layout, đối chiếu bằng calibration.
- Ghi rõ cái gì ĐÃ verify vs cái gì là giả thuyết.

## 5. TIEN DO (2026-10-13)

### Da xong: UI Knowledge Base (offline, khong can game)
`research/fx/ui_kb.py` -> ghep chuoi layout -> plist -> sheet cho tung node UI.

| Chi so | Gia tri |
|---|---|
| Layout da quet | 2.189 |
| Frame trong plist | 89.686 |
| Node UI (touch/button) | 22.178 |
| Anh tham chieu | 2.652 |
| Anh resolve duoc (co sheet + rect) | 2.363 |
| Sheet can lay tu tex_res | **709** (khong phai 82.876) |

Dau ra: `out/full_res/ui_nodes.jsonl`, `ui_images.tsv`, `ui_summary.json`.

Vi du that (nut cuong hoa soul):
```
name=strengthenBtn  canvas=(488,204) 120x60
image=common/btn_tyanniu01_normal.png
sheet=common.png    rect=(1280,456,50,50)
```

=> Moi node co du: TOA DO + ANH + NGU CANH PANEL. Day la dataset cho ML.

### Phat hien ve dung luong (quan trong)
Chi can **709 sheet** thay vi ca 82.876 anh. Nen khong can dump het 37.4 GB.
Buoc tiep: doc 709 sheet do tu `tex_res.npk`, roi cat anh theo `rect` -> PNG.

### Dang cho user
- Chay `docs/compact-wsl.ps1` voi UAC YES de thu hoi ~150 GB (fstrim da xong).
  Truoc do nen chay script bang user thuong; script tu hien UAC.
- LUU Y da rut ra: `diskpart` BAT BUOC quyen Admin. Loi that gap phai:
  "Program 'diskpart.exe' failed to run: requires elevation".


## 6. GIOI HAN THAT: chua lay duoc anh sheet (2026-10-13)

Da thu 4 duong, deu KHONG du de map ten sheet -> entry trong tex_res.npk:

1. **NPK khong luu ten file.** `tex_res.jsonl` chi co `sign` (u32), `off`, `clen`,
   `olen`, `flag`, `kind`. Khong co ten.
2. **CRC32 khong khop.** Thu crc32('common.png')/lower/backslash vs `sign` -> khong trung.
   => NeoX dung ham hash rieng (chua biet).
3. **`sign` KHONG dung chung giua 2 kho.** Lay 21 plist co `common.png`, so `sign`
   voi tex_res -> 0 trung. Nen khong the noi 2 kho bang sign.
4. **Ten sheet bi TRUNG.** 8.675 plist nhung chi 7.499 ten khac nhau. Vi du
   `template.png` xuat hien 250 lan, `vx.png` 89 lan. Va **403 ten co nhieu kich thuoc
   khac nhau** (vd `common.png` la 300x300 o plist 1546 nhung 202x202 o plist 4359)
   => trung ten that su, khong the lay theo ten.

### He qua
- Truong `sheet`/`rect` trong `ui_nodes.jsonl` la THONG TIN TU PLIST (dung), nhung
  **chua noi duoc voi entry nao trong tex_res.npk**. Chua co anh that.
- Muon lay anh phai giai bai toan hash ten -> entry cua NeoX (hoac dump het tex_res
  roi khop theo kich thuoc/pixel).

### Huong di tiep (chua lam)
- Dump het `tex_res.npk` (37.4 GB) roi khop sheet theo KICH THUOC + so sanh pixel
  voi mong doi tu plist (w*h*4 cho KTX RGBA8).
- Hoac tim ham hash NeoX trong `Client.exe`/`script.npk`.
- Hoac bo qua anh sheet: dung TRUC TIEP anh chup man hinh that lam mau train
  (da co san trong bot), va dung ui_nodes.jsonl lam GROUND TRUTH toa do.

## 7. DAO THEM 2026-10-13 (sau khi nen vhdx xong) - VAN CHUA NOI DUOC ANH

### Da tim thay (nhung chua du)
1. **`flathash.exe`** trong thu muc game = cong cu hash CUA CHINH NEOX. Co FNV:
   fnv1_16, fnv1a_16, fnv1_32, fnv1a_32, fnv1_64, fnv1a_64 (khong co crc32).
   => Da thu fnv1_32('common.png') = 2802890117 -> KHONG trung bat ky sign nao.
   Brute-force 6 thuat toan x 13 bien the ten (co/khong duong dan, .plist/.xml/.png,
   hoa/thuong) -> **KHONG KHOP** ca `res.npk` lan `tex_res.npk`.
2. **`Client.exe` co `hashFileName` + `files_hash_2_0.bin`** = manifest ten file -> hash.
   => Tim khap thu muc game: **KHONG co file `files_hash*` tren dia**. No duoc tai ve
   luc chay (co chuoi `files_hash_2_0.bin_temp`, `download file`) -> **phai chay game**
   moi co, hoac nam trong bo nho.
3. `Documents/` la thu muc lam viec cua game: co `tex.npk` (4.9 GB, magic **`NXPKM`**
   khac `NXPK`), `script.npk`, `res.npk` (2.0 GB), `resdb`, `cloudfilesys3/`.
   `Documents/tex.npk` co 48.205 entry (khac `tex_res.npk` 82.876).
4. **`.text` = atlas TexturePacker dang TEXT** (398 file, 370 ten): doc duoc het
   ten sheet + kich thuoc + moi frame (xy/size/orig/offset). Rat de doc.
   => Nhung 370 ten nay **KHONG trung** voi 709 sheet UI can (giao = 0).

### Ket luan ve `sign`
- `sign` co trong MOI entry cua moi npk, la so u32, KHONG trung giua cac entry
  (54.718/54.718 duy nhat trong res.npk).
- KHONG phai CRC32, KHONG phai FNV (moi bien the), KHONG phai index.
- KHONG dung chung giua 2 kho (21 plist chua 'common.png' -> sign khong xuat hien
  trong tex_res).
- Plist CUNG ten sheet (`common.png`) nhung KHAC sign va KHAC kich thuoc
  (300x300 vs 202x202) => xac nhan ten sheet bi TRUNG, khong dinh danh duy nhat.
  => `sign` kha nang cao la hash cua DUONG DAN DAY DU (co tien to thu muc) hoac
  hash noi bo khac, can `files_hash_2_0.bin` moi dich nguoc duoc.

### Trang thai
- **Chua lay duoc anh that.** Day la gioi han that, da thu 6 duong.
- Duong kha thi nhat con lai: **chay game** de no tai `files_hash_2_0.bin`, roi
  dung bang do tra `sign` -> ten file.
- Duong khac: dump het `tex_res.npk` (37.4 GB, gio da DU cho vi o C con 165 GB) roi
  khop bang KICH THUOC + so sanh pixel. Nhung van nhap nhang vi 1.447 sheet la 512x512.

## 8. CALIBRATION 2026-10-13 (GAME DA MO - bang chung that)

### Phat hien quan trong nhat
Game dang chay (Client PID 9708). Chup man hinh that: **1136 x 640**.
=> **DUNG BANG design canvas trong layout NPK.** Nen:
```
screen_x = canvas_x            (scale = 1.0)
screen_y = 640 - canvas_y      (lat truc Y)
```
**Khong can suy doan he so scale nua.** Truoc do minh doan 1.086 tu 1 diem -> SAI.

### Toa do hardcode cu trong bot DA LECH
So sanh man HOME, giua `automation/screen_graph.py` (ghi theo 1152x679) va OCR
anh chup that hom nay (1136x640):

| Nut | bot-hoc | OCR-that | lech |
|---|---|---|---|
| Explore | (608,192) | (495,192) | dx=-113, dy=0 |
| Summon | (991,194) | (1018,270) | dx=+27, dy=+76 |
| Event | (1078,195) | (1070,163) | dx=-8, dy=-32 |

=> **Toa do hardcode cu KHONG con dung.** Layout NPK la nguon tin cay hon.

### Con 1 diem chua giai thich
`btnChallenge` canvas (979,91) voi scale 1.0 -> screen (979,549), khong phai
(1063,580) da ghi trong farm_soul. Nen hoac:
- (1063,580) la toa do tren cua so cu (1152x679), hoac
- entry `btnChallenge` trong layout do KHONG phai nut Challenge man Soul.
=> Can verify lai khi vao dung man Soul stage.

### Da thu (that bai): tim bang ten file
- `Documents/cloudfilesys3/bin/hash_version` = `nx3_260701_729de661e9_20260928111651`
- `Documents/cloudfilesys3/zipres/script3.zip` (3 entry) ten file la **hash hex 16 byte**
  (vd `51809e0ecb61db0b467a8fec389ad9`), noi dung bat dau `PC\x01\x00` (bytecode ma hoa).
  => Thu MD5/SHA1 cua 10.462 ten da biet -> KHONG khop.
- Van KHONG tim thay `files_hash_2_0.bin` tren dia (game dang chay van khong thay).
- `pkgmapping.json`/`pkginfo.json` chi la bang anh xa THU MUC -> goi, khong co ten file.

## 9. MAN HOME KHONG CO TRONG res.npk (2026-10-13)

Quet TOAN BO 56.116 file cua `res.npk`: chi **6 file** chua chuoi "Explore", va
khong file nao la layout man HOME:
- 4 file = bang dich ten hien thi (39092.json, 37348.json, 36571.json, 7165.json)
- 1 file = scene 3D 3ds Max (`bin_d0cf11e0`, OLE compound, co 'Autodesk'/'mental ray')
- 1 file = `bin_14000000` (flatbuffer)

=> **Man HOME (Explore/Summon/Town/Seal) KHONG nam trong res.npk.**
Ly do kha nang cao: HOME la giao dien Cocos rieng, duoc dung bang CODE
(`nxgui_res`/`Compiled_full3` theo pkgmapping), khong phai file layout tinh.
Hoac nam trong `Documents/tex.npk` (NXPKM) / `script3.zip`.

### He qua cho bot
- 2.189 layout trong res.npk = cac PANEL/man chuc nang (shop, soul, guild, event...),
  KHONG gom man HOME va cac man chinh.
- Nen: toa do man HOME van phai lay bang OCR (nhu bot dang lam), KHONG lay duoc tu layout.
- Nhung cac panel chuc nang (vd man cuong hoa soul, shop) THI lay duoc tu layout.

### Da verify them
Chup lai man HOME 2 lan, OCR cho ket qua ON DINH:
Explore (495,192), Event (1071,164), Town (501,365), Seal (81,322).
=> Xac nhan anh chup 1136x640 va scale 1.0 (so sanh voi canvas design).

## 10. VERIFY CALIBRATION TREN MAN THAT (2026-10-13) - THANH CONG

Da dieu huong that: HOME -> Explore -> Soul Zone -> man Soul stage (Orochi).
OCR man Soul doc duoc: Challenge, Rewards Preview, Lineup, Auto, Orochi, Sougenbi,
Himiko, Sea of Eternity, Shikigami, Presets, Record, Legend.

### Doi chieu nut Challenge
| Nguon | Gia tri |
|---|---|
| Layout NPK `25994.btnChallenge` canvas | (979, 91), 145x145 |
| Cong thuc scale 1.0 -> screen | **(979, 549)** |
| OCR anh that | **(975, 548)** |
| Lech | dx=-4, dy=-1 (sai so OCR) |

=> **CONG THUC DA DUOC CHUNG MINH:**
```
screen_x = canvas_x
screen_y = 640 - canvas_y
```

### Con so cu trong farm_soul SAI
`_CHALLENGE_XY = (1063, 580)` lech **88 px ngang, 32 px doc** so voi (975,548) that.
Van bam trung duoc chi vi nut Challenge to (157x47). Nut nho se TRUOT.
=> NEN sua lai theo layout.

### CANH BAO: man Soul co NHIEU layout
| Layout | btnChallenge canvas |
|---|---|
| 25994, 46987 | (979, 91) 145x145 |
| 9550, 35317, 44568, 47054 | (913, 94) 159x159 |

=> Phai chon dung layout theo man cu the, KHONG dung bua mot so cho moi man.

### Nut cuong hoa soul (cho task enhance_soul)
Tu ui_labeled.jsonl, cac nut ENHANCE + toa do screen (scale 1.0):
| name | canvas | screen |
|---|---|---|
| strengthenBtn | (827, 63) | (827, 577) |
| strengthenBtn | (488, 204) | (488, 436) |
| enhancePanel | (566, 321) | (566, 319) |
| enhance | (1027, 59) | (1027, 581) |
=> Thay the ANCHORS gia thuyet trong tasks/enhance_soul.py bang cac so nay
(khi da xac dinh dung layout cua man chi tiet soul).

## 11. BANG DOI CHIEU MAN SOUL THAT (2026-10-13) - layout 4529/48704

Da dieu huong that HOME -> Explore -> Soul Zone -> man Soul stage (Orochi).
Tim duoc layout chuan: **4529.json va 48704.json** (giong nhau), 44 node, co text
tieng Trung tuong ung voi nut. Day la bang vang de doi chieu.

### Doi chieu text (CN trong layout) -> toa do -> OCR (EN man that)
| Text CN | Nut | screen (layout) | OCR EN that | lech |
|---|---|---|---|---|
| 挑战 | btn_zhandou | (1046, 563) | Challenge (975,548) | -71,-15 |
| 派遣 | btn_paiqian | (895, 563) | Presets (866,560) | -29,-3 |
| 式神录 | btn_shishenlu | (761, 588) | Shikigami (768,560) | +7,-28 |
| 自动战斗 | btn_auto | (967, 451) | Auto (693,618) | -274,+167 |
| 奖励预览 | (label) | (452, 543) | RewardsPreview (913,177) | +461,-366 |

**Ket luan:**
- 3/5 nut khop TRONG SAI SO (nut to 84-159px, OCR +-5px, lech 3-71px = van bam trung).
- `btn_zhandou` (挑战) = nut **Challenge**. Lech -71px nhung nut to 159x159 nen van trung.
- `btn_auto` va `奖励预览` lech xa => chung thuoc PANEL KHAC khong hien trong layout nay
  (panel_rightup/leftdown khac), hoac layout 4529 la bien the khac cua man.
- => **Layout cho TOA DO DUNG, nhung phai chon dung layout cho dung bien the man.**

### Sang toa do (DA XAC NHAN nhieu lan)
```
screen_x = canvas_x
screen_y = 640 - canvas_y
```
Ap dung cho anh chup 1136x640 (crop vung game, khong gom title bar).

### Y nghia tu cau hoi cua user (soul co nhieu loai + nhieu stage)
- Man Soul co 4-5 ZONE: Orochi(42,140), Sougenbi(41,280), Himiko(42,419),
  Sea of Eternity(41,548) - toa do OCR that.
- Moi zone co NHIEU stage (Chapter/Floor). Stage list nam trong panel trai.
- => Bot can: (1) chon zone theo toa do, (2) scroll tim stage theo TEN (OCR),
  (3) bam Challenge. Toa do Challenge co the lay tu layout (btn_zhandou).
- Layout 4529 = man stage cua MOT zone. Cac zone khac co the dung layout khac
  hoac cung layout nhung ten zone khac -> CAN MAP rieng tung zone.

## 12. SUA TOA DO OROCHI (2026-10-13) - CO DIEU CHINH TRUNG THUC

### Dinh chinh: minh da noi QUA ve toa do Challenge
| | gia tri | nam trong nut? |
|---|---|---|
| Nut challenge (layout 4529) | tam (1046,563) rect (967,484,159,159) | - |
| Toa do MOI | (1046,563) | True (tam nut - chuan nhat) |
| Toa do CU | (1063,580) | **True** (van bam trung) |

=> O tin truoc minh noi "con so cu SAI 88px" -> dung la lech 88px NHUNG vi nut to
159x159 nen **van bam trung**. Toa do cu KHONG lam hong farm_soul.
Da sua thanh (1046,563) cho chuan, nhung khong phai loi nghiem trong.

### Loi NGHIEM TRONG that su: CHON ZONE
Code cu trong `tasks/run.py` gia dinh 4 zone **xep ngang**:
```
_ZONE_X = {"orochi": 200, "sougenbi": 460, "fallen sun": 740, ...}
agent.click(zx, 250)
```
Nhung man Soul that: 4 zone **xep DOC ben trai** (OCR 2026-10-13):
```
Orochi (42,140) | Sougenbi (41,280) | Himiko (42,419) | Sea of Eternity (41,548)
```
=> Click (200,250) trung vao KHOANG TRONG giua cac zone -> **khong chon duoc zone**.
    Day moi la loi lam farm_soul khong the chay dung.

### Da sua + TEST THAT
Sua thanh click theo tam zone (60,140),(60,280),(60,419),(60,548).
Test live: bam (60,140) -> man doi thanh man stage Orochi
(thay 'OROCHI GF', 'TheMaidens', '0/500', '2076/8000', 'Rewards Preview').
=> **XAC NHAN SUA DUNG.**

### File moi: research/fx/soul_orochi.py
Chua toa do zone + nut man Orochi lay tu layout, kem ham `contains()` de tu kiem tra
(tam OCR co nam trong rect nut khong). Dung lam nguon duy nhat cho toa do soul.

### Ghi chu phuong phap (rut ra)
- Nut trong game TO (84-159px). OCR doc CHU, tam chu KHONG trung tam nut.
- Muon kiem khop: kiem tam chu co NAM TRONG rect nut, KHONG so tam voi tam.
- Zone: OCR tra ve toa do tam chu -> click lech phai ~18px cho an toan.

## 13. CO CHE CHON STAGE OROCHI (verify LIVE 2026-10-13) - RAT QUAN TRONG

### Su that ve man Soul
Man Soul **KHONG** co danh sach stage cuon duoc nhu minh tuong ban dau.
Bo cuc that (nhin anh 1136x640):
```
COT TRAI (x 0-210)          | GIUA (3D model)   | PHAI (info + nut)
 4 PANEL ZONE:              |                   |
  [Orochi]     Lv.6, Lv.7   |  Orochi 8 dau     | Orochi of the Maidens
  [Sougenbi]   Lv.8         |                   | Rewards Preview 0/500
  [Himiko]     Lv.9, Lv.10  |                   | Drops G4-G6 Souls
  [Sea of Et.] Moan (dang   |                   | [Team] [Challenge x12]
               chon, to do) |                   |
```

### Co che chon stage (BANG CHUNG)
Bam vao NHAN "Lv.N" -> CHON stage do. Man KHONG doi, nhung phan `Drops` doi:
| Bam nhan | Drops hien ra |
|---|---|
| Lv.6 | Drops G3-G5 Souls |
| Lv.7 | Drops G3-G6 Souls |
| Lv.8 | Drops G3-G6 Souls |
| Lv.9 | Drops G4-G6 Souls |
| Lv.10 | Drops G4-G6 Souls |

=> **Moi nhan Lv la 1 STAGE RIENG.** Bam = chon.

### DA CHAY 1 TRAN THAT (theo yeu cau user)
1. Bam `Lv.6` @ (120,118) -> chon stage thap nhat dang thay
2. Bam `Challenge` @ (1046,563) [layout btn_zhandou, da verify]
3. Cho battle (~60s, thay 'Tap to continue' + mau 39539/39539)
4. Bam tap to continue -> ve man stage
5. **COUNTER: 0/500 -> 1/500** = DUNG 1 TRAN. XAC NHAN THANH CONG.

### CHUA GIAI QUYET: cuon de lay stage thap hon (Lv.1..Lv.5)
- `bgdrag` (SendMessage) va click deu KHONG lam panel dich chuyen.
  Da thu: keo doc cot trai, keo ngang, keo manh, keo o giua -> khong doi.
- Nen hien chi chon duoc stage DANG THAY (Lv.6..Lv.10 cho Orochi).
- Muon lay Lv.1..Lv.5 phai tim cach cuon panel (co the can message khac,
  hoac panel chi hien stage cao nhat da mo khoa -> Lv.1 nam sau 1 lan bam khac).

### Da cap nhat
`research/fx/soul_orochi.py`: them OROCHI_STAGE_LABELS_Y, stage_label_xy(),
lowest_visible_stage().


## 14. SUA CHIEU CUON STAGE (2026-10-13) - USER CHI DUNG

### Minh da lam SAI chieu
Lan dau minh keo TU DUOI LEN TREN (y 580 -> 90) -> panel KHONG dich chuyen.
Ket luan sai la "khong cuon duoc". Thuc ra chi la sai chieu.

### Chieu DUNG: NAM TREN KEO XUONG (y 120 -> 580)
Mot lan keo la du. Ket qua:

| | Truoc keo | Sau keo 1 lan |
|---|---|---|
| Stage thay duoc | Lv.6, Lv.7, Lv.8, Lv.9, Lv.10 | **Lv.1, Lv.2, Lv.3, Lv.4, Lv.5, Lv.6** |

Toa do OCR that sau khi keo (x tam ~83, click le x=120):
```
lv1 (83,102) | lv2 (83,193) | lv3 (83,287) | lv4 (83,378) | lv5 (83,470) | lv6 (82,563)
```

### DA CHAY STAGE LV.1 THAT
1. Keo xuong 1 lan -> hien Lv.1..Lv.6
2. Bam Lv.1 @ (120,102) -> Drops doi thanh **G1-G3 Souls**
3. Bam Challenge @ (1046,563)
4. Cho battle -> ve man stage
5. **COUNTER: 1/500 -> 2/500** = dung 1 tran. XAC NHAN.

### Da cap nhat
`research/fx/soul_orochi.py`:
- `SCROLL_DOWN_DRAG = (110,120,110,580,30)` - keo dung chieu
- `OROCHI_STAGES_AFTER_SCROLL` - toa do Lv.1..Lv.6 sau khi keo
- `scroll_stages_down()`, `stage_after_scroll(n)`

## 15. DUC MAN HOME (2026-10-13) - cho ML

### Dieu quan trong: man HOME KHONG co trong res.npk
Da quet ca 56.116 file: chi 6 file chua chuoi 'Explore', va KHONG file nao la layout
HOME (4 file la bang dich, 1 la scene 3D 3ds Max, 1 flatbuffer).
=> **Toa do HOME phai lay bang OCR truc tiep, khong the lay tu layout NPK.**
Cac PANEL chuc nang (shop/soul/guild...) thi lay duoc tu layout.

### Nut tren HOME (OCR that, anh 1136x640)
| Nut | Toa do | Ghi chu |
|---|---|---|
| Explore | (495,191) | -> man Explore (Soul Zone, Realm Raid, EVO, Chapter...) |
| Town | (501,364) | |
| Seal | (80,323) | |
| Demon Parade Up | (508,315) | |
| Bonus | (337,51) | |
| Event | (1071,164) | cot phai |
| Settings | (1075,560) | **cuon giay goc phai duoi -> mo Settings**, KHONG phai menu chinh |
| **Summon** | (1022,268) | **DANG KY: KHONG BAM** (ton tai nguyen) |

### Menu ngang day man (menu chinh cua game)
`House | Team | Guild | Shop | Talisman Pass | Friends | Onmyoji | Shikigami` @ y~592-595
| Muc | Toa do |
|---|---|
| House | (327,595) |
| Team | (406,594) |
| Guild | (505,593) |
| Shop | (640,593) |
| Talisman Pass | (740,593) |
| Friends | (800,592) |
| Onmyoji | (905,595) |
| Shikigami | (1004,595) |

Da TEST: bam Guild @ (505,593) -> thoat Settings ve HOME. Toa do DUNG.

### Da luu thanh DU LIEU CHO ML (co commit)
- `data/ui_home.json` - toa do + nhan chuc nang + co `danger` cho tung nut
- `automation/ui_home.py` - nap du lieu, API: `xy(area,name)`, `is_danger()`,
  `safe_targets()` (TU DONG loai nut nguy hiem), `label()`

### Nguyen tac an toan (da ma hoa trong du lieu)
- `never_click: ["summon"]` -> `safe_targets()` khong bao gio tra ve summon.
- Nut 'settings' (cuon giay) KHONG phai menu chinh -> dung menu ngang de dieu huong.

## 16. MAN NGHI (IDLE) - DUC TU LAYOUT NPK (2026-10-13)

### Dac diem: OCR = 0 text
Man nghi (giao dien bi an) OCR tra ve **0 text** -> KHONG the doc bang OCR.
=> Bat buoc phai lay tu layout NPK. Day la ly do khong the chi dung OCR cho bot.

### Tim ra layout: 46693.json (= 2043.json), 58 node
Khop chinh xac voi anh that: 3 icon goc trai tren + nut goc phai duoi.

| Node | screen | size | Y nghia |
|---|---|---|---|
| buttonExit | (33,30) | 60x60 | thoat/back |
| buttonSetting | (96,30) | 60x60 | setting (icon nguoi) |
| buttonChat | (158,30) | 60x60 | chat |
| button_auto | (56,584) | 100x100 | auto battle ("自动") |
| button_accelerate | (112,549) | 72x72 | tang toc ("x1") |
| btnCombatTips | (1074,588) | 100x100 | tips/nhac ("特殊机制") |
| panel_summon | (986,577) | 100x100 | summon panel |

Label co text (de nhan dien man): 我方/敌方 (doi), 00:00 (thoi gian), 1/2 (so luong),
1/12 (so hero), 5/3, 特殊机制.

### Luu y: layout nay la MAN NGHI TRONG TRAN
Co `button_auto` + `button_accelerate` + `我方/敌方` + `number_hero 1/12`
=> day la giao dien trong luc danh nhau (auto mode), khong phai nghi ngoai tran.

### Da luu thanh du lieu cho ML (co commit)
- `data/ui_idle.json` - nut + label + toa do, ghi ro nguon layout 46693
- `automation/ui_idle.py` - API: `buttons()`, `xy(name)`, `size(name)`, `labels()`

### Nguyen tac rut ra (quan trong cho bot)
KHONG the chi dung OCR. Phai chia:
- Man/panel chuc nang (shop, soul, guild, menu ngang, man nghi) -> LAY TU LAYOUT NPK.
- Canh 3D / man chinh (HOME, Explore, Town, Summon) -> dung OCR.
- Man nghi -> OCR 0 text -> BAT BUOC dung layout.

## 17. DANH MUC LAYOUT TU SOURCE (2026-10-13)

### Da lap danh muc TOAN BO layout trong res.npk (khong bam thu, chi doc)
- `research/fx/out/layout_catalog.json` - **2.106 layout** co nut/text
  (moi dong: file, so node, so button, ten button, text)
- `research/fx/out/layout_index_by_feature.json` - tra theo CHUC NANG:
  guild(43 layout), friend(63), shop(29), shikigami(49), team(46),
  warehouse(95), onmyoji(27), settings(32), summon(7), explore(3), battle(48), task(8),
  soul(3), mail(11)

### Cach tra dung (thay vi mo bang OCR)
Muon biet man X nam o layout nao: tra `layout_index_by_feature.json` theo tu khoa
-> ra danh sach file layout -> doc toa do nut tu file do.
**Khong can bam thu, khong can OCR.**

### Icon goc phai tren man HOME (tu layout 43447)
| Icon | screen | node |
|---|---|---|
| Mail | (1024,40) | mailBtn |
| Chat | (1084,40) | chatBtn |

### MANH CUNG: man nao KHONG co trong res.npk
Da kiem chung: HOME (canh 3D), Explore/Town/Summon (canh 3D) -> phai dung OCR.
Man nghi -> OCR = 0 text -> phai dung layout (46693).
Cac panel chuc nang -> deu CO trong layout, tra theo feature index.

### Bai hoc phuong phap (quan trong)
DUC TU SOURCE, khong mo bang OCR:
- 1 lan quet 2106 layout trong ~40s -> co toan bo ban do UI.
- Mo bang OCR + bam thu vua cham (5 phut/man), vua de lac (bam nham mo panel khac),
  vua sai (OCR lech 30-156px).
- Thu tu dung: tra catalog -> doc toa do -> UPLOAD 1 lan de verify, thay vi mo mo.

## 18. RA FULL TOA DO - 22.178 NUT / 2.189 LAYOUT (2026-10-13)

### Da ra FULL toa do tu source, khong con lam le tung man
Tool: `research/fx/dump_all_coords.py` (chay offline 24s).
Ket qua trong repo: `data/ui_coords/`
| File | Noi dung |
|---|---|
| `coords_all.jsonl` (5.2 MB) | **1 dong/nut**: layout, man, panel, name, class, text, canvas, screen, size, touch, image, features |
| `coords_by_feature.json` | nhom theo chuc nang |
| `coords_summary.json` | thong ke + top layout |
| `README.json` | nguon + cong thuc + ghi chu |

**2.189 layout, 22.178 nut co toa do.**

### Da VERIFY: 11 gia tri doi chieu khop 100%
| Nut | Layout | screen | Ket qua |
|---|---|---|---|
| btn_zhandou (Challenge) | 4529 | (1046,563) | OK |
| tujianBtn | 43447 | (122,555) | OK |
| guildBtn | 43447 | (435,555) | OK |
| shishenluBtn | 43447 | (955,555) | OK |
| mailBtn | 43447 | (1024,40) | OK |
| chatBtn | 43447 | (1084,40) | OK |
| buttonExit | 46693 | (33,30) | OK |
| buttonSetting | 46693 | (96,30) | OK |
| buttonChat | 46693 | (158,30) | OK |
| btnCombatTips | 46693 | (1074,588) | OK |
| button_auto | 46693 | (56,584) | OK |

### Tra cuu: `automation/ui_coords.py`
```
python automation/ui_coords.py --stats            # thong ke
python automation/ui_coords.py --feature soul     # 55 nut lien quan soul
python automation/ui_coords.py --name guildBtn    # tra theo ten nut
python automation/ui_coords.py --layout 46693     # nut trong 1 man
```
API: `find(name=,layout=,feature=,text=)`, `screen('guildBtn','43447')`

### Chi con thieu (phai dung OCR, khong co trong res.npk)
- Man HOME / Explore / Town / Summon (canh 3D) -> `data/ui_home.json`
- Man nghi (OCR=0 text) -> `data/ui_idle.json`

## 19. BOT NHAN DIEN DANG O LAYOUT NAO (2026-10-13)

### Van de
2.189 layout -> bot phai biet dang o man nao moi bam dung nut.

### Cach giai: CHU KY LAYOUT (tap nut + tap text)
Moi layout co **tap TEN NUT** va **tap TEXT** dac trung. Do la "chu ky" cua man.
Tool: `research/fx/layout_id.py` -> `layout_signatures.json` (2.173 layout).

### DA TEST - nhan dien dung ca 3 man:
| Man | Dau vao | Ket qua | Cach biet |
|---|---|---|---|
| Soul stage | text `奖励预览,挑战,66` + nut `btn_zhandou,btn_shishenlu` | **4529** (diem 4.98) | nhom sau chi 1.99 |
| Man nghi | text `00:00,x1,1/12` + nut `button_auto,button_accelerate,buttonSetting` | **2043/46693** (diem 6.99) | nhom sau 5.95 |
| Menu ngang | nut `tujianBtn,guildBtn,shishenluBtn,mailBtn` | **43447/33286** (diem 7.96) | nhom sau 1.98 |

### Vi sao KHONG dung anh nguyen man de nhan dien
- Nhieu man dung CHUNG khung/theme, chi khac vai nut -> anh nguyen man giong nhau.
- Man nghi (46693) va man khac co the cung nen 3D -> phai dua vao TAP NUT.
=> Dung TAP TEN NUT + TEXT lam chu ky, khong dung pixel toan man.

### Luong nhan dien de xuat cho bot
```
1. OCR man hinh           -> tap text
2. Phat hien nut (template/sprite tu NPK) -> tap ten nut
3. layout_id.identify(texts, names)
   - khop text: diem 1.0 / text
   - khop nut : diem 2.0 / nut   (nut dac trung hon)
   - tru diem neu layout qua nhieu nut/text (tranh khop ngau nhien)
4. Lay layout diem cao nhat -> doc toa do nut tu coords_all.jsonl -> bam
```

### Y nghia cho ML
- `layout_signatures.json` = nhan (label) cho bai toan "man nao?".
- `coords_all.jsonl` (22.178 nut) = nhan toa do cho bai toan "nut o dau?".
- Anh that (tu tex_res.npk + plist, hoac chup man hinh) = dau vao.
=> Du 3 thanh phan de train: ANH -> (MAN, NUT, TOA DO).

## 20. ASSET ANH: KET LUAN TRUNG THUC (2026-10-13)

### Da co (verify duoc)
1. **Toa do**: 22.178 nut / 2.189 layout -> `data/ui_coords/` (da verify 11 diem khop)
2. **Nhan MAN**: 2.173 chu ky (tap nut + text) -> `layout_signatures.json`
   Da test: nhan dien dung Soul(4529) / nghi(46693) / menu ngang(43447)
3. **Anh**: 82.867 texture da dump (35 GB) trong `out/full_tex`
4. **Plist**: 8.675 plist, ghi ten sheet + toa do cat tung sprite

### THIEU: noi TEN SHEET -> ENTRY THAT. Da thu 5 cach, KHONG du:
| # | Cach | Ket qua |
|---|---|---|
| a | Doc ten file tu NPK | NPK KHONG luu ten (chi `sign` u32) |
| b | CRC32 / FNV | 6 thuat toan x 13 bien the -> KHONG khop `sign` |
| c | `sign` dung chung 2 kho | 0/21 plist khop -> khong noi duoc |
| d | Khop KICH THUOC | 8140 sheet khop, nhung **7476 TRUNG** kich thuoc |
| e | Kiem NOI DUNG theo plist | 146x146 -> 13 ung vien, chi so 0.28..0.76, khong phan biet |

=> **Dataset (ANH tu source, MAN, NUT, TOA DO) CHUA ghep duoc.**
   Nguyen nhan goc: NPK khong luu ten file, nen khong co khoa noi plist <-> entry.

### DUONG KHA THI (khong can anh sheet tu NPK)
Dung **anh chup man hinh that** lam dau vao, voi SIEU DU LIEU tu source:
```
ANH (chup man that)  +  nhan MAN (layout_signatures)  +  nhan TOA DO (coords_all)
```
- Bot chup man -> OCR text + phat hien nut -> `layout_id.identify()` ra MAN
- Tu MAN -> `coords_all.jsonl` cho toa do TUNG NUT -> nhan cho bai toan "nut o dau"
- => Train duoc: (1) phan loai MAN tu anh, (2) dinh vi NUT, (3) map nut -> chuc nang

Uu diem: anh dung nhu bot THAY (ke ca nhieu, anti-alias, hieu ung), khong phai
anh ly tuong tu NPK. Thuc dung hon cho bot chay that.
Nhuoc diem: can thu thap anh (chay bot/explorer), khong co san 82k anh.

### Neu muon lay anh tu source sau nay
Huong con lai: tim ham hash NeoX trong `Client.exe` (co `hashFileName` va
`files_hash_2_0.bin` tai luc chay) -> tra `sign` ra ten file -> noi duoc plist.

## 21. GIAI MA SCRIPT.NPK + TIM BANG TI LE NGU HON (2026-10-13)

### DOT PHA: giai ma duoc TOAN BO script.npk
Tool co san `research/fx/script_dump.py` (Rotor cipher + marshal27) chay duoc:
```
33.900 file Python giai ma, 0 loi -> research/fx/out/py/**.py.marshal
```
(Python 2.7 marshal; doc bang `marshal27.load()`). Day la lan dau doc duoc logic game.

### Tim thay trong code
| File | Y nghia |
|---|---|
| `com/Equip.py` | logic ngự hồn |
| `com/utils/yuhun_helpers.py` | hàm hỗ trợ |
| `com/data/cdata_en/equip_upgrade` | bang cuong hoa |
| `auto_yuhun_rand_attr_rate` | **ti le roll dong phu** |
| `auto_yuhun_single_attr_rate` | ti le 1 dong |
| `auto_yuhun_suit_attr_rate` | ti le theo bo |
| `auto_yuhun_const` | hang so |

### NHUNG: cac file nay chi la WRAPPER
Vi du `equip_upgrade.py` chi chua:
```
names: [bindict, BindictProxy, game3d, taggeddict, TD, data, bin_data, equip_upgrade_orig]
```
=> Du lieu THAT nam trong file **bin_data** rieng, khong phai trong script.

### Da tim bin_data o MOI noi - KHONG CO
- Quet 9 kho NPK (res/script/func1/func2/qmodel/model1/liudao/scene1/scene2):
  **0 entry** chua ten bang ti le.
- Quet `Documents/` (moi file): khong co.
=> Ket luan: **bang ti le duoc TAI TU SERVER luc chay**, khong nam tren dia.

### Y nghia
- Logic game (Equip.py, yuhun_helpers.py) thi doc duoc tu script.npk.
- Nhung DU LIEU (ti le, bang cuong hoa) nam o server -> khong lay duoc bang cach doc file.
- Muon co ti le THAT: phai (a) bat `EnableYuhunAlgoLog` de engine in ra, hoac
  (b) bat goi mang khi game tai bang, hoac (c) dung wiki (da co trong data/fandom).

### Viec con lai (can account + game chay)
Ban de nghi cap account de test API. Huong di:
1. Kiem tra game co Python console/driver de goi API khong (khong can account).
2. Neu co: goi `auto_yuhun_*` de doc bang + `Node.getWorldPosition` lay toa do that.
3. Neu khong: bat log `EnableYuhunAlgoLog` xem engine tu in gi.

## 22. DICH NGUOC PYTHON DE DOC BANG TI LE (2026-10-13) - DANG LAM

### Da xac dinh nen tang (buoc quan trong)
| Phat hien | Y nghia |
|---|---|
| `python27.dll` (trong game dir + Documents/cloudfilesys3/bin) | **CPython 2.7** |
| PE machine `0x8664` | **64-bit** -> con tro 8 byte |
| `.marshal` bat dau `63 00 00 00` | la TYPE_CODE; header 8 byte da bi cat |
| `script.npk` giai ma duoc | 33.900 file Python -> `out/py/**.py.marshal` |

### Layout struct CPython 2.7 64-bit (suy ra duoc, khong con doan)
```
PyObject_HEAD   = 16   (ob_refcnt@0, ob_type@8)
PyDictObject    : ma_fill@16, ma_used@24, ma_mask@32, ma_table@40, smalltable@56
PyDictEntry     : me_hash@0,  me_key@8,   me_value@16   (size 24)
PyStringObject  : ob_size@16, ob_shash@24, ob_sstate@32, ob_sval@36
PyIntObject     : ob_ival@16
PyFloatObject   : ob_fval@16
PyTypeObject    : tp_name@24
```

### CHAN DOAN LAI ket qua quet truoc (minh da ket luan sai)
Vung `0x7FF6975EDE00` minh tuong la "bang dang ky" -> THAT RA la **UTF-16 bytecode**:
giai ma ra `attr_idx < dict.ARRT_NUM`, `equip_init`, `equip_upgrade`... = TEN BIEN trong code.
Vung `com.data.cdata.equip_attr` -> chi la **bang dang ky TEN MODULE**, moi con tro
deu tro ve cung `0x7FF698B557B0` -> KHONG phai du lieu.

### Tool da viet
- `docs/mem_scan.ps1` - quet heap tim chuoi ten bang (DA CHAY, tim thay 7 ten)
- `docs/mem_read.ps1` - hexdump + lan con tro (DA CHAY)
- `docs/mem_dict.ps1` - **tim doi tuong STR -> quet con tro -> doc DICT** (dang chay)

### Buoc tiep
`mem_dict.ps1`: tu ob_sval lui 36 byte ra doi tuong str -> quet heap tim con tro
(me_key) -> doc me_value @+8 -> in kieu + gia tri. Neu value la dict -> in cac cap
key/value de lay SO TI LE.
