# Full API flow: token (RAM) → gọi RPC gate Onmyoji

Tài liệu toàn bộ chuỗi, từ lấy thông tin phiên tới gửi một RPC và nhận trả lời.
Tool: `research/npk/onmyoji_netclient.py` (chạy bằng `research/npk/.venv-net/bin/python`).

## 0. Cần gì

| Thứ | Lấy từ | Script |
|---|---|---|
| gate_ip, gate_port | `Globals.currentGateAddr` (RAM) | `grab_session.ps1` |
| entityid (12B ObjectId) | `player1.id` | `grab_session.ps1` |
| deviceid (fulluid) | `GateClient.fulluid` | `grab_session.ps1` |
| loginpubkey (RSA) | `Globals.loginpubkey` | `grab_session.ps1` |
| authmsg (BSON loginInfo) | `GateClient.reconnect_data.bin_authmsg`, hoặc authmsg cũ + sửa | `grab_session.ps1` / tự sửa |
| sid hiện tại | `player1.login_session.sid` | `read_versions.ps1` |
| versions | `heroes_version#inventory_version#_last_process` | `read_versions.ps1` |

Các giá trị ghi ra `data/session.json` + `data/authmsg.bson` (gitignored, chứa token).

## 1. Transport (lib/mobilerpc, GateClient)

```
frame  = u32le(len(pb)+2) | u16le(method_index) | protobuf_body
gui    : RC4(zlib_sync_flush(frame))      # sau connect_server moi bat zlib
nhan   : zlib_decompress(RC4(data))       # RC4 & zlib la stream lien tuc ca 2 chieu
```

- `method_index` khi **gửi** = chỉ số method trong service `IGateService` (`SVC_IDX[name]`).
- Khi **nhận**, frame là method của `IGateClient` (`GATE_CLI.methods[idx]`).
- Proto schema: `data/proto/common.proto.desc`, `client_gate.proto.desc` (FileDescriptorProto lấy từ RAM).

## 2. Handshake (RSA + RC4)

```
1. seed_request(Void)              -> seed_reply(SessionSeed{seed})
2. tao SessionKey:
     session_key = sha1(random 32B)         # khoa RC4
     random_padding_header/tail = random 32B
     seed = seed tu buoc 1
   EncryptString.encryptstr = RSA-OAEP(loginpubkey, SessionKey.SerializeToString())
   gui session_key(EncryptString)
   -> ngay sau khi gui: bat RC4 ca enc va dec bang session_key
3. nhan session_key_ok   (luc nay moi frame deu da qua RC4)
```

## 3. Resume phiên (vào lại avatar)

```
connect_server(ConnectServerRequest{
    type = RE_CONNECTION (1),
    deviceid = <fulluid>.encode(),
    entityid = <12B ObjectId>,
    authmsg  = <BSON loginInfo>})
# ngay sau connect_server: bat zlib (compressobj + decompressobj)
-> nhan connect_reply(type):  2 = RECONNECT_SUCCEEDED
-> roi server day loat dong bo: create_entity (bdict player 730 keys), send_inventory_by_block,
   become_player, safety_lock, dynamic_hotfix, freeze_update, ...
```

authmsg = BSON của `loginInfo` (UserInfoMgr.getLoginInfo + device + sdk). **Tái dùng authmsg cũ**: chỉ cần sửa `session` = sid hiện tại, `versions` = chuỗi mới (đọc RAM). `sauth_str`, MAC, udid giữ nguyên vẫn được chấp nhận.

## 4. Gọi RPC entity (gameplay)

```
entity_message(EntityMessage{
    id = <entityid 12B>,
    method = Md5OrIndex{ md5 = md5(tên_method) },   # hoac index neu da biet
    parameters = msgpack(dict, use_bin_type=True)})
```

- Tên → md5: `hashlib.md5(b"dungeon_rune_attack").digest()`. Tự lưu map md5→tên để dịch reply.
- Server trả reply cũng là `entity_message`, method là `<tên>_cb` / `<tên>_return` / tên khác; ObjectId trong msgpack là ExtType code 42.
- Chỉ gửi được **sau khi nhận `become_player`** (chưa có entity thì server bỏ qua) → netclient có `--wait-ready`.

## 5. Lệnh chạy sẵn

```bash
cd research/npk

# Bắt đầu 1 trận Rune Orochi Lv.3 (chi mo tran, KHONG gui result)
.venv-net/bin/python onmyoji_netclient.py \
  --session data/session_live.json \
  --calls 'dungeon_rune_attack={"dungeon_id":3}' \
  --wait-ready 60 --listen 20 \
  --dump data/rune_reply.jsonl --reward-out data/rune_rewards.jsonl

# Chi doc trang thai (khong goi gi) -> xem day_limit_pc, currency trong create_entity
.venv-net/bin/python onmyoji_netclient.py --session data/session_live.json \
  --calls '' --listen 12 --dump data/entity_snapshot.jsonl --only "@@none@@"
```

`--calls` nhận `method` hoặc `method={json}`. `--reward-out` tự bắt `rewardId` từ `*_attack_return`.

## 6. dungeon_rune_attack_result (payload đầy đủ)

Chỉ dùng cho **tầng 1-10** (`DungeonMember.dungeon_rune_attack_result` return sớm nếu `dungeon_id > 10`).

```python
entity_call(entityid, "dungeon_rune_attack_result", {
    "dungeon_id": 3,
    "result": {"iswin": True, "rewardId": <từ dungeon_rune_attack_return>},
    "heroes": [<fightHeroUids>],     # 5-7 uid, doc RAM: localBattleEngine.controllers[0].fightHeroUids
    "buff":   {}                      # getSkinBuffList() = battle_ext_buff[camp1], thuong rong
})
```

- `rewardId`: lấy từ reply `dungeon_rune_attack_return` của **cùng** trận (dùng 1 lần).
- `heroes`: `fightHeroUids` thật chỉ tồn tại **trong lúc trận diễn ra** (sau trận `localBattleEngine` = None). Dùng `watch_battle_result.ps1` để bắt. Quan sát thực tế: 7 uid (gồm cả thú cưng/áp trận), không chỉ 5.
- `buff`: `OrderedDict`, rỗng nếu không bật skin buff.
- Bản EN: `requestCheckBattle` (`battle_check`) `return` ngay, nên đây là dữ liệu kết quả duy nhất client gửi. Xem `TESTING_REPORT.md §3.3`.

## Lưu ý an toàn

- Gate trong `session.json` (`34.48.52.40`) là **production public**. Gửi `result` tự dựng = báo thắng trận không đánh trên server thật → rủi ro khóa tài khoản. Chỉ chạy luồng `result` trên **staging/QA** do team game cấp.
- Mỗi avatar một kết nối: resume bằng tool sẽ **đá game client ra**.
- `dungeon_rune_attack` qua tool **trừ stamina thật**, không gửi `result` thì không có thưởng, không tính lượt ngày.
