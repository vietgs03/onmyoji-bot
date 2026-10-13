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
