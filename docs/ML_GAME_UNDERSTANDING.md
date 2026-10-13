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
