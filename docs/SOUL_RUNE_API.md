# Soul Zone (Ngự hồn) - API trận Rune và payload

Cập nhật 2026-10-15. Nguồn: code game dịch từ RAM (`research/npk/src_decompiled/avatarmembers/DungeonMember.py`, `module/fubenlevel/runelevelsystem.py`), bảng cấu hình `research/npk/data/cdata/cdata_en.dungeon_rune.json`, và một lần đọc RAM lúc đánh trận thật.

## 1. Luồng 1 trận (đơn, Orochi Lv.1-10 / Moan / Judgment / Aether / Fallen Sun / Sea of Eternity)

```
1. client -> server  dungeon_rune_attack
                     {"dungeon_id": <id>}

2. server -> client  dungeon_rune_attack_return(dungeon_id, rewardId, copy_skin_id)
                     client lưu: player1.dungeon_reward['dungeon_rune'] = rewardId
                     rồi vào màn trận (enterMainUi MODE_RUNE_FB)

3. đánh xong:
   client -> server  dungeon_rune_attack_result
                     {"dungeon_id": <id>,
                      "result": {"iswin": <bool>, "rewardId": <rewardId bước 2>},
                      "heroes": <fightHeroUids của engine trận>,
                      "buff":   helpers.getSkinBuffList()}

4. server -> client  dungeon_client_attack_return(reward)  -> hiện PanelReward
```

- Bước 1 do `runelevelsystem.GotoLevelBtnClickedCallback` gọi khi bấm Challenge (kèm `save_begin_battle_params(MODE_RUNE_FB, {'func':'dungeon_rune_attack', 'cid':900003, 'limit':<strength>})`).
- Bước 3 do `runelevelsystem.CallWhenBattleFinish(isWin, battle_id)` gọi.
- Guard trong `dungeon_rune_attack`: `if 10 < dungeon_id <= 100: return`. Id 11-13 (Sougenbi) không đi đường này mà dùng `team_create_yeyuanhuo(...)`. Tầng có `battleid==102` có thể đi `team_create_rune_single`.
- Các chế độ khác cùng mẫu, khác key trong `dungeon_reward`:
  `dungeon_challenge_*` -> `'dungeon_challenge'`, `dungeon_challenge_leaf_*` -> `'dungeon_leaf_challenge'`, `dungeon_awake_*` -> `'dungeon_awake'`, `dungeon_friend_*` -> `'dungeon_friend'`.

### Không có API bỏ qua trận
Đã rà 2,193 RPC trong `rpc_catalog.json` (tìm sweep/quick/saodang/multi/repeat/batch/auto_battle/again). Soul Zone chỉ có `dungeon_rune_attack`, `dungeon_rune_attack_result`, `team_create_rune`, `team_create_rune_single`, `rune_plot_finish_dialog`.
- Nút "Đánh lại" (`PanelReward`) chỉ gọi lại `dungeon_rune_attack(*params)` phía client, kèm `from_again_btn=True`. Mỗi lần vẫn là một trận mới.
- `auto_yuhun_*` là công cụ tính bộ ngự hồn tối ưu (calc/rank), không phải farm.
- Không có RPC nào trả thưởng Soul mà không qua trận.

## 2b. Orochi Lv.1-10 rơi gì (bảng phần thưởng thật của game)

Nguồn: `RuneLevelInfoDict[1]` (module `com.data.cdata_en.dungeon_rune`, đọc RAM) có **một** `loot_id` chung cho cả Lv.1-10: `"4418|4419|4420|4421|4422|4423|4424"`, `leveldesc: "Drops G5-G6 Souls"`. Game chọn theo **thứ trong tuần (giờ UTC+8)**: `loot_id = lootList[dayOfWeek]` (`runelevelsystem.getCurrencyList`, Mon=0). Bảng `reward` (`DATA_REWARD`) cho từng loot_id:

| Thứ | loot_id | Bộ ngự hồn rơi | coin | EXP |
|---|---|---|---|---|
| T2 | 4418 | Snow Spirit, House Imp, Claws, Jizo Statue + 2 bộ mới (300079, 300080) | 1800 | 1860 |
| T3 | 4419 | Holy Flame, Fortune Cat, Scarlet, 300007 + 2 bộ mới (300081, 300082) | 1800 | 1860 |
| T4 | 4420 | Mimic, Boroboroton, Harpy, 300035 + 2 bộ mới (300083, 300084) | 1800 | 1860 |
| T5 | 4421 | Shy Soul, Watcher, Tree Spirit, Seductress + 2 bộ mới (300079, 300082) | 1800 | 1860 |
| T6 | 4422 | Dawn Fairy, Mirror Lady, Priestess, Shadow + 2 bộ mới (300080, 300083) | 1800 | 1860 |
| T7 | 4423 | Soul III (900180, ngẫu nhiên) + 300081, 300084 | 1800 | 1860 |
| CN | 4424 | Soul III + cả 6 bộ mới 300079-300084 | 1800 | 1860 |

