# Giao thức mạng Onmyoji (gate RPC), đọc từ code đã dịch và RAM

Ngày 2026-10-14. Đã kiểm chứng bằng client độc lập `research/npk/onmyoji_netclient.py`.

## Tóm tắt
Không có HTTP API hay api key cố định. Gameplay đi qua **TCP tới gate** (ví dụ `34.48.52.40:10075`, lấy từ `mini_server_list_*.txt`):

```
frame      = u32le(len(pb)+2) | u16le(method_index) | protobuf        (lib/mobilerpc/RpcChannel.py)
client->sv = RC4( zlib_sync_flush(frame) )                             (ConnectionDecorator.send_data)
sv->client = zlib_decompress( RC4(data) )                              (stream liên tục)
```

1. `seed_request(Void)` → `seed_reply(SessionSeed{seed})`
2. Client tạo `session_key = SHA1(rand32)`, gửi `session_key(EncryptString{ RSA-OAEP(loginpubkey, SessionKey{pad, key, seed, pad}) })`.
   `loginpubkey` là RSA-2048 nằm trong `Globals.loginpubkey`. Sau bước này bật RC4(session_key) cho cả hai chiều. Server trả `session_key_ok`.
3. `connect_server(ConnectServerRequest)`:
   - `NEW_CONNECTION` khi đăng nhập mới. Sau đó account entity gọi `login_with_sdk` bằng token SDK NetEase.
   - `RE_CONNECTION` khi vào lại phiên, gửi kèm `deviceid`, `entityid` (ObjectId 12 byte của avatar) và `authmsg` (BSON loginInfo, chứa `session` = sid, `sauth_str`, thông tin máy...).
   - Sau `connect_server` bật zlib. Server trả `connect_reply(RECONNECT_SUCCEEDED=2)`.
4. RPC gameplay: `entity_message(EntityMessage{id, method=Md5OrIndex{md5(tên) | index}, parameters=msgpack(dict)})`.
   Server trả về `<tên>_cb` theo cùng định dạng. ObjectId trong msgpack là ExtType 42.

Schema protobuf (`common.proto`, `client_gate.proto`) được lấy nguyên dạng `FileDescriptorProto` từ RAM, nằm trong `research/npk/data/proto/*.desc`.

## Đã chạy thử (2026-10-14 06:13)
Client Python độc lập, không cần game, đã làm được:
- Bắt tay RSA + RC4 → server trả `session_key_ok`.
- Resume phiên bằng authmsg đọc từ RAM → `RECONNECT_SUCCEEDED`.
- Nhận ~60 message đồng bộ lúc vào phiên: inventory, cấu hình ngự hồn (`req_equip_set_info_cb`), rank (`get_rank_score_cb`), guild...
- Gọi các API chỉ đọc và nhận được trả lời:
  - `ping_message` → `{'new_ver': '1.8.13.2423310', 't': ...}`
  - `get_shop_sort_info` → `get_shop_sort_info_cb {'skin_buy': [[id, count], ...]}`
  - `get_guild_task_info` → `{'guild_lv': 8, 'construction': 382500, ...}`
  - `get_guild_achieve_info` → `{'achieve_lv': 9, ...}`
- Tên method được giải từ md5 bằng từ điển 214k định danh lấy từ code (`data/md5_names.json`). 54/55 method resolve được.

## Lưu ý quan trọng
- **Mỗi avatar chỉ có một kết nối.** Khi client ngoài resume vào, server đá kết nối của game. Trong lần chạy thử, game client đã thoát sau khi bị chiếm phiên.
- Phiên (`sid`) hết hạn hoặc đổi khi game đăng nhập lại. Mỗi lần cần đọc lại `authmsg` và `entityid` từ RAM (xem `pyobj_dump.ps1`: `GateClient.reconnect_data`).
- `session.json` và `authmsg.bson` chứa token tài khoản. Chúng nằm trong `research/` (gitignored), **không commit**.
- Chỉ gọi RPC đọc dữ liệu. Gọi RPC thay đổi trạng thái (mua bán, cường hóa...) từ client ngoài có rủi ro bị phát hiện (`_record_and_alert_abnormal_rpc`, log `rpc_counter`) và bị khóa tài khoản.

