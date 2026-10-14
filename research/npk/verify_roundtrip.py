# Round-trip: source decompile cua lib\*.py -> compile -> so opcode-sequence voi CPython goc cua cung ham
import os, re, types, opcode, collections
LIB = os.path.dirname(os.__file__)
def ops(co):
    b = co.co_code; i = 0; out = []
    while i < len(b):
        op = ord(b[i]); out.append(opcode.opname[op]); i += 3 if op >= 90 else 1
    return out
def collect(co, res):
    res[(co.co_name, co.co_firstlineno)] = co
    for k in co.co_consts:
        if isinstance(k, types.CodeType): collect(k, res)
tot = same = cfail = 0
for root, ds, fs in os.walk('/work/src/lib'):
    for f in fs:
        if not f.endswith('.py'): continue
        rel = os.path.relpath(os.path.join(root, f), '/work/src/lib')
        orig = os.path.join(LIB, rel)
        if not os.path.exists(orig): continue
        std = {}
        try: collect(compile(open(orig).read(), orig, 'exec'), std)
        except Exception: continue
        text = open(os.path.join(root, f)).read()
        for m in re.finditer(r'# line (\d+)  @\S+\n(def (\w+)\(.*?)(?=\n# line |\Z)', text, re.S):
            fl, body, name = int(m.group(1)), m.group(2), m.group(3)
            o = std.get((name, fl))
            if o is None or 'DECOMPILE FAILED' in body: continue
            tot += 1
            try: c = compile(body, 'x', 'exec')
            except SyntaxError: cfail += 1; continue
            fc = [k for k in c.co_consts if isinstance(k, types.CodeType)]
            if fc and ops(fc[0]) == ops(o): same += 1
print 'stdlib funcs checked', tot, 'identical opcode seq', same, '(%.1f%%)' % (100.0 * same / max(1, tot)), 'syntax-fail', cfail
