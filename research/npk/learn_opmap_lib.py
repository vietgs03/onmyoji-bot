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