- `Soul III` (900180): "Grants the same souls of the day (obtainable from stage 1-10)".
- Tên lấy từ bảng vật phẩm `DATA_CURRENCY` giải mã từ RAM (20,446 dòng) và bảng dịch EN cùng chỉ mục (`translate_buf`, 62,166 chuỗi). 300007, 300035 và 6 bộ mới 300079-300084 (icon `hscard_0064_1`..`0069_1`) không có dòng tên trong `DATA_CURRENCY`. Tên nằm ở `DATA_CARD_INIT`, mà module này chưa load trong lần chạy (chỉ load khi mở màn ngự hồn).
- **Mọi tầng 1-10 dùng chung danh sách bộ rơi.** Bảng không có khác biệt theo tầng. Tầng chỉ đổi stat quái (`atk_alter`, `crt_alter`, `def_alter`: Lv.1 atk -0.7, Lv.10 atk +2.5) và `strength` (stamina). Số sao/số lượng ngự hồn theo tầng và tỉ lệ rơi **không có trong client**, nằm ở server.
- Gọi `dungeon_rune_attack` 1-10 qua API **không** cho biết thêm: lời gọi chỉ trả `rewardId`, nội dung thưởng chỉ tới sau `result` thắng thật (§3b).

## 2. Bảng dungeon_id (từ `cdata_en.dungeon_rune.json`)

| dungeon_id | Zone (`typedesc`) | Tầng | Vé (`menpiao`) |
|---|---|---|---|
| 1-10 | Orochi | Lv.1-10 | 900003 (stamina) |
| 11 / 12 / 13 | Sougenbi | Greed / Anger / Foolery | 900039 / 900040 / 900041 |
| 101 | Orochi of the Maidens: Moans | Moan (tầng 11) | 900003 |
| 102 | Judgment | Judgment (tầng 12) | 900003 |
| 103 | Aether | Emptiness (tầng 13) | 900003 |
| 1001-1004 | Fallen Sun | Lv.1-3, Eclipse | 900003 |
| 2001-2003, 2005 | Sea of Eternity | Lv.1-4 | 900003 |
| 2004 | Sea of Eternity Tutorial | - | 900003 |

**Orochi Lv.3 = `dungeon_id: 3`.**

## 3. Bắt thật (2026-10-15, Orochi Lv.3)

Đọc RAM `player1.dungeon_reward` (chỉ đọc, không gửi gì lên server) trong lúc người chơi đánh trận bình thường:

```
09:30:40  dungeon_reward = {}
09:33:11  dungeon_reward = {"dungeon_rune": "6ad03b666051644c2b3a039d"}   <- lúc bấm Challenge
```

- `rewardId` là ObjectId 12 byte do server sinh. Timestamp trong ObjectId = 09:33:10 (+07), trùng lúc bấm Challenge.
- Phần machine/pid `6051644c2b` trùng với sid phiên (`6acf48e7 6051644c2b 36f87c`): cùng tiến trình server cấp.
- Mỗi trận một mã, dùng một lần. Server giữ bản đối chiếu.

Chưa bắt được (không nằm trong `dungeon_reward`): `copy_skin_id`, `heroes`, `buff`. Muốn có phải đọc RAM khi trận đang chạy (engine trận / `save_begin_battle_params`).

## 3b. Phần thưởng sinh ra khi nào

| Thời điểm | Client nhận gì | Bằng chứng |
|---|---|---|
| Bấm Challenge (`dungeon_rune_attack_return`) | chỉ `rewardId` (ObjectId), **không có nội dung thưởng** | RAM 09:33:11; code gọi `enterMainUi(..., {'allRewards': {}})` |
| Trong trận | không có gì về thưởng (`allRewards` rỗng) | code |
| Sau khi gửi `dungeon_rune_attack_result` | `dungeon_client_attack_return(reward)`: nội dung thưởng (ngự hồn, vàng...) | code: gán `sceneUserData['allRewards'] = reward` rồi mở `PanelReward` |

- **Chắc chắn:** server cấp `rewardId` trước trận. Client chỉ thấy nội dung thưởng sau khi báo kết quả. Chỉ số ngự hồn rơi ra (`rattr`) cũng do server sinh (`YUHUN_SUBSTAT_ROLL.md`).
- **Chưa chứng minh:** server roll nội dung thưởng lúc cấp `rewardId` (rồi giữ lại) hay lúc nhận `result`. Cả hai đều chạy trên server, client không phân biệt được.
- So sánh: Realm Raid (`lbs_onAttack` → `onAttackTargeterInfo(attackinfo, rewardId, reward)`) trả **cả nội dung thưởng ngay lúc bắt đầu đánh**, nên ở chế độ đó thưởng chắc chắn định trước. Soul Zone thì không trả nội dung lúc bắt đầu.
- Dù roll lúc nào, client không đổi được kết quả: không có tham số nào ảnh hưởng thưởng, và `rewardId` chỉ là khóa để server đối chiếu.

## 3c. Gọi thật bằng API (2026-10-15 09:53, Orochi Lv.3)

