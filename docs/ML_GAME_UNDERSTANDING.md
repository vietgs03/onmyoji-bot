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
