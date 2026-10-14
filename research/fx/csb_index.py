#!/usr/bin/env python3
"""
csb_index.py - Quet TOAN BO CSB trong res.npk -> chi muc + toa do man hinh.

Dau ra (research/fx/out/csb/):
  csb_index.jsonl   1 dong / CSB: id, textures, dir (thu muc ui suy tu plist), so node,
                    ten nut, text, sub-csb tham chieu
  csb_nodes.jsonl   1 dong / node co ten: id, path, class, name, text, image,
                    canvas(tam, goc duoi-trai), screen(tam, goc tren-trai), size, touch,
                    callback, root_full (CSB co root 1136x640 = man/panel full-screen)

Cong thuc man hinh (da verify o docs/ML_GAME_UNDERSTANDING.md muc 10/18):
  screen_x = canvas_x ; screen_y = 640 - canvas_y   (anh chup 1136x640)
Chi DUNG cho CSB co root full-screen (1136x640). CSB con (node_*.csb, item) co toa
do TUONG DOI noi no duoc gan vao -> xem `root_full`.
"""
import os, sys, json, glob, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import csb_parse as C
from dump_all_coords import features_of

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
EXPORT = os.path.join(REPO, 'data', 'ui_coords', 'coords_csb.jsonl')
CLICKABLE = ('Button', 'CheckBox', 'TextField', 'Slider')

SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'out', 'full_res')
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'out', 'csb')
H = 640


def ui_dir(textures):
    dirs = collections.Counter()
    for t in textures:
        t = t.replace('\\', '/')
        if t.startswith('mulnation/'):
            t = '/'.join(t.split('/')[2:])
        parts = t.split('/')
        if len(parts) >= 2:
            dirs['/'.join(parts[:2]) if parts[0] in ('ui_new', 'ui') else parts[0]] += 1
    return dirs.most_common(1)[0][0] if dirs else None


def root_size(tree):
    """Kich thuoc node co ten dau tien (thuong la 'root' / Layer)."""
    stack = [tree]
    while stack:
        n = stack.pop(0)
        if n.get('name') and n.get('size') and n['size'] != (0.0, 0.0):
            return n['size']
        stack.extend(n.get('children', []))
    return None


def main():
    os.makedirs(OUT, exist_ok=True)
    fi = open(os.path.join(OUT, 'csb_index.jsonl'), 'w', encoding='utf-8')
    fn = open(os.path.join(OUT, 'csb_nodes.jsonl'), 'w', encoding='utf-8')
    # ban gon cho bot: chi CSB full-screen, node hien + bam duoc hoac co text
    fe = open(EXPORT, 'w', encoding='utf-8')
    n_csb = n_nodes = n_full = n_exp = 0
    for f in sorted(glob.glob(os.path.join(SRC, '*.bin_14000000')),
                    key=lambda p: int(os.path.basename(p).split('.')[0])):
        cid = os.path.basename(f).split('.')[0]
        try:
            d = C.parse(open(f, 'rb').read())
        except Exception:
            continue
        dir_ = ui_dir(d['textures'])
        rs = root_size(d['tree'])
        full = bool(rs and abs(rs[0] - 1136) < 1 and abs(rs[1] - 640) < 1)
        n_full += full
        btns, texts, subs, cnt = [], [], [], 0
        for path, node, (cx, cy), (w, h) in C.walk(d['tree']):
            if not node.get('name'):
                continue
            cnt += 1
            if node['class'] in ('Button', 'CheckBox') or node.get('touch'):
                btns.append(node['name'])
            if node.get('text'):
                texts.append(node['text'])
            if node.get('csb'):
                subs.append(node['csb'])
            rec = {'id': cid, 'path': path, 'class': node['class'], 'name': node['name'],
                   'canvas': [round(cx, 1), round(cy, 1)],
                   'screen': [round(cx), round(H - cy)] if full else None,
                   'size': [round(w), round(h)], 'touch': node.get('touch', False),
                   'visible': node.get('visible', True), 'root_full': full}
            for k in ('text', 'callback', 'csb'):
                if node.get(k):
                    rec[k] = node[k]
            if node.get('image'):
                rec['image'] = node['image']['path']
            fn.write(json.dumps(rec, ensure_ascii=False) + '\n')
            n_nodes += 1
            if full and rec['visible'] and (node['class'] in CLICKABLE or rec['touch']
                                            or rec.get('text')):
                parts = path.split('/')
                blob = '%s %s %s' % (dir_, path, rec.get('image') or '')
                row = {
                    'layout': 'csb:' + cid, 'man': dir_ or '', 'panel': '/'.join(parts[2:4]),
                    'name': node['name'], 'class': node['class'], 'text': rec.get('text'),
                    'screen': rec['screen'], 'size': rec['size'],
                    'touch': rec['touch'] or node['class'] in CLICKABLE,
                    'image': rec.get('image'), 'path': '/'.join(parts[2:]),
                    'features': features_of(blob)}
                row = {k: v for k, v in row.items() if v not in (None, [], '')}
                fe.write(json.dumps(row, ensure_ascii=False, separators=(',', ':')) + '\n')
                n_exp += 1
        fi.write(json.dumps({'id': cid, 'dir': dir_,
                             'textures': sorted(set(d['textures'])),
                             'root_size': rs, 'root_full': full, 'nodes': cnt,
                             'buttons': btns, 'texts': texts[:60], 'sub_csb': sorted(set(subs))},
                            ensure_ascii=False) + '\n')
        n_csb += 1
    print('csb', n_csb, 'full-screen', n_full, 'named nodes', n_nodes, 'exported', n_exp,
          '->', EXPORT)


if __name__ == '__main__':
    main()
