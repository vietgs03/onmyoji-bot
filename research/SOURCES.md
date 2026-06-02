# Khao sat source automation Onmyoji (de danh gia)

Ngay khao sat: 2026-06-02. Tim tren GitHub theo tu khoa: onmyoji/yys/阴阳师 + auto/bot/脚本.

## #1 (DE XUAT) - runhey/OnmyojiAutoScript  (OAS)
- Link: https://github.com/runhey/OnmyojiAutoScript
- Doc:  https://runhey.github.io/OnmyojiAutoScript-website/
- Stars: **4305** | Forks: 412 | Python 3.10 | GPLv3 | **update hom nay (2026-06-02)**
- Mo ta: "阴阳师自动化脚本, 一键托管" (script tu dong hoa toan dien, ho tro 1 cham)

### Vi sao manh nhat
- Ke thua kien truc tu **Alas (AzurLaneAutoScript)** - framework bot game noi tieng nhat,
  cai tien: tach front/back-end, giam coupling voi game, GUI Flutter da nen tang.
- **OCR moi**: ppocr-onnx (onnxruntime + PaddleOCR) - nhanh, chinh xac.
- **Assets management** rieng (anh/text/diem click).
- Config bang **pydantic**.
- **Bao phu ~60 task**: Exploration, RealmRaid (御魂), Hunt (悬赏), Hyakkiyakou (百鬼, dung AI tha dau),
  Duel (斗技), Secret (秘闻), Orochi (八岐大蛇), Guild, Daily/Weekly...
- Co he thong **scheduler** dieu phoi task, "vo seam".

### Cau truc thu muc (de hoc theo)
```
module/        # engine
  device/      #   ket noi + dieu khien thiet bi (capture, click)
  ocr/         #   OCR
  atom/        #   don vi tac vu nguyen tu (click/swipe/match...)
  base/        #   lop nen
  config/      #   pydantic config
  handler/     #   xu ly tinh huong
  map/         #   ban do (di chuyen)
  daemon/ gui/ notify/ server/ team_flow/
tasks/         # ~60 thu muc, moi cai 1 hoat dong game
  base_task.py #   lop cha cho moi task
  Exploration/ RealmRaid/ Hunt/ Duel/ ...
gui.py script.py server.py   # entrypoints
```
=> Day la mo hinh tham khao tot nhat cho project cua minh: tach **device layer**
   (capture+input) khoi **task layer** (logic tung hoat dong), co OCR + asset matching.

## Cac source khac (tham khao them)
| Stars | Repo | Ngon ngu | Ghi chu |
|------:|------|----------|---------|
| 380 | AcademicDog/onmyoji_bot | Python | da nen tang, don gian hon OAS |
| 424 | zzliux/assttyys_autojs | TS | Android, Auto.js, nhieu tinh nang |
| 72  | xwang233/yys-auto-yuhun | Python/AHK | PC emulator, farm 御魂, gon |
| 38  | YaKun9/YYS-AutoHelpMe | C# | GUI WinForm .NET6 |
| 9   | sup817ch/AutoOnmyoji | Python | auto探索 (exploration) don gian |

## Khac biet voi setup hien tai cua minh
- OAS thuong dieu khien qua **ADB/emulator** hoac capture cua so; minh dang dieu khien
  truc tiep cua so PC qua Win32 (WSL->PowerShell). Logic task & OCR & asset matching
  cua OAS van hoc/port duoc.
- Game cua minh la ban **Global (tieng Anh)** "陰陽師Onmyoji"; OAS chu yeu server CN,
  co fork Asia: necro-wbj/OnmyojiAutoScript-Asia. Asset/toa do se khac -> can remap.