Chỉ gửi `dungeon_rune_attack`, **không gửi `result`**.

```
[>] dungeon_rune_attack {"dungeon_id": 3}
[<] onUpdateCurrency {"cid": 900003, "cnt": 18991, ...}        <- trừ stamina
[<] screen_click_log_by_strength_start {}                      <- server bảo client bắt đầu ghi toạ độ chạm
[<] yys_yinchui_update_task_cb {"task_sid": 187, "task_info": {"process": 158}}
[<] dungeon_rune_attack_return {"dungeon_id": 3, "rewardId": "6ad040406051644c2b3a0bfd", "copy_skin_id": 0}
```

- Server chấp nhận lời gọi từ client ngoài: trừ stamina, cấp `rewardId` mới, tiến độ nhiệm vụ tăng.
- `copy_skin_id` = 0 (skin cảnh mặc định).
- `screen_click_log_by_strength_start` → client gọi `ScreenRecordMgr.onStrengthDailyCost()`: mỗi lần tiêu stamina, game bắt đầu ghi toạ độ chạm để gửi lên (`log_screen_click`, xem `ANTICHEAT_FE_BE.md` §5). Client ngoài không gửi log này, nên phía server có dấu hiệu "tiêu stamina mà không có thao tác chạm".
- `freeze_update.frozen.num = 0`, `safety_lock {err:3}` như các lần resume trước.
- Trận bỏ dở: không gửi `result`, nên không có thưởng. Game client bị đá ra khi tool resume (mỗi avatar một kết nối).

**Lần 2 (10:00, game đã thoát):** resume lại bằng cùng authmsg (`session_live.json`) vẫn `RECONNECT_SUCCEEDED` dù game client không còn chạy.
- Gửi ngay sau `connect_reply` thì server **bỏ qua** lời gọi (chưa có entity). Phải đợi `become_player` rồi mới gửi (`--wait-ready 60`).
- Kết quả: stamina 18991 → **18979 (-12/lần)**, `yinchui` 158 → 170 (+12), `rewardId` mới `6ad041d36051644c2b3a0f39`, `copy_skin_id` 0, `freeze_update.num` = 0.
- Mỗi lần gọi là một trận mới, `rewardId` khác nhau. Không có thưởng vì không gửi `result`.

**Resume không cần game reconnect:** authmsg cũ (BSON loginInfo) dùng lại được sau khi thay `session` = sid hiện tại (đọc RAM `player1.login_session.sid`) và `versions` = `heroes_version#inventory_version#_last_process` (`read_versions.ps1`). `sauth_str` cũ vẫn được chấp nhận. Đây là phát hiện đáng báo cho team game: token resume không gắn với lần đăng nhập cụ thể.

## 4. Giới hạn khi gọi từ client ngoài

- **Server quyết định phần thưởng.** `rewardId` cấp trước trận. `iswin`, `rewardId`, `heroes`, `buff` đều được server đối chiếu (xem `ANTICHEAT_FE_BE.md` §7). Gửi `result` thắng mà server không có trận tương ứng sẽ bị từ chối/ghi nhận bất thường.
- **Mỗi avatar một kết nối.** `onmyoji_netclient.py` resume vào sẽ đá game ra. Trận mở bằng tool thì `rewardId` về tool, game không đánh được trận đó. Gọi `dungeon_rune_attack` từ tool sẽ trừ stamina thật.
- **Resume cần authmsg mới.** `GateClient.reconnect_data.bin_authmsg` chỉ có sau khi game tự reconnect ít nhất 1 lần. Lần thử 2026-10-14 bị `RECONNECT_FAILED` vì authmsg cũ, và `grab_session.ps1` báo `authmsg=none`.

## 5. Công cụ

| Việc | Lệnh |
|---|---|
| Tìm dict `dungeon_reward` trong RAM | `pyobj_dump.ps1 -Mode finddump -Name dungeon_reward -Depth 4 -All` (lấy entry kiểu `dict`) |
| Theo dõi thay đổi (chỉ đọc) | `watch_dungeon_reward.ps1 -Addr 0x<dict> -Seconds 1200 -Out <file.jsonl>` |
| Gửi RPC có params + bắt rewardId | `.venv-net/bin/python onmyoji_netclient.py --calls 'dungeon_rune_attack={"dungeon_id":3}' --listen 20 --dump data/rune_reply.jsonl --reward-out data/rune_rewards.jsonl` |

Chạy PowerShell từ WSL: `/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe -NoProfile -ExecutionPolicy Bypass -File '\\wsl.localhost\Ubuntu\home\viethx\onmyoji-bot\research\npk\<script>.ps1' ...`

Ghi chú:
- Địa chỉ dict đổi mỗi lần login. Chạy lại `finddump` trước khi watch.
- netclient phải chạy bằng `research/npk/.venv-net/bin/python` (python hệ thống thiếu `msgpack`).
- `session.json`, `authmsg.bson`, file watch nằm trong `research/` (gitignored, chứa token). Không commit.
