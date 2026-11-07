"""Test gia thuyet: nut Bonus chi mo khi window FOREGROUND.
restore window -> politeclick swirl -> doc man. Ghi logs/_bt.log."""
import sys, time, cv2
sys.path.insert(0, '/home/viethx/onmyoji-bot/automation')
sys.path.insert(0, '/home/viethx/onmyoji-bot/scripts')
sys.path.insert(0, '/home/viethx/onmyoji-bot/ml')
out = open('/home/viethx/onmyoji-bot/logs/_bt.log', 'w')
def L(s):
    out.write(s + '\n'); out.flush()
from agent import Agent
a = Agent()
L('info=' + str(a.c.info()))
# restore + bring window onto screen
try:
    L('restore=' + str(a.c._cmd('restore')))
except Exception as e:
    L('restore err ' + str(e))
time.sleep(1)
L('info2=' + str(a.c.info()))
r = a.read()
base = set(t for t,_,_ in r.words)
L(f'before: hasBonus-region, n_words={len(r.words)}')
# thu nhieu diem quanh swirl
for (x, y) in [(394, 49), (397, 66), (405, 52), (388, 58)]:
    a.c.politeclick(x, y); time.sleep(2.2)
    r2 = a.read()
    newt = [t for t,_,_ in r2.words if t not in base]
    L(f'politeclick({x},{y}) -> n_words={len(r2.words)} new={newt[:8]}')
    # dau hieu popup bonus mo: chu Bonus to / Extra / Activate / Buff / so %
    if any(k.lower() in ' '.join(newt).lower() for k in ['extra','activate','buff','bonus','%','enable','off','on ']):
        L('  >> CO THE LA POPUP BONUS')
        cv2.imwrite('/home/viethx/onmyoji-bot/logs/_bonus_popup.png', r2.img)
        break
    base = set(t for t,_,_ in r2.words)  # cap nhat
cv2.imwrite('/home/viethx/onmyoji-bot/logs/_bt_final.png', a.shot())
import os; os._exit(0)
