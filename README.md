# Onmyoji Bot / Research

Bo cong cu nghien cuu & dieu khien game **陰陽師Onmyoji** (Windows) tu WSL.

## Kien truc

```
WSL (bash CLI)  --calls-->  powershell.exe  --Win32 API-->  Game window
     ^                                                            |
     |---------- screenshot PNG (sync ve captures/) --------------|
```

- Game chay tren Windows (process `Client`, title `陰陽師Onmyoji`).
- WSL goi `powershell.exe` de focus cua so, click/drag/key, va chup screenshot.
- Toa do dung trong CLI la **tuong doi so voi goc tren-trai cua so game**.

## Files

| Path | Mo ta |
|------|-------|
| `ps/control.ps1`     | Core PowerShell: info/focus/shot/click/dclick/move/drag/key |
| `scripts/onmyoji.sh` | CLI bash wrapper (tu sync ps1 sang Windows, sync anh ve WSL) |
| `config/coords.json` | Toa do cac nut da map o man hinh chinh |
| `captures/`          | Screenshot luu o day |
| `logs/`              | Log (de danh cho automation sau) |

## Dung nhanh

```bash
cd ~/onmyoji-bot/scripts
./onmyoji.sh info            # PID, vi tri & kich thuoc cua so
./onmyoji.sh focus           # dua game len foreground
./onmyoji.sh shot home       # chup -> captures/home.png
./onmyoji.sh click 451 188   # click nut Explore
./onmyoji.sh drag 100 400 600 400 700   # vuot (700ms)
./onmyoji.sh key ESC
```

## Luu y
- Kich thuoc cua so hien tai: **1152x679** @ (2093,58) - man hinh phu.
- Neu thay doi kich thuoc cua so, can chup lai va remap toa do (hoac them logic scale).
- Man hinh "san nha" la tinh, KHONG di chuyen nhan vat bang click. Di chuyen xay ra trong Explore/ban do.

## TODO / huong nghien cuu
- [ ] Template matching de nhan dien nut tu dong (OpenCV) thay vi toa do cung.
- [ ] Auto-scale toa do theo kich thuoc cua so.
- [ ] Loop tu dong cho Explore (auto-battle).
- [ ] OCR doc so lieu (tien, ve, AP).
