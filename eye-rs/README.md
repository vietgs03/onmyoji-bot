# eye-rs - lop EYE (tri giac) viet bang Rust thuan

`eye-rs` la phan **perception hot-loop** cua onmyoji-bot, port tu `scripts/perception.py`
(OpenCV/Python) sang **Rust thuan** (khong dung opencv crate). Muc tieu cuoi:
mot binary `onmyoji-eye.exe` chay native tren Windows, chup man + CV + tra ket qua
qua localhost socket cho lop Python (BODY/MIND).

## Vi sao Rust o day, khong phai cho Python
Day la vong lap nong: chup -> dhash -> detect_buttons chay lien tuc. Python + cv2
ton ~85ms/frame + chi phi bien WSL<->Windows + PNG 1.7MB/frame. Rust standalone
tren Windows bo het cac chi phi do.

## Vi sao KHONG dung opencv crate
Muc tieu la 1 .exe nhe, de build/cross-compile cho Windows. opencv crate keo theo
toan bo native OpenCV (kho build tren Windows, nang). Cac thuat toan ta can (BGR2GRAY,
resize bilinear, threshold, contour/connected-components, Hough nhe) deu don gian du
de hand-roll, va ta kiem soat duoc do chinh xac bit-level.

## Tuong thich bit-level voi Python (RAT QUAN TRONG)
World model dang co **105 states** khoa theo `dhash` (va `state_id=md5(dhash)[:10]`).
Neu Rust dhash lech, cac state da hoc thanh vo dung. May man:
- `world_model.py` **fuzzy-match**: `hamming(dh, stored) <= 12` (CANON_THR), KHONG exact.
- Thuat toan fixed-point cua ta dat **max hamming = 2** tren 105 goldens => an toan lon.

Moi thay doi perception PHAI chay `cargo test` (so voi `tests/goldens/`) truoc khi merge.

## Cau truc
- `crates/eye-core` : thu vien thuan (decode PNG, gray, resize, dhash, detect_buttons).
  Khong I/O he thong, de test. Day la phan port tu perception.py.
- `crates/onmyoji-eye` : binary (capture Windows + socket server). Se lam o buoc sau.
- `tests/goldens/` : oracle sinh tu Python (`perception_goldens.json`) - nguon su that
  de validate Rust khop Python.

## Lo trinh noi bo
- [ ] P1: eye-core dhash + state_id, test khop goldens (hamming<=2)
- [ ] P2: detect_buttons (Hough circle + saturation contour + NMS)
- [ ] P3: onmyoji-eye binary (capture + socket, theo contracts/schema.json)
- [ ] P4: RustEye adapter ben Python (onmyoji/adapters/eye_rs/) noi qua socket
