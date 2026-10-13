# Onmyoji Bot - State / Context nén (cap nhat: 2026-06-03)

Muc dich: tranh phai doc lai session khong lo (gay 413 Payload Too Large).
Doc file nay de nam context nhanh thay vi load lich su chat.

## Setup
- Game: 陰陽師 Onmyoji (Global/EN), **Steam PC window** (KHONG emulator), engine NeoX, class `Win32Window`.
- Agent chay WSL/Linux, dieu khien Windows game qua persistent PowerShell server `ps/server.ps1` + Win32 API.
- Client: `scripts/control_client.py` (Controller): `bgshot()`, `bgclick(x,y)`, `bgdrag/senddrag` (scroll KHONG chiem chuot - dung SendMessage, NeoX nhan; PostMessage KHONG nhan).
- Venv: `.venv/bin/python`. OCR: `ml/ocr.py` `ocr_words(img, roi=None, min_conf=40)` -> [(text,(x,y,w,h),conf)]. Luu y: crop ROI nho lam OCR KEM -> nen OCR full anh roi loc bbox/regex.
- Agent: `automation/agent.py` (shot/read/click/tap_text/wait_stable/drag/goto). Nav graph: `automation/screen_graph` + world.json.

## Breakthroughs (session truoc)
1. Click KHONG chiem chuot (SendMessage).
2. Benchmark honest random (chong overfit) - `automation/maze_bench.py`.
3. Fix toa do exit HOME->exploration/town (test F trong test_screen_graph.py).
4. Fix currency localizer HOME: gold(vang)/jade(hong ngoc)/shushi - `automation/hypothesis_test.py`.

## Task farm_soul (MOI - da verify LIVE)
File: `tasks/run.py` -> `farm_soul(agent, stage="Moan", zone="Orochi", times=N, dry=True)`.
- Nav: HOME -> Explore(608,192) -> Soul icon(175,620). Verify `on_soul`: header 'soul' (x<320,y<90) + 'challenge' co trong body.
- Chon zone theo VI TRI panel (OCR ten zone bi xoay): _ZONE_X dict. Orochi @ x=200,y=250.
- Tim stage: `_find_stage` scroll list cot trai (drag KHONG chiem chuot), match substring OCR.
- Action loop: retry 6 lan tim Challenge -> click Challenge(1063,580) -> poll 120s cho 'Challenge' tro lai (=ve man stage=win) -> tap Reward/Confirm/Continue/center.
- GHI SO LIEU -> `logs/farm_soul_stats.jsonl`: moi vong {round,won,dur_s,counter}; summary {win_rate,avg_dur_s,stamina_used,...}.
  - counter = 'Rewards Preview X/500' (OCR full, regex `\d+/500`).
  - stamina = shushi top-bar (bbox x>820,y<90, dang NN.NK).

## KET QUA DO DUOC
- **30 lan**: 30/30 win (100%), avg 45.5s/vong, stamina dung 400 (~13.3/vong), counter 6->36. Tong 22.75 phut.
- **100 lan**: dang chay (run id xem logs/farm_soul_stats.jsonl). Du kien ~75 phut.

## Lan tiep theo / TODO nghien cuu
- Sau 100 lan: phan tich phan bo dur_s (battle nhanh/cham), ti le timeout, stamina/vong chinh xac.
- Map tier-2 (trong realm_raid/battle/challenge) - world.json data DUNG o muc menu, chua co anh ben trong.
- Mo rong farm_soul cho zone/stage khac (Sougenbi/Himiko/Sea of Eternity).
- Auto-repeat native cua game (nut 'x5'/'Auto' o man Soul) - co the dung thay vong lap thu cong.

## Commit gan nhat (2026-10-13: enhance_soul + soul_lines + tests)
- feat(soul): task enhance_soul (loc som) + ml/soul_lines.py + 11 test offline

## Commit truoc do
- 84040a0 feat(soul): task farm_soul + GHI SO LIEU
- (fix) tang timeout 75->120s + retry 6 lan tim Challenge