## Rà toàn bộ API (2026-10-14 06:18)

### Danh mục RPC (`research/npk/rpc_catalog.py` → `data/rpc_catalog.json`)
- Trích được **2,193 RPC client→server** từ code đã dịch (`callServerMethod`/`callServerMethodDeprecated`), kèm file, hàm gọi, tên tham số và mẫu tham số.
- 1,449 RPC có handler `<tên>_cb` phía client.
- Phân loại theo tên (heuristic): 423 đọc, 1,146 ghi, 624 không rõ.
- Nhóm lớn nhất: `get_*` 218, `guild_*` 106, `lbs_*` 98, `sg_*` 66, `team_*` 59, `friend_*` 50, `gamble_*` 49, `hero_*` 44, `gym_*` 44, `equip_*` 21.
- Danh sách này chưa đủ: thiếu RPC gọi qua tên động (`'{}.open_box'.format(...)`, hằng `RpcConst.*`) và RPC của hàm bị lỗi decompile.
- Client tự chặn khi một method bị gọi quá ngưỡng `RPC_PER_SEC_TIMES_RELEASE_THRESHOLD` lần mỗi giây (`_record_and_alert_abnormal_rpc`). Sweep chỉ gọi mỗi method 1 lần, cách nhau 0.35s.

### Sweep bằng phiên đã lấy (`research/npk/api_sweep.py`)
- Chọn 147 RPC thuộc loại đọc và **không cần tham số**, đã loại các tên chứa reward/buy/use/send/claim/draw/battle/set/...
- Kết quả: resume thành công, **81/147 trả lời** với `<tên>_cb`/`_callback`/`_return`, độ trễ 0.23–0.56s.
- 66 RPC im lặng: chủ yếu là sự kiện đã đóng (`asura_*`, `sg_*`, `luna_*`, `gongyi_*`), cần tham số thật, hoặc server trả về dưới tên khác (`get_season_resume` → `get_dojo_resume_cb`, `get_cur_guess_info` → `update_player_guess_data`).
- Tên method trả về giải được 173/174 qua từ điển md5.
- Phiên đã resume 4 lần liên tiếp trong khoảng 7 phút mà vẫn hợp lệ (sid không đổi khi chỉ reconnect).
- Dữ liệu chi tiết nằm trong `data/api_sweep_results.json`, `data/api_sweep_all.jsonl`, `data/api_sweep_table.md` (gitignored vì chứa dữ liệu tài khoản).

Một số API đọc tiêu biểu đã có trả lời:
| RPC | Reply | Nội dung |
|---|---|---|
| `friend_get_list` | `friend_get_list_return` | danh sách bạn, black list |
| `guild_get_info` / `get_guild_members` | `guild_info_cb` / `get_guild_members_cb` | thông tin và thành viên guild |
| `get_shop_items` / `get_shop_sort_info` | `*_cb` | hàng trong shop, xếp hạng skin bán chạy |
| `mission_get_list` | `*_cb` | nhiệm vụ |
| `damage_boss_get_info` / `_rank` | `*_callback` | điểm và hạng boss |
| `dojo_member_self_win_info` | `*_cb` | thống kê đạo trường |
| `ask_pet_dress_record` | `*_cb` | trang phục pet đã sở hữu |

**Cách hiểu yêu cầu "rà toàn bộ api với session key mới lấy được":** (1) liệt kê đầy đủ các API có trong client, (2) dùng phiên vừa lấy để gọi thật diện rộng. Bước gọi thật chỉ áp dụng cho API **đọc, không tham số**, để tránh thay đổi tài khoản. API ghi và API cần tham số mới được liệt kê, chưa gọi.

### Kiểm chứng phân loại đọc/ghi
- **Mẫu ngẫu nhiên gán nhãn tay** (seed 7, 20 API mỗi lớp, dựa trên tên, tham số và hàm gọi):
  - Lớp `read` đúng 19/20. Sai: `dojo_answer_big_data`, thực chất là gửi đáp án.
  - Lớp `write` đúng 18/20. Sai: `precheck_lbs_set_hero2other`, `lbs_request_all_JJCard_compose_plan`, thực chất là truy vấn.
  - Lớp `unknown` thực tế gồm 16 ghi và 4 đọc, nên không được coi `unknown` là an toàn.
