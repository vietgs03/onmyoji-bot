# Phan tich do ben (robustness) cua lop Perception

> Tra loi truc tiep cho lo ngai: *"game Onmyoji thay doi theo event rat nhieu,
> 5 ngay sau detect se loi, thay skin bat ky thi se bi lech het"*.

Phan tich dinh luong tren **322 anh that** (full-screen 1152x679, gom ca man chua hoc),
khong phai phong doan. Tat ca so lieu deu tai lap bang script + `cargo test`.

---

## 1. He thong nhan dien dua vao GI?

Co **2 co che doc lap**, do ben rat khac nhau:

### a) `state_id` = md5(dhash)[:10] -- nhan dien MAN HINH
`dhash` KHONG hash toan man. No chi hash **4 vung TINH** (da chon ky de tranh
phan dong):

| Vung | Toa do | Y nghia |
|------|--------|---------|
| currency bar | y55-95, ca chieu ngang | vang/ve/sushi |
| cot mode PHAI | x980-1130, y130-560 | Event/Summon/clock... |
| footer text | y600-660 | Collection/Team/Guild |
| ria TRAI | x0-280, y95-600 | avatar/seal |

Va moi vung con bi **resize ve luoi 5x4** roi chi lay 16 bit so sanh cot-ke-cot.
=> dhash da "lam mo" chi tiet nho, chi giu BO CUC THO.

**Vung GIUA man (nhan vat dong, cay sakura, ribbon) bi BO QUA hoan toan.**

### b) `detect_buttons` -- tim NUT de click
Khong template. Dua tren **hinh hoc + mau**: icon tron (Hough) + vung mau bao
hoa cao (saturation). Chi dung khi EXPLORE man moi.

---

## 2. dhash CO bi event/skin lam lech khong?

Mo phong dung kich ban cua user tren cac man nhieu nut nhat:

| Thay doi | dhash hamming | Ket qua (nguong gop = 12) |
|----------|---------------|----------------------------|
| Event them 2 icon + badge do (cot phai) | 0-3 | **GOP dung** (van nhan ra man) |
| Doi skin nhan vat (hue shift vung giua) | 0-2 | **GOP dung** |
| Banner ngang to giua man | 0 | GOP dung |
| Doi so currency (vang +999999) | 5 | GOP dung |
| Popup che 70% man | 4 | GOP dung |

**Ket luan:** dhash BEN hon nhieu so voi lo ngai. Ly do:
- Vung nhan vat/skin **da bi mask** -> doi skin gan nhu khong anh huong.
- Resize ve 5x4 lam mo -> them/bot 1-2 icon nho chi doi 0-3 bit.
- Nguong fuzzy `CANON_THR=12` con du cho cac thay doi nho.

**Khi NAO dhash se lech (>12 bit, hoc lai)?**
- Doi **bo cuc lon** cot mode phai (event thay TOAN BO cum icon, khong phai them 1-2).
- Doi **ngon ngu/UI theme** toan cuc.
- Popup che het ca 4 vung tinh cung luc.
Cac truong hop nay HIEM va thuong la man that su khac -> hoc lai la dung.

---

## 3. 322 man co "tach bach" khong? (chong nham man)

- Cap man gan nhat: hamming **0** voi 1.1% cap.
- NHUNG kiem tra ky: cac cap hamming<=2 co MSE pixel cao **deu khac nhau o vung
  NGOAI stable region (animation/skin)** -> chung la **CUNG man logic, khac frame**.
  Day la THIET KE DUNG (chong nhieu animation), khong phai loi.
- Cac cap that su khac man: hamming median = 31, p5 = 23 >> 12 => tach bach tot.

---

## 4. detect_buttons co ben voi skin khong?

| Thay doi | % nut goc van detect lai duoc |
|----------|-------------------------------|
| Event them icon | **99-100%** |
| Doi skin nhan vat | **69-73%** |

