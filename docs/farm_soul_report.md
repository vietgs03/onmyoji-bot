# Farm Soul (Orochi/Moan) - Bao cao so lieu (2026-06-03)

Task `tasks/run.py farm_soul` chay LIVE tren game that (Steam PC, NeoX).
Verify thang = counter 'Rewards Preview X/500' TANG (dang tin nhat).
Log day du: `logs/farm_soul_stats.jsonl`. Phan tich: `tasks/analyze_soul.py`.

## Ket qua

### Run 30 lan (id 20260603T194328Z)
- 30/30 win = **100%**
- dur_s: mean 45.5s, median 42.7s, min 36.8, max 85.5, stdev 9.1
- counter 6 -> 36 (+30 dung)
- stamina 13400 -> 13000 (dung 400 = **13.3/vong**)
- tong 22.8 phut
- phan bo: tap trung 40-50s (24/30 vong), chi 1 outlier 85s.

### Run 60 lan (id 20260603T211526Z) - sau khi fix dialog Bonus
- 60/60 done, 54 win-flag = 90% (nhung counter 78->132 = **54 tran that**, 6 vong >160s la xu ly dialog/popup ngau nhien con tinh won qua counter)
- dur_s: mean 60.7s, median 48.7s, min 41.5, max 169.8, stdev 35.1
- counter 78 -> 132
- stamina 12500 -> 11900 (dung 600 = 10/vong, OCR ve cuoi loi nen thap)
- tong 60.7 phut
- 6 vong cham >160s: round 3,12,14,31,37,43 = gap dialog Bonus/popup -> loop xu ly (van win).

### Tong hop ~141 vong (gom ca run loi truoc fix)
- win_rate (counter-verified) ~94%, median dur ~45-48s.

## Bug da fix trong qua trinh chay (quan trong)
1. **Dialog Bonus 'Enable it again?'** pop moi khi click Challenge sau khi bonus tat 15'.
   - Truoc: loop tuong 'thay Challenge' = win -> ghi nham 9-17s/vong, counter DUNG YEN.
   - Fix: (a) detect bang OCR FULL anh (crop ROI fail), (b) Confirm hitbox @ **(660,410)** (KHONG phai 667,416), (c) win = counter TANG, (d) saw_battle KHONG tinh khi dialog hien.
2. **Popup 'Parade Privilege'** -> X dong @ **(975,135)**.
3. **Man reward dac biet 'New Skill/Tap to continue'** -> tap (576,620)+(576,340).
4. Timeout battle 75 -> 150s; retry tim Challenge 6 lan truoc khi ket luan het luot.

## Toa do chot (man Soul/Orochi)
- Explore @ (608,192), Soul icon @ (175,620)
- Zone Orochi @ (200,250), stage Moan @ (139,523)
- Challenge x12 @ (1063,580)
- Dialog Bonus Confirm @ (660,410), Cancel @ (483,416)
- Popup Parade X @ (975,135)
- Native: x5 @ ~(650,635), Auto @ (707,639) -- CHUA dung, de toi uu sau.

## Ket luan
Bot farm Soul ON DINH, tu dong xu ly dialog/popup ngau nhien, verify bang counter.
~45-50s/vong khi khong gap dialog. Stamina ~13/vong (cost Challenge x12).
