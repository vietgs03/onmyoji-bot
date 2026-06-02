# MEMORY - Nghien cuu Onmyoji automation (PC Steam window)

> File nay luu lai kien thuc da hoc tu doc source OAS va dung lam tai lieu noi bo.
> Ngay: 2026-06-02.

## 0. Boi canh setup CUA MINH
- Game: **陰陽師Onmyoji ban Global/EN**, chay **Steam PC window** (KHONG phai gia lap).
- Process: `Client` (PID thay doi, vd 23660), title chua `陰陽師`/`Onmyoji`.
- Window hien tai: **1152x679** @ (2093,58) tren man hinh phu.
- Dieu khien tu **WSL -> powershell.exe -> Win32 API**.
- Toolkit hien co: `ps/control.ps1` (SetCursorPos + mouse_event, FOREGROUND), `scripts/onmyoji.sh`.

## 1. KIEN TRUC OAS (runhey/OnmyojiAutoScript) - mo hinh tham khao
Ke thua tu **Alas (AzurLaneAutoScript)**. Tach lop ro rang:

```
Device  (capture + input + chong stuck)
  -> Platform / Screenshot / Control / AppControl  (multiple inheritance)
Task    (logic tung hoat dong, ke thua BaseTask)
  -> appear() / appear_then_click() / wait_until_appear() ...
Atom    (RuleImage, RuleClick, RuleOcr, RuleSwipe, RuleLongClick...) = "Button" co toa do + asset
Assets  (sinh tu anh template, moi task 1 file assets.py)
```

### Device la multiple-inheritance:
`class Device(Platform, Screenshot, Control, AppControl)` - gop kha nang.
- `screenshot()` co **stuck detection** (Timer 60s/300s), neu cho qua lau -> GameStuckError.
- `click_record` (deque 15): neu click 1 nut >=10 lan hoac 2 nut moi cai >=6 lan -> GameTooManyClickError (chong loop chet).
- Tu chon **screenshot method nhanh nhat** qua benchmark.

## 2. KY THUAT BACKGROUND CONTROL (QUAN TRONG cho PC window)
File: `module/device/method/windows_impl.py` (class `Window(Handle)`).

### Capture nen (khong can foreground):
- `GetWindowDC(hwnd)` -> `CreateDCFromHandle` -> `CreateCompatibleDC` -> `BitBlt(SRCCOPY)`
  -> `GetBitmapBits` -> numpy (h,w,4) -> `cv2.cvtColor(BGR2RGB)`.
- => Chup duoc ngay ca khi cua so bi che/khong focus. (Setup minh hien gio dung
  CopyFromScreen => CAN foreground. Day la diem can nang cap.)

### Click nen (khong chiem chuot that):
- `SendMessage(handle, WM_LBUTTONDOWN, 0, MAKELONG(x,y))` + sleep + `WM_LBUTTONUP`.
- press_time random 100-200ms (fast: 10-40ms) => mo phong nguoi.
- Toa do chia cho `window_scale_rate` (van de DPI scaling cua pywin32 306).
- LUU Y: OAS gui message toi child window cua EMULATOR (mumu/nox/ld co cay handle khac nhau).
  Voi **Steam PC window thuan** thi cay handle se KHAC -> can do lai (xem muc 5).

### Swipe nen:
- Dung **Bezier trajectory** (cBezier.py) de mo phong duong vuot tay nguoi (chong detect).
- `PostMessage(WM_MOUSEMOVE, MK_LBUTTON, lparam)` lien tuc giua DOWN va UP.

## 3. ASSET MATCHING (nhan dien UI)
File: `module/atom/image.py` (class `RuleImage`).
- 2 phuong phap: **Template matching** (cv2.matchTemplate TM_CCOEFF_NORMED, threshold ~0.8)
  va **Sift Flann** (feature match, chong scale/xoay).
- Khai niem **roi_back** = vung TIM trong anh; **roi_front** = vi tri ket qua tim duoc (de click).
- `match()` tra True/False + cap nhat roi_front. `coord()` tra diem click ngau nhien trong roi_front.
- `match_multi_scale()`: thu nhieu ti le 0.5-1.2 => chiu duoc thay doi do phan giai.
- `match_all()` + NMS: tim NHIEU instance (vd nhieu quai/nut giong nhau).
- `match_mean_color()`: kiem tra mau trung binh vung (check trang thai don gian).

## 4. PATTERN VIET TASK (rat sach, hoc theo)
File: `tasks/base_task.py`.
- `appear(target, interval, threshold)`: target la RuleImage/RuleOcr/RuleGif.
  `interval` => Timer chong spam (chi check sau moi N giay).
- `appear_then_click(target, action, interval)`: thay -> click. Pattern chu dao cua moi task.
- `wait_until_appear(target, wait_time)`: vong lap screenshot cho den khi thay.
- `_burst()`: xu ly su kien dot xuat (loi moi ket ban/hiep tro) giua tran.
- Moi task co `limit_time`, `limit_count`, `current_count` + scheduler `set_next_run`.

## 5. KHAC BIET CAN GIAI QUYET cho Steam PC (TODO nghien cuu)
1. **Cay handle**: emulator co child window (TheRender...). Steam PC window co cau truc rieng.
   Can dung Spy++/EnumChildWindows de tim child handle nhan duoc WM_LBUTTON message.
   => NEU background click khong an, fallback ve foreground SetCursorPos (minh dang co).
2. **DPI / scale**: window_scale_rate. Game EN co the chay full-window khac do phan giai.
3. **Toa do/asset**: OAS la server CN. Ban EN khac chu, khac vai layout => phai TU CHUP asset.
4. **OCR**: OAS dung ppocr-onnx (PaddleOCR). Ban EN co the dung OCR tieng Anh de hon (Tesseract eng).

## 6. KE HOACH PORT (cho minh)
- [x] Toolkit co ban WSL->PS (focus/shot/click/drag/key).
- [ ] Nang cap: **background capture** (GetWindowDC+BitBlt) + thu **background click** (SendMessage) cho Steam window.
- [ ] Lop `RuleImage`-like don gian (cv2.matchTemplate) trong Python chay tren WSL doc anh tu captures/.
- [ ] He thong assets: tu chup nut tu screenshot ban EN.
- [ ] Vong lap task dau tien: vd nhan qua / daily don gian de validate end-to-end.

## 7. [DA VALIDATE 2026-06-02] Background capture + click cho Steam PC window
- **bgshot** (PrintWindow flag=2 PW_RENDERFULLCONTENT): chup DUNG cua so game ke ca khi bi
  Chrome che, KHONG can foreground. => giai quyet van de SetForegroundWindow bi chan.
- **bgclick** (PostMessage WM_LBUTTONDOWN/UP toi MainWindowHandle, toa do CLIENT-relative):
  click duoc, KHONG chiem chuot that. Test: click Explore -> mo dung Explore map.
- => Toan bo viec map UI se dung bgshot/bgclick. Toa do tinh tren anh 1152x679 (full window).
- CLI: `./onmyoji.sh bgshot <ten>` , `./onmyoji.sh bgclick <x> <y>`.