detect_buttons nhay hon dhash voi doi mau (vi no dung saturation). Nhung:
- Cac nut UI THAT (ria man, footer) khong doi mau theo skin -> van detect tot.
- Phan mat (27-31%) chu yeu la cac vung mau o GIUA (false-positive tu nhan vat).
- **Quan trong:** khi navigate, bot KHONG re-detect. No replay toa do da hoc trong
  `world.json` edges. detect_buttons chi can recall tot khi EXPLORE man moi.

---

## 5. Rui ro that su + huong giam thieu

### Rui ro con lai
1. **dhash van la pixel-based.** Event thay doi BO CUC LON cot mode phai (vd mua su
   kien thay 5 icon cung luc) co the vuot 12 -> bot coi la man moi, phai explore lai.
2. **detect_buttons dua vao mau** -> skin sang/toi co the giam recall vung giua.
3. Khong co tang NGU NGHIA: bot khong "hieu" nut "Bat dau" la gi, chi biet toa do.

### Huong giam thieu (lo trinh)
- **B5+**: them kenh **OCR text** vao Observation (da co `ocr.py`). Text "Bắt đầu",
  "Vượt ải" ON DINH hon pixel qua event. Match theo text >> match theo dhash.
- **Template-free + OCR-anchor**: dinh danh man bang TAP TEXT thay vi pixel hash
  -> mien nhiem skin/banner hoan toan.
- **B6 Goal model**: gan y nghia cho man (objective_for) -> bot chon nut theo MUC
  TIEU + text, khong phu thuoc toa do hoc cung.
- Tang `CANON_THR` co kiem soat: margin hien tai (man khac cach >=23 bit) cho phep
  nang nguong len ~18 ma khong nham man -> chiu duoc event lon hon.

### Tom tat 1 dong
> dhash **ben hon lo ngai** (event/skin nho: hamming 0-5, van nhan dung). Diem yeu
> that su la khi event doi BO CUC LON cot phai/footer -> giai phap dung dan la them
> ANCHOR THEO TEXT (OCR), khong phai chinh dhash.

---

## 6. detect_buttons co DOC LAP VI TRI khong? (lat/cat/xao ngau nhien)

> Cau hoi user: *"neu nut khong con o vi tri do nua, dao nguoc anh hoac cat nho roi
> sap xep cuc ngau nhien thi no con detect dung 1 btn khong?"*

Day la cau hoi MAU CHOT: detect nhan theo **NOI DUNG** (hinh/mau) hay nho **VI TRI**?

**Thi nghiem tren anh that (Python + xac minh lai bang Rust):**

| Phep bien doi | Ket qua |
|---------------|---------|
| Lat NGANG (nut sang vi tri guong) | giu **77%** nut (map ve goc) |
| Lat DOC | giu **90%** nut |
| Cat luoi 2x2..6x4, XAO ngau nhien | giu **80-94%** SO nut detect |
| Cat 1 nut, DAN vao vi tri NGAU NHIEN tren nen toi | **97%** tim thay nut o cho moi |

**Xac minh trong Rust** (`cargo test --test robustness`):
- `flip_h.png` (lat ngang): Rust detect 99 nut (khong sup ve 0).
- `pasted.png` (nut dan tai (633,433)): Rust tim thay dung nut o vi tri moi.

**KET LUAN:**
`detect_buttons` (Hough + saturation) hoat dong **CUC BO** - quet ca man tim hinh
tron / vung mau bao hoa, KHONG gia dinh vi tri. Nut o **bat ky** dau cung detect
duoc. Day khac han `dhash`:

| Co che | Phu thuoc vi tri? | Lat/cat/xao -> |
|--------|-------------------|-----------------|
| `detect_buttons` | KHONG (nhan noi dung) | van detect duoc nut o cho moi (~80-97%) |
| `dhash`/`state_id` | CO (vi tri tuyet doi) | VO hoan toan (dung -> man da KHAC that) |

=> Khi event **doi cho** nut (van con nut do, chi o vi tri khac), `detect_buttons`
**van tim ra**. Cai vo la `state_id` (nhan dien MAN), va do la dung: bo cuc doi
nghia la man da khac, can hoc lai duong di. Giai phap ben vung: anchor theo OCR text
(nut "Bat dau" du o dau van la "Bat dau").
