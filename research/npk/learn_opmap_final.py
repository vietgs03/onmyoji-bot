# -*- coding: utf-8 -*-
import json, base64, os, sys, opcode, collections, types
execfile('/work/learn_opmap_lib.py')
pairs=[]
for f,lst in ne.items():
    std=get_std(f); idx=collections.defaultdict(list)
    for (nm,fl),cs in std.items():
        for c in cs: idx[(nm,tuple(c.co_varnames),tuple(c.co_names))].append(c)
    for d in lst:
        cs=idx.get((d['name'],tuple(d['varnames']),tuple(d['names'])),[])
        if len(cs)==1: pairs.append((d,cs[0]))
sl=[(d,c) for d,c in pairs if len(d['bcode'])==len(c.co_code)]
votes=collections.defaultdict(collections.Counter); argd=collections.defaultdict(collections.Counter)
for d,c in sl:
    ins=insns_std(c.co_code); pos=0; b=d['bcode']
    for op,arg in ins:
        nm=opcode.opname[op]; votes[ord(b[pos])][nm]+=1
        if arg is not None:
            na=ord(b[pos+1])|(ord(b[pos+2])<<8); argd[nm]['eq' if na==arg else 'ne']+=1; pos+=3
        else: pos+=1
final={}
for k,v in sorted(votes.items()):
    nm,n=v.most_common(1)[0]; tot=sum(v.values())
    final[k]=nm
    print '0x%02X %-22s %5d/%-5d %s'%(k,nm,n,tot,'' if n==tot else dict(v))
names=collections.Counter(final.values())
print 'dup names:',[n for n,c in names.items() if c>1]
allnames=[n for n in opcode.opname if not n.startswith('<')]
print 'unseen std ops:',[n for n in allnames if n not in names]
print 'arg mismatches:',{k:dict(v) for k,v in argd.items() if v['ne']}
json.dump({'%d'%k:v for k,v in final.items()},open('/work/opmap_final.json','w'),indent=1)
