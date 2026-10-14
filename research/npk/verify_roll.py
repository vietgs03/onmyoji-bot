# Chay CHINH ham allitem_randEquipAttr da decompile voi bang that, kiem phan phoi
import json, sys, types, collections, random
src = open('/work/src/com/utils/helpers.py').read()
i = src.index('def allitem_randEquipAttr'); j = src.index('\n# line', i)
fn_src = src[i:j]
data = json.load(open('/work/cdata/cdata_en.equip_attr.json'))['data']
class P(object): pass
DATA_EQUIP_ATTR = P(); DATA_EQUIP_ATTR.data = dict((int(k), v) for k, v in data.items())
mod = types.ModuleType('DynamicConfigData'); mod.DATA_EQUIP_ATTR = DATA_EQUIP_ATTR
sys.modules['DynamicConfigData'] = mod
ns = {}; exec(fn_src, ns); f = ns['allitem_randEquipAttr']
random.seed(1); N = 60000
kind = collections.Counter(); dup = 0; lo = 9; hi = 0
for _ in range(N):
    r = f(6, 4, 0)['rattr']
    names = [a for a, v in r]
    if len(set(names)) != 4: dup += 1
    for a, v in r: kind[a] += 1; lo = min(lo, v); hi = max(hi, v)
tot = sum(kind.values())
print 'rolls', tot, 'dup_sets', dup, 'coef range %.4f..%.4f' % (lo, hi)
for k, c in sorted(kind.items()): print '  %-22s %.4f' % (k, float(c) / tot)
r = f(6, 1, 0)['rattr']; print 'single roll sample', r