## Nghien cuu: native multi-battle (chua thu - tranh dung khi 100-run dang chay)
Man Soul co cac nut tang toc native (toa do tu /tmp/after_soul.png):
- 'x5' @ ~(650,635): danh 5 tran 1 lan bam (multi-battle native).
- 'Auto' @ (707,639): tu dong lap.
- 'Line-up' @ (595,640): doi team nhanh.
- 'Challenge x12' @ (1063,580): x12 = cost 12 stamina/lan? (nhung do stamina_used 30 lan = 400 -> ~13.3/vong, gan dung 12-13).
=> NEN thu dung 'x5' thay vong lap Python: it screenshot/OCR hon, nhanh hon. Verify counter +5 sau 1 lan.

## CAP NHAT 2026-06-03 (sau 30+60 lan + fix dialog)
- DA chay 30 lan (100% win) + 60 lan (counter 78->132 = 54 tran that). Bao cao: docs/farm_soul_report.md.
- BUG LON da fix: dialog Bonus 'Enable it again?' -> Confirm hitbox @ (660,410) [KHONG 667,416]; detect OCR FULL anh; win = counter TANG.
- Popup Parade X @ (975,135). Reward dac biet -> tap (576,620)+(576,340).
- Toa do chot: xem docs/farm_soul_report.md.
- TODO: dung native x5(@650,635)/Auto(@707,639) de nhanh hon + bot dialog. Mo rong zone/stage khac.

## CAP NHAT 2026-10-13 (task enhance_soul - cuong hoa Ngu Hon theo chien thuat loc som)
Doi khi game KHONG chay -> lam phan verify DUOC OFFLINE, cam game vao la chay.

- `ml/soul_lines.py` (MOI): doc DONG PHU cua soul tu OCR words -> `SoulState.stats`
  ({'spd':2.4,'crit':3%,...}). Ghep <ten dong> <gia tri> theo HANG (loc dy <= 20px
  truoc, roi uu tien so co '%'), co bang alias ten dong EN -> key chuan.
- `tasks/enhance_soul.py` (MOI): task `enhance_soul`, chien thuat loc som:
  cuong hoa -> OCR lai -> `_stats_diff` biet roll vao dong nao -> trung dich thi di
  tiep, truot thi DUNG giu lam thuc an. `_decide()` la phan logic thuan, test rieng.
  Ghi tung lan roll -> `logs/enhance_soul_stats.jsonl` (do TI LE THAT vs 1/4 cua wiki).
  Co `_ocr_words()` tach ra de monkeypatch khi test. dry=True (mac dinh) KHONG bam gi.
- Dang ky trong `tasks/run.py`: `python tasks/run.py enhance_soul target=spd times=5 --live`.
- `tests_arch/test_soul_enhance.py` (MOI): 11 test OFFLINE (khong can game/OCR):
  parse dong phu, khong gan lan so giua cac hang, logic quyet dinh, diff, mo phong
  1/4 (cat som 74%), va **E2E voi FakeAgent** (dry khong bam / live co bam + ghi log).
  => `python tests_arch/test_soul_enhance.py` -> "OK - tat ca test soul enhance pass".

### CHUA VERIFY (can game chay)
- Toa do nut trong `tasks/enhance_soul.py` -> `ANCHORS` la GIA THUYET suy tu layout
  res.npk (entry 35994.json panel chi tiet / 26763.json panel cuong hoa). Phai chay
  `python tasks/run.py enhance_soul --dry` khi game mo de doi chieu, roi moi --live.
- Ten dong phu EN that tren client: bang alias trong ml/soul_lines.py can doi chieu
  bang anh that (hien suy tu ten lore: Attack Bonus / Speed / Crit Rate / Effect Hit...).
- Chua lam: tu dong CHON soul tu list (mo chi tiet tung con) - hien task gia dinh dang
  o man chi tiet 1 soul; va nut danh dau bo (弃置) chua tu bam.
