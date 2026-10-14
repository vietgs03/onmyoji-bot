# Anti-cheat Onmyoji: kiểm tra ở FE (client) hay BE (server)

Ngày 2026-10-14. Nguồn: source đã decompile, chuỗi trong binary native, và message server gửi xuống trong 5 lần resume (4 lần sweep nhanh + 1 lần giãn cách 3–7s).
Tài liệu này chỉ mô tả cơ chế, phục vụ học reverse engineering, không kèm cách né.

## Kết luận
**Có ở cả hai phía, nhưng BE (server) là phần quyết định.** Client chủ yếu thu thập dữ liệu rồi gửi lên. Phát hiện, xử phạt và cả việc ra lệnh kiểm tra đều do server điều khiển. Server có thể đẩy code Python bất kỳ xuống để client chạy (`dynamic_hotfix`).

## 1. FE: client tự kiểm tra rồi gửi log lên
| Cơ chế | Vị trí | Gửi lên server |
|---|---|---|
| **NetEase Yidun** (native, trong `Client.exe`) | export `yidun_cheat_init/_token/setExtraData/setSeniorStatus`, gọi qua `g37misc.yidun_cheat_token` | token Yidun gửi kèm request HTTP nhạy cảm (ví dụ pick card). Server dùng token để đánh giá thiết bị |
| **Speed-hack / sai lệch đồng hồ** | `ClientAvatar.check_player_acc`, chạy mỗi lần `onSyncServerTime` | Nếu tốc độ trôi local/server liên tục ≥0.45 thì gọi `log_check_player_acc{rate_lst, delta_server_time_ls}`, tối đa 1 lần/giờ |
| **Ghi lại vị trí chạm màn hình** | `userinfomgr/ScreenRecordMgr` (bật sau một số lần clear phó bản) | `log_screen_click{recordStr}`: thiết bị, ip, độ phân giải, chuỗi toạ độ chạm. Dùng để phát hiện auto-click hoặc macro |
| **Kiểm tra trận đấu** | `BattleSceneBase.requestCheckBattle` (skill, hero, enemy, monster) | `battle_check{battle_mode, battle_info}`. **Bản EN bỏ qua** (`if LANG.isEnglish(): return`) |
| **Giới hạn RPC/giây** | `_record_and_alert_abnormal_rpc` | Client tự chặn khi một method vượt ngưỡng mỗi giây |
| **Đếm RPC** | `_add_rpc_log` (chỉ server 15048/15049) | `send_rpc_counter_log`: thống kê số lần gọi mỗi method trong giờ |
| Báo cáo cheat chung | `new_client_cheat_report{info}`, `client_checkwg{gtype, checkwg}` | Code gửi có sẵn nhưng **không có lời gọi tĩnh nào**. Nhiều khả năng server kích hoạt qua hotfix |
| Thông tin máy trong login | `authmsg` (loginInfo) | MAC, udid, CPU, `is_simulator`, `real_ip`, `ip_country`, `sys_version`, version script/res/engine, `sauth_str` |
| Binary phụ | `DeviceCheck.exe` | import `IsDebuggerPresent`, `CreateToolhelp32Snapshot`, `Process32*`, `Module32*` (liệt kê process/module) |

## 2. BE: server tự kiểm tra hoặc ra lệnh cho client kiểm tra
Mỗi lần vào phiên, server đẩy **3 `dynamic_hotfix`** (bắt được ở cả 5 lần resume). Client chạy chúng bằng `exec(compile(h))` trong `__main__`:
1. **Đếm module được nạp:** import danh sách module (GhostWalk, `redirect`, RuneChoosePanel, AwakeLevelPanel...) rồi gửi `globals_hps_cb{hps: [__file__...]}`. Mục đích là phát hiện module bị thay hoặc nạp từ đường dẫn lạ.
2. **Toàn vẹn script:** `md5(C_file.get_file("redirect.nxs","script"))` → gửi `fix_hero_data{uid: <nonce mỗi phiên>, md5}`. Đây là challenge kiểu nonce: server biết md5 đúng nên phát hiện script bị sửa, và một client không trả lời cũng tự lộ.
3. **Chống đọc RAM:** đổi tên `player1.inventory` sang tên ngẫu nhiên mỗi phiên (ví dụ `vvqbxubmfr`, `tdpfthkoarzthrjk`, `gzlwxisepb`) và gắn `__getattr__` để code game vẫn chạy. Mục đích là làm hỏng các tool đọc RAM theo tên thuộc tính cố định.

Hai RPC trả lời `globals_hps_cb` và `fix_hero_data` **không xuất hiện ở đâu trong client code**. Chúng chỉ tồn tại trong hotfix do server gửi, nên tool tĩnh không thể biết trước.

