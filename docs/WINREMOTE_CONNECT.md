# Kết nối jcode ⇄ WinRemote MCP (điều khiển Windows) — Hướng dẫn dùng lại

Tài liệu này để **khi bạn đổi model / mở session jcode mới** vẫn kết nối lại được
tới máy Windows (`desktop-il2t9se`) mà không phải dựng lại từ đầu.

## Kiến trúc kết nối

```
jcode (Linux/WSL2)
  └─ mcp-remote  ──► 127.0.0.1:8790  (bridge.py)
                        └─ Tailscale HTTP-CONNECT proxy 127.0.0.1:1055 (tailscaled userspace)
                             └─ 100.84.38.90:8090  ← WinRemote MCP chạy trên Windows
```

- **Máy Windows:** `desktop-il2t9se`, Tailscale IP `100.84.38.90`, WinRemote nghe cổng `8090`.
- **Máy Linux (WSL2):** chạy `tailscaled` userspace + `bridge.py`. Đây cũng chính là
  WSL2 nằm trên cùng máy Windows đó (ổ C: mount ở `/mnt/c`).
- **Auth key (Bearer):** do server WinRemote tạo lúc khởi động (`--auth-key`).
  Key hiện tại đang dùng: xem mục "Bí mật" bên dưới.

## A. Phía Windows — chạy server WinRemote

Mở **PowerShell (Run as Administrator)**:

```powershell
# tao key co dinh 1 lan, luu lai
$key = [Convert]::ToBase64String((1..32 | % { Get-Random -Maximum 256 }))
$key   # <-- copy va luu vao password manager

# chay server (giu cua so nay mo)
py -3.12 -m winremote --host 0.0.0.0 --port 8090 --auth-key $key --enable-tier3
```

- `--enable-tier3` bật các tool ghi/exec (Shell, FileWrite, FileUpload...). Bỏ đi nếu chỉ cần đọc + điều khiển GUI.
- Chạy nền tự khởi động cùng Windows: `winremote-mcp install` (tạo scheduled task).

Firewall chỉ mở cho dải Tailscale (đã tạo rule "WinRemote MCP Tailscale"):

```powershell
New-NetFirewallRule -DisplayName "WinRemote MCP Tailscale" `
  -Direction Inbound -Protocol TCP -LocalPort 8090 `
  -RemoteAddress 100.64.0.0/10 -Action Allow -Profile Any
```

## B. Phía Linux — dựng lại cầu nối

Chạy **một lệnh** (idempotent, chạy lại bao nhiêu lần cũng được):

```bash
bash ~/.local/bin/winremote-connect.sh
```

- Nếu in ra "SAN SANG" → tốt, sang bước C.
- Nếu báo "CAN DANG NHAP" → chạy lệnh nó gợi ý, mở URL hiện ra, đăng nhập
  Tailscale **cùng tài khoản với Windows**, rồi chạy lại script.

## C. Đăng ký MCP trong jcode

Trong phiên jcode, dùng công cụ `mcp` action=connect với:

- **server:** `winremote`
- **command:** `npx`
- **args:** `["-y","mcp-remote@latest","http://127.0.0.1:8790/mcp","--header","Authorization: Bearer <KEY>"]`

Hoặc bảo jcode: *"kết nối MCP winremote qua bridge 8790 với key <KEY>"*.

Kiểm tra nhanh sau khi kết nối: gọi `GetSystemInfo` hoặc `Snapshot`.

> **Lưu ý:** Mỗi khi **restart server WinRemote** trên Windows, phải **đăng ký lại**
> MCP trong jcode (làm lại mục C). Đổi cờ `--enable-all` không cần đổi key nên
> lệnh đăng ký giữ nguyên.

### Full access (khuyến nghị cho làm việc với bot)

Chạy server với `--enable-all` để bật đủ 45 tool (gồm `Shell`, `FileWrite`,
`FileUpload`, `RegWrite`, `ServiceStart/Stop`, `KillProcess`, `App`...):

```powershell
$key = "5vna3w2WSAlb89jjtwDk3P92g0B4GRk/KHwBntmylgw="
py -3.12 -m winremote --host 0.0.0.0 --port 8090 --auth-key $key --enable-all
```

Chỉ đọc + điều khiển GUI (30 tool, an toàn hơn): bỏ `--enable-all`.

## D. Khi ĐỔI MODEL / session mới

1. Bảo model mới đọc file này: `C:\Users\HASAKI\onmyoji-bot\docs\WINREMOTE_CONNECT.md`
   (hoặc bản Linux `~/onmyoji-bot/docs/WINREMOTE_CONNECT.md`).
2. Chạy `bash ~/.local/bin/winremote-connect.sh`.
3. Đăng ký MCP như mục C.
4. Xong. Không cần cài lại Tailscale hay copy source.

## E. Vị trí source Onmyoji Bot

- **Trên Windows:** `C:\Users\HASAKI\onmyoji-bot`  (đã copy, ~367MB, không gồm data nặng)
- **Trên Linux (bản gốc, có git):** `~/onmyoji-bot`
- Dữ liệu nặng **không** được copy (extract lại được): `data/external/`,
  `data/game_assets/`, `data/fandom_images/`, `captures/`, `logs/`, `research/`,
  `eye-rs/target/`, `.venv/`.

Đồng bộ lại code sau này (chạy trên Linux WSL2):

```bash
rsync -a --delete \
  --exclude='.venv/' --exclude='data/external/' --exclude='data/game_assets/' \
  --exclude='data/fandom_images/' --exclude='captures/' --exclude='logs/' \
  --exclude='research/' --exclude='eye-rs/target/' --exclude='__pycache__/' --exclude='*.pyc' \
  ~/onmyoji-bot/ /mnt/c/Users/HASAKI/onmyoji-bot/
```

## F. Bí mật (cập nhật khi đổi key)

- **WinRemote Bearer key hiện tại:** `5vna3w2WSAlb89jjtwDk3P92g0B4GRk/KHwBntmylgw=`
  (đổi key thì cập nhật dòng này và lệnh ở mục C).
- Tailnet: tài khoản `viet.gs03@`, node Linux tên `jcode-linux` (`100.126.17.76`).

## G. Xử lý sự cố

| Triệu chứng | Nguyên nhân | Cách xử lý |
|---|---|---|
| `mcp-remote` báo Empty reply | bridge/tailscaled chưa chạy | chạy lại script mục B |
| Kết nối 401 | sai/đổi Bearer key | lấy key mới ở Windows, cập nhật mục C & F |
| SOCKS/CONNECT fail nhưng ping OK | Windows Firewall chặn 8090 | tạo lại rule firewall mục A |
| `tailscale status` = NeedsLogin | chưa đăng nhập tailnet | `tailscale --socket=... up --hostname=jcode-linux` |
| Đổi máy Windows | Tailscale IP khác | sửa `WIN_TAILSCALE_IP` trong `~/.local/bin/winremote-connect.sh` |

## H. File liên quan (trên Linux)

- `~/.local/bin/winremote-connect.sh` — script dựng lại cầu nối
- `~/.local/state/tailscale/bridge.py` — cầu HTTP-CONNECT 8790 → Windows 8090
- `~/.local/state/tailscale/daemon.log` — log tailscaled
- `~/.local/state/tailscale/bridge.log` — log bridge
- `~/.local/bin/tailscale`, `~/.local/bin/tailscaled` — binary Tailscale userspace
