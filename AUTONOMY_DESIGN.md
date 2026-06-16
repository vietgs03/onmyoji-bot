# AUTONOMY DESIGN - Tu nhan dien -> TU CHOI (4 tang)

> Trang thai truoc: he thong co MAT (nhan dien) + BAN DO (graph) + TRI THUC (vector DB)
> nhung click thu cong. Doc nay thiet ke 4 tang de bot TU CHOI 1 mode tron ven +
> tu len lich daily. Theo Clean Architecture (domain -> application -> adapter -> interface).

## Nguyen tac (giu kien truc sach)
- Entities/Ports moi nam o `domain/`. Logic dieu phoi o `application/use_cases.py`.
- Adapter cu the o `adapters/`. Wiring o `interface/container.py`. MCP tool o `interface/mcp_server.py`.
- KHONG hardcode flow game (triet ly self-learning): moi quyet dinh dua tren
  world graph + vector DB + Observation da hoc. Task = du lieu (TaskSpec), KHONG code cung.
- Moi tang co TEST o `tests_arch/` (FakeEye, khong can game).

---

## TANG 1: Outcome Verification (lam truoc - cac tang khac phu thuoc)
**Muc tieu:** sau 1 action/battle, biet KET QUA (thang/thua/loi/loading) de dong vong feedback.

**Entity moi (`domain/entities.py`):**
```
class Outcome(str, Enum): VICTORY, DEFEAT, IN_BATTLE, LOADING, UNKNOWN, NO_RESOURCE
@dataclass Verdict: outcome: Outcome; confidence: float; detail: str; resources: Resources
```

**Cach nhan dien (khong hardcode, dua landmark):**
- Them page template live cho man Victory (chu "Victory"/防御成功) + Defeat (失败).
- `VerifyUseCase.classify(obs) -> Verdict`: uu tien page detector (page_victory/page_defeat),
  fallback heuristic (mau vang reward / chu do). Confidence theo score.
- Doc resource delta (AP truoc/sau) de biet da ton AP = da danh that.

**MCP:** `verify_outcome()` -> Verdict dict.
**Test:** FakeEye tra obs co page=page_victory -> Verdict.VICTORY.

---

## TANG 2: Task Executor (gia tri cao nhat) - "lam tron 1 viec"
**Muc tieu:** `do_task(spec)` tu dieu huong + lap N lan + verify + dung dung luc.

**Entity (`domain/entities.py`):**
```
@dataclass TaskSpec:
    goal_screen: str        # man dich (vd 'SoulBattle')
    action: str             # 'challenge' | 'collect' | 'navigate'
    repeat: int = 1         # so lan lap (vd farm 10 tran)
    stop_on: tuple[Outcome] # dung khi gap (vd NO_RESOURCE)
    max_steps: int = 50     # tran an toan
@dataclass TaskResult: ok, done_count, stopped_reason, verdicts: list[Verdict]
```

**`ExecuteTaskUseCase` (state machine, KHONG hardcode toa do):**
```
1. NAVIGATE: goto(goal_screen) qua world graph bfs_path (da co).
   - neu khong co duong -> tra loi 'chua map duong, can explore'.
2. LOOP repeat lan:
   a. tim element hanh dong (vd 'Challenge') tu verified_elements cua man.
   b. click_at(element) -> _wait_settle.
   c. neu action='challenge': xu ly chuoi pre-battle (Ready) -> in-battle (Auto)
      -> cho VerifyUseCase ra VICTORY/DEFEAT (poll dhash on dinh + page).
   d. ghi Verdict. neu outcome in stop_on -> dung.
   e. dismiss man ket qua (click reward/close) -> ve man goal.
3. tra TaskResult.
```
**Quan trong (senior):** moi buoc dua tren DU LIEU (verified_elements + page), khong
toa do cung. Neu thieu element -> bao 'can hoc element X' (self-learning loop).

**MCP:** `do_task(goal_screen, action, repeat, ...)` -> TaskResult.
**Test:** FakeEye scripted (navigate -> challenge -> victory x3) -> done_count=3.

---

## TANG 3: Daily Routine Planner - "lam gi moi ngay"
**Muc tieu:** tu vector DB (man nao farm gi) + trang thai -> sinh chuoi TaskSpec hop ly.

**Du lieu (`knowledge/daily_plan.json` - data, KHONG code cung):**
```
[{"screen":"SpiritVenture","action":"challenge","repeat":2,"priority":1,"why":"farm EXP/coin daily"},
 {"screen":"Soul","action":"challenge","repeat":10,"priority":2,"why":"farm ngoc hon",
  "stop_on":["NO_RESOURCE"]}, ...]
```

**`PlanDailyUseCase`:**
- doc daily_plan.json + loc theo: man da map (co bfs_path tu HOME) + con luot (neu doc duoc).
- sap theo priority. Tra list TaskSpec.
- `ask_kb` bo tro: neu plan thieu, hoi vector DB 'man nao farm <X>'.

**MCP:** `plan_daily()` -> list TaskSpec; `run_daily()` -> chay tuan tu qua ExecuteTask.
**Test:** plan tu json gia -> dung thu tu priority + bo man chua map.

---

## TANG 4: Resource-aware decisions - "quyet dinh thong minh"
**Muc tieu:** dung Observation.resources (gold/ap/jade da co) de quyet dinh.

**`ResourcePolicy` (domain, thuan logic):**
```
- can_afford(spec, resources) -> bool   (vd Soul battle can AP>=6)
- should_stop(resources) -> Optional[Outcome.NO_RESOURCE]
- cost cua moi action: data trong daily_plan ("ap_cost":6).
```
**Tich hop:** ExecuteTaskUseCase goi ResourcePolicy truoc moi vong lap -> het AP -> stop_on NO_RESOURCE.
**Test:** resources AP=3, cost=6 -> can_afford False -> task dung voi NO_RESOURCE.

---

## Thu tu trien khai (phu thuoc)
1. **Outcome/Verdict entity + VerifyUseCase** (tang 1) - nen tang feedback.
2. **TaskSpec/TaskResult + ExecuteTaskUseCase** (tang 2) - dung tang 1.
3. **ResourcePolicy** (tang 4) - tich hop vao tang 2.
4. **PlanDailyUseCase + run_daily** (tang 3) - dung tang 2+4.
Moi buoc: entity -> usecase -> adapter (neu can) -> container -> MCP -> test -> commit.

## Rui ro + giam thieu
- **Man Victory/Defeat chua co template:** can chup live + add_live_page (da co tool). Lam khi co game.
- **Battle lau/treo:** max_steps + timeout moi vong. _wait_settle da co.
- **Popup la giua chung (level up, reward bat ngo):** ExecuteTask co buoc 'dismiss unknown'
  (tim nut close/tap-empty) truoc khi tiep.
- **Khong lam hong graph:** ExecuteTask CHI dieu huong (click da hoc), khong learn_screen tu dong.