Message bảo mật khác server gửi khi vào phiên: `safety_lock` (khoá bảo vệ / mật khẩu cấp 2), `freeze_update` (`GuaranteeData`: đóng băng tài nguyên), `phone_verify_remind_cb`, `double_awake_check_time`.

Phía server còn: kiểm tra sid/authmsg khi `connect_server` (`RECONNECT_FAILED`, `FORBIDDEN`, `MAX_CONNECTION`), mỗi avatar chỉ một kết nối (resume ngoài sẽ đá game), và giới hạn tốc độ RPC (client chỉ chặn trước cho đỡ).

## 3. Quan sát động
| Lần chạy | Nhịp gọi | Kết quả |
|---|---|---|
| sweep nhanh | 147 RPC, 0.35s/lần | 81 trả lời, không lỗi |
| resume tiếp theo (game đã tắt) | 2 RPC | `RECONNECT_SUCCEEDED` |
| resume sau ~17 phút, 3 hotfix challenge **không được trả lời** suốt 4 phiên | – | **`RECONNECT_FAILED (3)`**: phiên bị thu hồi. Không phân biệt được do sid hết hạn hay do bỏ qua challenge |
| phiên mới (game mở lại, authmsg cũ + sid mới) | 81 RPC, 3–7s jitter | Resume được. 62 RPC đầu trả lời, **sau ~333s server ngừng trả lời** (19 RPC cuối im lặng) |
| ngay sau đó | – | Không TCP được tới gate nào (10072/10075/10160/10170), game cũng mất kết nối. List server cập nhật lúc 07:03:43 UTC sang cổng mới. Khớp với **bảo trì server** (user xác nhận), không phải bị ban |

Hệ quả: lần cuối không đủ dữ liệu để kết luận việc giãn cách có tác dụng hay không, vì server bảo trì ngay giữa lần chạy. Không thấy message cảnh báo hay kick nào nhắm vào client ngoài trong 5 lần chạy.

## 4. Điểm học RE rút ra
- Với game NetEase, **nguồn sự thật nằm ở server**. Bộ anti-cheat client có thể được cập nhật bất cứ lúc nào bằng code Python đẩy qua `dynamic_hotfix`, nên chỉ phân tích tĩnh là chưa đủ: phải bắt message lúc chạy.
- Challenge kiểu nonce (`fix_hero_data` với `uid` ngẫu nhiên mỗi phiên) cùng việc đổi tên thuộc tính ngẫu nhiên là hai kỹ thuật chống tool bên ngoài phổ biến, đáng học.
- Thông tin máy trong `authmsg` cho phép server gắn phiên với thiết bị. Dùng lại authmsg từ chỗ khác vẫn mang dấu vân tay của máy gốc.

## 5. Chi tiết: ghi toạ độ chạm `ScreenRecordMgr` → `log_screen_click`
Nguồn: `userinfomgr/ScreenRecordMgr.py`, `scenemembers/*FbScene.py`, `ClientEntities.screen_click_log_by_strength_start`.

**Bật ghi khi:**
- clear đủ số lần trong ngày (bộ đếm `screen_record_dict`, reset mỗi ngày ở `LocalRefreshManager.refresh_screen_record`):
  `rune_fb_num`=10 (Soul Zone/Ngự hồn, gồm cả Hun13), `awake_fb_num`=10, `goren_fb_num`=10, `yaoqi_fb_num`=10, `bgyx_num`=10, `tansuo_fb_num`=40
- server gọi RPC `screen_click_log_by_strength_start` (gắn với mốc tiêu 150 thể lực, log `copy='cost_enegy150'`). Chưa thấy server gọi trong 5 lần bắt message.
- tạo nhân vật mới (`onCreateRole`)
- `game3d.is_outlaw_device()` (root/jailbreak/thiết bị không chuẩn): ghi liên tục, cứ 900s gửi 1 lần

**Ghi gì:** toạ độ (x, y) của 50 lần chạm kết thúc tiếp theo trên layer phủ toàn màn hình (`setSwallowTouches(False)`, nên chạm vẫn đi tiếp vào game). Đủ 50 thì gửi 1 lần rồi tắt. **Không ghi thời điểm** từng lần chạm.

**Payload:** `cur_time, ip, device_model, device_width/height, os_name/os_ver, mac_addr, isp (chỉ CN: IMSI), total_cost (tổng nạp), network, app_channel, app_ver, server, account_id, old_accountid, role_id, invite_code, role_name, past_copy, past_tasks, copy, root, check_msg='{x:y,...}', click_type`.

**Bản global/EN:** không bị tắt (khác `battle_check`). Chỉ khác là `isp` để trống.

**Ý nghĩa:** auto-click spam 1 điểm cho ra 50 toạ độ giống hệt nhau, dấu hiệu rất rõ. Client chỉ thu thập. Xử lý (bỏ qua, cảnh cáo, khóa theo đợt) nằm ở server, không xác định được từ client.
