# Danh gia RustEye theo OAS action tasks

## Muc tieu
Dung OAS (research/OAS) lam **ground-truth** de danh gia RustEye + perception cua bot:
- OAS co 38 page (man hinh game) + 66 link dieu huong (page.py) - ban do game da kiem chung.
- OAS co 59 task (feature game) voi assets (anh template + ROI) - cach nhan/click moi man.
- OAS chay 1280x720, template matching tai ROI chinh xac.

Game that cua ta: client 1136x640 (ti le 0.888 so OAS, cung 16:9 -> scale duoc).

## Cach danh gia (3 tang)

### Tang 1: Page detection (man hinh nao)
- Port OAS `appear()` (template match tai ROI, scale 0.888) -> detector chinh xac.
- So sanh: RustEye dhash/state_id co phan biet duoc cac page nhu OAS khong?
- Metric: tren N frame, ty le RustEye + OAS-detector dong y "dang o page X".

### Tang 2: Navigation (di chuyen dung)
- Dung OAS page graph (page_main -> page_exploration qua I_MAIN_GOTO_EXPLORATION...).
- Test: RustEye navigate co di dung duong nhu OAS map khong.
- Metric: ty le navigate thanh cong toi N page dich.

### Tang 3: Action features (lam dung viec)
- Chon vai task don gian (vd Exploration, FriendBoss, MysteryShop).
- Test: RustEye + bot logic co hoan thanh duoc buoc dau cua task khong.
- Metric: so buoc task hoan thanh / tong buoc.

## Trang thai
- [ ] Tang 1: OAS page detector (template match, scale 0.888)
- [ ] Tang 1: so sanh RustEye vs OAS tren live frames
- [ ] Tang 2: extract OAS page graph -> so voi world model
- [ ] Tang 3: chon + chay 1-2 task don gian

## Ghi chu ky thuat
- OAS asset: research/OAS/tasks/GameUi/page/*.png (check_button moi page)
- OAS page graph: research/OAS/tasks/GameUi/page.py (38 page, 66 link)
- Scale OAS->game: x * 1136/1280, y * 640/720 (~0.888)
- RustEye: ONMYOJI_EYE=rust, observe()/observe_nav()/act()

## KET QUA TANG 1 (page detection)

Test 15 frame live (game dang o HOME):
- **OAS template detector: 15/15 = 100%** nhan dung page_main (score 0.989)
- **dhash world model: 0/15 = 0%** (live HOME dhash hamming 22-35 so 24 state HOME da luu, deu > threshold 12)

### PHAT HIEN QUAN TRONG
dhash tren TOAN man qua nhay voi man DONG (HOME co shikigami dong, thong bao
thay doi). 24 state HOME trong world model van khong khop live HOME.

OAS manh hon vi match 1 VUNG NHO ON DINH (nut menu tai ROI co dinh) thay vi
hash ca man. -> Bai hoc: page detection nen dua tren landmark on dinh, khong
phai full-screen hash.

### DE XUAT
1. Them "page detector" kieu OAS vao perception (template match landmark) ->
   robust hon dhash cho dieu huong. dhash van dung cho state chi tiet.
2. Hoac: tinh dhash tren VUNG on dinh (top bar/menu) thay vi toan man.
