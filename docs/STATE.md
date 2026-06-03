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

## Commit gan nhat
- 84040a0 feat(soul): task farm_soul + GHI SO LIEU
- (fix) tang timeout 75->120s + retry 6 lan tim Challenge
