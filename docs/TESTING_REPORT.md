# Báo cáo kiểm thử client/giao thức Onmyoji (bản Steam EN)

Ngày: 2026-10-14. Tài khoản: acc phụ của người kiểm thử. Phạm vi: chỉ đọc dữ liệu và thao tác UI hợp lệ.
**Không** gửi RPC thay đổi trạng thái từ client ngoài, **không** gửi kết quả trận.

## 1. Môi trường
| Mục | Giá trị quan sát |
|---|---|
| Client | Steam, `client.exe` (NeoX, Python 2.7 nhúng), `login_channel=netease_global_steam` |
| Server | Gate TCP `34.48.52.40` (cổng đổi theo phiên: 10072 → 10172 → 10178) |
| Phiên bản | `patch/res/script_version=1.8.13.2423310` |
| Công cụ | `pyobj_dump.ps1` (đọc RAM), `onmyoji_netclient.py` (client giao thức độc lập), `api_sweep.py`, `control_client.py` (click UI) |

## 2. Phạm vi đã kiểm
| Hạng mục | Kết quả |
|---|---|
| Danh mục RPC từ code | 2,193 RPC client→server, phân loại sơ bộ 423 đọc / 1,146 ghi / 624 chưa rõ |
| Sweep đọc đợt 1 | 147 RPC không tham số, **81 trả lời** |
| Sweep đọc đợt 2 | 72 RPC không tham số, **34 trả lời** (lọc thêm theo thân callback) |
| Tác dụng phụ | 0 message cộng/trừ vật phẩm, tiền, phần thưởng trong cả 2 đợt |
| Daily qua UI | Quick Done + Claim all: điểm hoạt động 0 → 40, mốc 20/40 nhận; xác minh lại bằng RAM |
| Trạng thái phạt | `freeze_update` = 0 sau toàn bộ quá trình (không bị xử phạt) |
| Chưa kiểm | ~220 RPC đọc cần tham số; các RPC ghi/trận đấu (ngoài phạm vi) |

## 3. Phát hiện
### 3.1 Xác thực phiên
- Resume phiên chỉ cần `deviceid`, `entityid` và `authmsg` (BSON) đọc từ RAM client. Client ngoài resume thành công (`RECONNECT_SUCCEEDED`).
- `authmsg` chỉ có trong RAM **sau khi client tự reconnect ít nhất 1 lần**. **Cập nhật 2026-10-15:** không cần đợi reconnect. `authmsg` cũ dùng lại được, chỉ cần thay `session` = sid hiện tại và `versions` (đều đọc từ RAM). Resume vẫn thành công cả khi game client đã thoát. Token không gắn với lần đăng nhập.
- Mỗi avatar một kết nối: client ngoài vào thì game hiện "Your account has been logged in elsewhere". Đây là cơ chế tốt, đã xác nhận 2 lần.
- `authmsg` chứa thông tin thiết bị: MAC, udid, CPU, `real_ip`, `ip_country`, `sys_version`, `sauth_str`.

### 3.2 Challenge chống tool qua `dynamic_hotfix`
- Mỗi phiên server đẩy 3 đoạn Python: đếm module nạp (`globals_hps_cb`), md5 script với nonce (`fix_hero_data`), đổi tên ngẫu nhiên `player1.inventory`.
- Client ngoài không trả lời challenge. Server không đá kết nối hay phạt ngay trong các lần quan sát. Phản ứng (nếu có) nằm ở server, không thấy từ phía client.

### 3.3 Kiểm tra trận đấu
- `BattleSceneBase.requestCheckBattle` (`battle_check`) **bị tắt ở bản EN** (`if LANG.isEnglish(): return`).
- Drop do server định trước (`rewardId`). Không có tham số điều khiển tỉ lệ rơi.
- Không kiểm thử động bằng cách gửi kết quả trận (ngoài phạm vi, xem mục 5).
- **Client ngoài mở được trận Soul Zone (2026-10-15).** `dungeon_rune_attack` gửi từ client ngoài được server chấp nhận: trừ stamina, cấp `rewardId`, cộng tiến độ nhiệm vụ. Không gửi `result` thì không có thưởng.
- **Bộ đếm lượt ngày Soul Zone (`day_limit_pc["2"]`, trần 500) chỉ tăng khi trận hoàn tất**, không tăng lúc mở trận (4 lần mở bằng API, bộ đếm giữ nguyên 2; 1 trận đánh thật trong game: 2 → 3). Hiện chưa thấy cách lấy thưởng vượt trần, vì không có `result` thì không có thưởng. Chưa kiểm được server có chặn `result` khi đã chạm trần với các trận mở từ trước hay không (cần gửi `result`, ngoài phạm vi). Chi tiết: `SOUL_RUNE_API.md` §3e.

### 3.4 Lộ dữ liệu ra client (đề xuất xem xét)
- Các reply `friend_get_list_return`, `friend_get_recommend_return`, `get_team_friend_cb`, `friend_other_add_notify` chứa trường **`high_risk_account`** của **người chơi khác** (75 đối tượng quan sát, tất cả `False`). Cờ đánh giá rủi ro nội bộ không nên gửi xuống client.
- Cùng object còn có `location`, `online`, `olt/llt` (thời gian online/offline gần nhất).

### 3.5 Theo dõi hành vi
- `ScreenRecordMgr` ghi toạ độ 50 lần chạm sau 10 lần clear Soul/Awake/... mỗi ngày, gửi `log_screen_click`. Bản EN vẫn bật.
- `check_player_acc` so tốc độ đồng hồ local/server mỗi lần `onSyncServerTime`.

## 4. Đề xuất cho team Game
1. Không gửi `high_risk_account` (và cân nhắc `location`) của người chơi khác xuống client.
2. Cân nhắc gắn `authmsg` resume với kết nối TCP/thiết bị gốc, hoặc rút ngắn thời hạn, để giảm việc resume bằng token đọc từ RAM.
3. Bật lại `battle_check` cho bản EN, hoặc xác nhận server đã có kiểm tra tương đương.
4. Xử lý phiên không trả lời `dynamic_hotfix` (hiện vẫn dùng được RPC đọc bình thường).
5. Xác nhận `day_limit` được kiểm ở **cả** `dungeon_rune_attack` lẫn `dungeon_rune_attack_result`. Nếu chỉ kiểm lúc mở trận thì có thể mở sẵn nhiều trận trước khi chạm trần rồi nộp `result` sau. Nên giới hạn số trận đang mở cùng lúc và thời hạn của `rewardId`.
6. Mở trận (`dungeon_rune_attack`) từ phiên không trả lời `dynamic_hotfix` và không gửi `log_screen_click` vẫn được chấp nhận. Có thể dùng làm tín hiệu nghi tool.

## 5. Giới hạn
- Kiểm thử trên **server production** (gate public, người chơi thật trong danh sách bạn bè, có bảo trì và sự kiện live). Vì vậy không gửi RPC ghi hay kết quả trận từ client ngoài.
- Để kiểm thử luồng trận đấu (giả `result`, sai `rewardId`, spam RPC), cần **server staging/QA** do team Game cấp.
- Dữ liệu thô (`api_sweep*_all.jsonl`, `session.json`, `authmsg.bson`) chứa token và dữ liệu người chơi khác, **không đính kèm**.
