# RUNTIME MODEL - Vong doi tu choi (chay dung khi game mo)

> Game chua mo -> thiet ke mo hinh chay DUNG + verify OFFLINE truoc. Toi chi viec cam vao.
> Doc nay: (1) vong doi runtime, (2) xu ly loi/edge-case, (3) FakeGame de test khong can game.

## 1. Vong doi tu choi (autonomy loop)

```
START
 |
 v
[Restart/GotoMain]  <- dam bao o HOME (man goc) truoc khi bat dau
 |
 v
[plan_daily]  <- doc daily_plan.json + loc man da map + sap priority -> list TaskSpec
 |
 v
for each TaskSpec:
 |
 +-> [navigate] goto(goal_screen) qua bfs_path
 |     |- that bai (chua map duong) -> SKIP task, log, task sau
 |     |- popup chan duong -> dismiss roi thu lai
 |
 +-> loop repeat lan:
 |     |- [resource check] het AP/luot -> NO_RESOURCE -> next task
 |     |- [click element] (Challenge/Enter...) -> _wait_settle
 |     |- [run_battle] Ready -> Auto -> WATCH ket qua (victory/defeat)
 |     |     |- timeout -> coi nhu UNKNOWN, dismiss, next
 |     |- [dismiss] tap toi khi ve goal_screen
 |     |- ghi Verdict (wins/losses)
 |
 v
[report] tong ket: moi task done/wins/losses/stopped_reason
 |
 v
END (hoac sleep toi lan daily sau)
```

## 2. Xu ly loi / edge-case (QUAN TRONG - phai dung khi game that)

| Tinh huong | Xu ly |
|---|---|
| Khong map duong toi man | SKIP task + log "can explore", KHONG crash |
| Chua hoc element hanh dong | SKIP + log "can learn_element", KHONG doan toa do |
| Popup la chan giua (level up, reward bat ngo) | dismiss: tim nut close/X -> neu khong, tap goc an toan -> verify ve man cu |
| Battle treo (khong ra ket qua) | timeout max_steps*2s -> UNKNOWN -> dismiss -> next (khong ket vo han) |
| Man LA hoan toan (screen_confirmed=False) | DUNG task, bao agent NHIN (khong hanh dong mu) |
| Het AP giua chung | NO_RESOURCE -> dung task do, sang task khac |
| Game disconnect/crash | observe tra alive=False -> dung toan bo, bao loi |
| dhash troi (man dong) | canonical_state neo theo page (da co) |

**Nguyen tac an toan (fail-safe):**
- KHONG BAO GIO hardcode toa do / doan mu. Thieu du lieu -> DUNG + bao ro.
- Moi action co the revert (tranh hanh dong khong the hoan tac: mua bang tien that, xoa).
- Co "panic button": neu N action lien tiep khong doi man -> dung (tranh kẹt loop).

## 3. FakeGame - mo phong game de TEST OFFLINE (verify mo hinh dung)

**Y tuong:** FakeGame = state machine mo phong luong game that. Cam vao thay FakeEye
-> chay do_task/run_daily END-TO-END khong can game. Verify mo hinh DUNG ngay bay gio.

**Cau truc:**
```
FakeGame(graph): doc 1 dinh nghia man + transition (giong world thu nho)
  - current_screen, resources (AP...)
  - observe(): tra Observation theo current_screen (page, dhash, loading gia)
  - act(click): tim element tai (x,y) -> chuyen current_screen theo transition
    + mo phong battle: SoulBattle click Challenge -> SoulPreBattle -> Ready ->
      SoulInBattle (loading vai frame) -> page_victory -> ve SoulBattle
    + tru AP moi battle
  - mo phong loading frame (vai lan observe dau tra loading=True)
```

**Kich ban test (verify mo hinh):**
1. do_task(SoulBattle, repeat=3) -> navigate + 3 battle + verify VICTORY -> done 3, wins 3.
2. AP can -> NO_RESOURCE dung dung luc.
3. run_daily -> chay het plan, bao cao tung task.
4. Popup chan -> dismiss -> tiep.
5. Battle treo -> timeout -> UNKNOWN -> khong ket.

-> Neu FakeGame pass HET, mo hinh DUNG. Toi game mo chi can chup Victory/Defeat template.
