# -*- coding: utf-8 -*-
"""decompile_all.py (Python 2.7 + uncompyle6) - Dich toan bo code object NetEase -> Python source.

Pipeline:
  codes.jsonl (pyobj_dump.ps1 -Mode codes)
   -> remap opcode NetEase -> CPython 2.7 (opmap_final2.json, hoc tu stdlib)
   -> dung lai types.CodeType (consts long nhau tro toi code object khac qua dia chi)
   -> uncompyle6.code_deparse -> source
Output: <out>/<file path>.py  (moi file gom cac ham top-level, sap theo firstlineno)
        <out>/_stats.json

Ghi chu: code '<module>' va than class da bi giai phong sau khi import nen khong co;
ham nam trong class duoc xuat duoi dang ham top-level (giu self).
"""
import json, base64, os, sys, types, opcode, collections, re, traceback, io
from multiprocessing import Pool

WORK = '/work'
OUT = sys.argv[1] if len(sys.argv) > 1 else '/work/src'
M = {int(k): opcode.opmap[v] for k, v in json.load(open(os.path.join(WORK, 'opmap_final2.json'))).items()}

def remap(b):
    out = bytearray(); i = 0; n = len(b); unknown = 0
    while i < n:
        op = ord(b[i])
        std = M.get(op)
        if std is None: unknown += 1; std = opcode.opmap['NOP']
        out.append(std)
        if op >= 90:
            out += b[i+1:i+3]; i += 3
        else:
            i += 1
    return bytes(out), unknown

CODES = {}
def load():
    for l in open(os.path.join(WORK, 'codes.jsonl')):
        d = json.loads(l)
        CODES[d['a']] = d

def cval(c, depth=0):
    t = c[0]
    if t == 'N': return None
    if t == 'T': return True
    if t == 'F': return False
    if t == 'i': return c[1]
    if t == 'l': return long(c[1])
    if t == 'f': return float(c[1])
    if t == 'j': return complex(float(c[1]), float(c[2]))
    if t == 's': return base64.b64decode(c[1])
    if t == 'u': return base64.b64decode(c[1]).decode('utf-16-le', 'replace')
    if t == 'E': return Ellipsis
    if t == 't': return tuple(cval(x, depth) for x in c[1])
    if t == 'z': return frozenset(cval(x, depth) for x in c[1])
    if t == 'c':
        return build(c[1], depth + 1)
    return None

_built = {}
def build(addr, depth=0):
    if addr in _built: return _built[addr]
    d = CODES.get(addr)
    if d is None or depth > 50:
        return None
    code, unk = remap(base64.b64decode(d['code']))
    consts = tuple(cval(c, depth) for c in d['consts'])
    s = lambda l: tuple(str(x.encode('utf-8')) if isinstance(x, unicode) else x for x in l)
    co = types.CodeType(d['argc'], d['nloc'], d['stack'], d['flags'], code, consts,
                        s(d['names']), s(d['varnames']), str(d['file'].encode('utf-8')), str(d['name'].encode('utf-8')),
                        d['fl'], base64.b64decode(d['lnotab']), s(d['freevars']), s(d['cellvars']))
    _built[addr] = co
    return co

def deparse(co):
    from uncompyle6.semantics.pysource import code_deparse
    buf = io.BytesIO() if sys.version_info[0] == 2 else io.StringIO()
    code_deparse(co, out=buf, version=(2, 7))
    return buf.getvalue()

def fmt_func(d, co):
    """Boc than ham thanh 'def name(args):' + body."""
    from uncompyle6.semantics.pysource import code_deparse
    # Deparse function body: uncompyle6 deparses a code object as module-level body.
    body = deparse(co)
    args = list(co.co_varnames[:co.co_argcount])
    i = co.co_argcount
    if co.co_flags & 0x4: args.append('*' + co.co_varnames[i]); i += 1
    if co.co_flags & 0x8: args.append('**' + co.co_varnames[i]); i += 1
    hdr = 'def %s(%s):' % (co.co_name, ', '.join(args))
    if co.co_flags & 0x20 and 'yield' not in body: pass
    lines = [l for l in body.splitlines() if not l.startswith('# ')]
    if not any(l.strip() for l in lines): lines = ['pass']
    return hdr + '\n' + '\n'.join(('    ' + l) if l.strip() else '' for l in lines) + '\n'

class _Timeout(Exception): pass
def _alarm(sig, frm): raise _Timeout('timeout')

