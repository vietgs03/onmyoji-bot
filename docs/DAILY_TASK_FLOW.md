# Luồng Daily Task (nhiệm vụ ngày / điểm hoạt động) Onmyoji

Ngày 2026-10-14. Suy ra từ source đã decompile. Mục đích: hiểu luồng để làm tool nhận thưởng (chỉ claim việc đã hoàn thành thật trong game), không bịa kết quả trận.

## Mô hình
- "Nhiệm vụ ngày" tích **điểm hoạt động** (currency `DAY_ACTIVE_SCORE`, id tiền tệ dùng ở `getDailyTaskCurActiveScore`).
- Mỗi nhiệm vụ con hoàn thành → server tự cập nhật qua `daily_task_update` / `daily_task_update_list` (server→client, không cần client xin).
- Người chơi bấm nhận: điểm từng nhiệm vụ, rương theo mốc điểm, và event.

## RPC liên quan (client → server)
| RPC | Tham số | Ý nghĩa | Loại |
|---|---|---|---|
| `daily_task_commit_score{id}` | id nhiệm vụ | nhận **điểm hoạt động** của 1 nhiệm vụ đã xong | claim |
| `daily_task_commit_reward{rid}` | rid mốc rương | nhận **rương mốc điểm** (90/160/...); client tự chặn nếu `score < data['score']` hoặc đã nhận | claim |
| `daily_task_commit_act_reward{id}` | id event | nhận thưởng event nhiệm vụ ngày | claim |
| `get_daily_task_reward_list{reward_id}` | id | chỉ xem danh sách thưởng (đọc) | read |

## Callback (server → client)
- `daily_task_commit_reward_cb(err, rid, rewards)`: `err==0` thành công, rid vào `daily_task_reward`.
- `daily_task_commit_act_reward_cb(err, id, rewards)`: `err==0` ok, `err==1` = "đã nhận".
- `daily_task_event_update(info)`, `daily_task_update(t_id, t_data)`, `daily_task_update_list(update_list, rewards)`: server chủ động đẩy tiến độ.

## Điều kiện client kiểm trước khi gửi (từ `MonthMainPanel.dayTaskBoxClick`, `DailyTaskLogic`)
```
nowScore = player1.currency[DAY_ACTIVE_SCORE]
data = DATA_DAILY_TASK_REWARD.data[eid]
if nowScore < data['score'] or eid in player1.daily_task_reward:
    get_daily_task_reward_list(eid)      # chỉ xem, chưa đủ điều kiện
else:
    daily_task_commit_reward(eid)        # đủ điểm & chưa nhận -> claim
```
→ **Tool chỉ nên claim khi `score >= nguong` và `rid chưa có trong daily_task_reward`.** Hai giá trị này đọc được từ entity `player1` trong RAM hoặc từ các message `daily_task_update*` server gửi lúc đăng nhập.

## Nguồn dữ liệu trạng thái (đọc, không cần đánh)
- `player1.daily_task` (dict tiến độ từng nhiệm vụ), `player1.daily_task_reward` (list mốc đã nhận), `player1.daily_task_event`.
- `player1.currency[DAY_ACTIVE_SCORE]` = điểm hoạt động hiện tại.
- Bảng: `cdata_en.daily_task.json` (định nghĩa nhiệm vụ), `cdata_en.daily_task_reward.json` (mốc/thưởng).

## Ranh giới an toàn cho tool
- **Chỉ gọi 3 RPC claim ở trên** cho nhiệm vụ server đã đánh dấu hoàn thành (`daily_task` cho thấy đủ tiến độ). Không gửi RPC đánh trận, không bịa `iswin`/record.
- Trước khi claim phải đọc trạng thái thật để không gửi mốc chưa đủ điểm (server trả `err` và có thể ghi cờ bất thường nếu spam mốc chưa đạt).
- Luôn trả lời 3 challenge `dynamic_hotfix` nếu muốn phiên trông giống client thật (hiện tool chưa làm → server phân biệt được).
