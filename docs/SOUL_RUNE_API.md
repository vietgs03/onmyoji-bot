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