def out_path(fn):
    rel = fn.replace('\\', '/').lstrip('/')
    rel = re.sub(r'[^A-Za-z0-9_./\-]', '_', rel)
    if not rel.endswith('.py'): rel += '.py'
    return os.path.join(OUT, rel)

def work(item):
    import signal
    signal.signal(signal.SIGALRM, _alarm)
    fn, addrs = item
    p = out_path(fn)
    if os.path.exists(p) and os.environ.get('RESUME'):
        return fn, -1, 0, []
    # uncompyle6 in loi parse ra stdout/stderr -> nuot di
    devnull = open(os.devnull, 'w'); so, se = sys.stdout, sys.stderr
    res = []; ok = 0; fail = 0; errs = []
    for a in addrs:
        d = CODES[a]
        try:
            sys.stdout = sys.stderr = devnull
            signal.alarm(int(os.environ.get('FN_TIMEOUT', '20')))
            try:
                co = build(a)
                src = fmt_func(d, co)
            finally:
                signal.alarm(0); sys.stdout, sys.stderr = so, se
            ok += 1
            res.append((d['fl'], '# line %d  @%s\n%s' % (d['fl'], a, src)))
        except Exception as e:
            fail += 1
            msg = str(e).splitlines()[0][:200] if str(e) else type(e).__name__
            errs.append(msg)
            res.append((d['fl'], '# line %d  @%s\n# DECOMPILE FAILED: %s\ndef %s(*args): pass\n' % (d['fl'], a, msg, d['name'].encode('utf-8'))))
    res.sort()
    try: os.makedirs(os.path.dirname(p))
    except OSError: pass
    with open(p + '.tmp', 'w') as f:
        f.write('# -*- coding: utf-8 -*-\n# Decompiled from Onmyoji RAM dump: %s (%d functions)\n\n' % (fn.encode('utf-8'), len(addrs)))
        for _, s in res:
            f.write(s if isinstance(s, str) else s.encode('utf-8')); f.write('\n')
    os.rename(p + '.tmp', p)
    return fn, ok, fail, errs[:5]

def main():
    load()
    referenced = set()
    for d in CODES.values():
        def walk(c):
            if c[0] == 'c': referenced.add(c[1])
            elif c[0] in ('t', 'z'):
                for x in c[1]: walk(x)
        for c in d['consts']: walk(c)
    byfile = collections.defaultdict(list)
    seen = set()
    for a, d in CODES.items():
        if a in referenced: continue
        if not re.match(r'^[ -~]+$', d['file']) or not re.match(r'^[A-Za-z_<][A-Za-z0-9_<>]*$', d['name']): continue
        key = (d['file'], d['name'], d['fl'], d['code'])
        if key in seen: continue
        seen.add(key)
        byfile[d['file']].append(a)
    # file nho truoc: tien do deu, file khong lo khong chan ca pool
    items = sorted(byfile.items(), key=lambda x: len(x[1]))
    only = os.environ.get('ONLY')
    if only: items = [x for x in items if only in x[0]]
    print >>sys.stderr, 'files', len(items), 'top-level functions', sum(len(v) for _, v in items)
    pool = Pool(int(os.environ.get('JOBS', '8')))
    tot_ok = tot_fail = 0; errc = collections.Counter(); per = {}
    skipped = 0
    for i, (fn, ok, fail, errs) in enumerate(pool.imap_unordered(work, items, chunksize=1)):
        if ok < 0: skipped += 1; continue
        tot_ok += ok; tot_fail += fail; per[fn] = [ok, fail]
        for e in errs: errc[e[:80]] += 1
        if i % 50 == 0:
            print >>sys.stderr, 'JCODE_PROGRESS {"current":%d,"total":%d,"unit":"files"} ok=%d fail=%d' % (i, len(items), tot_ok, tot_fail)
            sys.stderr.flush()
    print >>sys.stderr, 'skipped (resume)', skipped
    json.dump({'ok': tot_ok, 'fail': tot_fail, 'top_errors': errc.most_common(30), 'per_file': per},
              open(os.path.join(OUT, '_stats.json'), 'w'), indent=1)
    print 'functions ok=%d fail=%d (%.1f%%)' % (tot_ok, tot_fail, 100.0 * tot_ok / max(1, tot_ok + tot_fail))
    for e, c in errc.most_common(10): print '  %5d %s' % (c, e)

if __name__ == '__main__':
    main()
