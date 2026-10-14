# -*- coding: utf-8 -*-
"""Python2: khop code object NetEase (stdlib) voi CPython 2.7 goc -> suy ra bang opcode.

Input : /work/stdlib_codes.jsonl (tu pyobj_dump.ps1 -Mode codes, loc lib\\*)
Output: /work/opmap_learned.json  {ne_opcode: {std_name: count}}
        + in thong ke khop.
Ghep cap: (file, name, firstlineno) -> so sanh tung lenh khi so luong lenh bang nhau.
"""
import json, base64, os, sys, dis, opcode, collections, types

LIB = os.path.dirname(os.__file__)

def std_codes(path):
    src = open(path).read()
    try: co = compile(src, path, 'exec')
    except Exception: return {}
    res = {}
    def walk(c):
        res.setdefault((c.co_name, c.co_firstlineno), []).append(c)
        for k in c.co_consts:
            if isinstance(k, types.CodeType): walk(k)
    walk(co); return res

def insns_std(code):
    out = []; i = 0; n = len(code)
    while i < n:
        op = ord(code[i]); i += 1; arg = None
        if op >= opcode.HAVE_ARGUMENT:
            arg = ord(code[i]) | (ord(code[i+1]) << 8); i += 2
            if op == opcode.EXTENDED_ARG:
                pass
        out.append((op, arg))
    return out

def insns_ne(code, argset):
    out = []; i = 0; n = len(code)
    while i < n:
        op = ord(code[i]); i += 1; arg = None
        if op in argset:
            if i + 2 > n: return None
            arg = ord(code[i]) | (ord(code[i+1]) << 8); i += 2
        out.append((op, arg))
    return out

ne = collections.defaultdict(list)
for l in open('/work/stdlib_codes.jsonl'):
    d = json.loads(l)
    f = d['file'].replace('\\', '/')[4:]
    d['bcode'] = base64.b64decode(d['code'])
    ne[f].append(d)

cache = {}
def get_std(f):
    if f not in cache:
        p = os.path.join(LIB, f)
        cache[f] = std_codes(p) if os.path.exists(p) else {}
    return cache[f]

def firstline(d):
    return d['fl']

# Pha 1: dung do dai bytecode de suy ra opcode nao co arg.
# Voi cap khop (cung varnames), dem so lenh std; bytecode NE co cung tong do dai?
pairs = []
for f, lst in ne.items():
    std = get_std(f)
    for d in lst:
        cands = std.get((d['name'], d['fl']), [])
        for c in cands:
            if list(c.co_varnames) == d['varnames'] and list(c.co_names) == d['names']:
                pairs.append((d, c)); break
print >>sys.stderr, 'pairs', len(pairs)

same_len = [(d, c) for d, c in pairs if len(d['bcode']) == len(c.co_code)]
print >>sys.stderr, 'same length', len(same_len)

# Pha 2: voi cap cung do dai, align byte-by-byte theo cau truc lenh std
votes = collections.defaultdict(collections.Counter)
argmatch = collections.defaultdict(collections.Counter)
for d, c in same_len:
    ins = insns_std(c.co_code); pos = 0; b = d['bcode']
    for op, arg in ins:
        neop = ord(b[pos])
        votes[neop][opcode.opname[op]] += 1
        if arg is not None:
            nearg = ord(b[pos+1]) | (ord(b[pos+2]) << 8)
            argmatch[opcode.opname[op]]['same' if nearg == arg else 'diff'] += 1
            pos += 3
        else:
            pos += 1

res = {}
for neop in sorted(votes):
    top = votes[neop].most_common(3)
    res[neop] = dict(votes[neop])
    print '0x%02X %-22s %s' % (neop, top[0][0], top[1:] if len(top) > 1 else '')
print
for k, v in sorted(argmatch.items()):
    if v['diff']: print 'ARG-DIFF', k, dict(v)
json.dump({'votes': res, 'argmatch': {k: dict(v) for k, v in argmatch.items()}}, open('/work/opmap_learned.json', 'w'), indent=1)