- **Danh sách sweep** (147 API) được soát lại bằng regex các từ nguy hiểm (answer/commit/finish/choose/vote/play/share/trigger/sync/apply...). 11 tên bị gắn cờ, xem tay thì đều là truy vấn `get_*`/`search_*`/`req_sync_*_info` gọi với `{}`.
- **Kiểm theo hành vi:** trong toàn bộ message server gửi trong lúc sweep, không có message cộng hoặc trừ vật phẩm, tiền hay phần thưởng. Chỉ có `entity_param_update` sau `get_share_boss_info` (dấu thời gian `ffmld` / bộ đếm hiển thị `ffmt`) và sau `get_recommend_yuyue_guild` (`src`). Đây là trạng thái UI/cooldown, không phải tài nguyên.
- **Kết luận:** độ chính xác của heuristic khoảng 90–95%, đủ để chọn ứng viên. Trước khi gọi bất kỳ API nào ngoài danh sách đã kiểm, vẫn phải xem tay hàm gọi.

## Sweep đợt 2 (2026-10-14 17:18)
- Danh sách: `research/npk/build_sweep2.py` → 72 API đọc, không tham số, chưa có ở đợt 1.
  - Ngoài lọc theo tên, còn **đọc thân hàm gọi và callback**. Trong game này `get_` hay nghĩa là *nhận*: `cx_get_free_blue`, `guild_get_day_funds_bonus`, `cclive_get_red` mở `RookieRewardPanel`. `try_get_discount` random lại mức giảm giá. Bộ lọc loại 14 API như vậy.
  - Loại tay: `get_event_from_set` (Quick Done dùng để lấy sự kiện Fengmo, tiêu lượt `EVENING_EVENT_COUNT`), mã mời bạn.
- `api_sweep.py` giờ từ chối chạy nếu `session` trong `authmsg.bson` khác `sid` hiện tại (tránh resume bằng token cũ).
- Kết quả: resume OK (`connect_reply 2`), **34/72 trả lời**, độ trễ 0.3–4.7s. Gap 0.35s + jitter 0–0.4s.
- Kiểm hành vi: 110 message server gửi, không có message cộng/trừ vật phẩm hay tiền. `guild_ask_day_funds_bonus_cb` chỉ trả `{err_code:0, donate:40}` (xem số quỹ, không nhận). `safety_lock {err:3}` và 3 `dynamic_hotfix` là đợt sync bình thường lúc vào phiên (đã thấy ở đợt 1).
- Game client hiện "Your account has been logged in elsewhere" như dự kiến (mỗi avatar một kết nối). Bấm OK để đăng nhập lại.
- Tổng phủ API đọc không tham số: 147 + 72 = 219 đã gọi, 115 trả lời. Còn ~220 API đọc **cần tham số** (uid, id sự kiện...), phải lấy giá trị thật từ RAM/đợt sync trước khi gọi.

| RPC | Reply | Nội dung |
|---|---|---|
| `mail_on_get_mails_list` | `_return` | `mails, cnt, err` |
| `friend_get_relations` | `_callback` | quan hệ, độ thân, tương tác |
| `guild_get_online_members` | `_cb` | thành viên guild online |
| `get_dinner_info` | `_cb` | tiệc guild, số lần trong tuần |
| `gym_query_defend_level` / `gym_get_defends_as_leader` | `_cb` | phòng thủ Guild Realm |
| `gym_query_season_stamps` | `_cb` | mốc thời gian mùa |
| `auto_yuhun_query_progresst` | `_cb` | tiến độ auto ngự hồn `err, remain, p` |
| `hero_batch_get_cult_num_rate` | `_cb` | tỉ lệ nuôi thức thần |
| `free_fengmo_get_calendar` | `_cb` | lịch Fengmo miễn phí |
| `damage_boss_get_world_damage` | `_callback` | tổng sát thương boss thế giới |
| `ns_get_month_card_count` | `_cb` | số thẻ tháng |
