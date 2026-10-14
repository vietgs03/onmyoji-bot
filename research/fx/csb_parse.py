#!/usr/bin/env python3
"""
csb_parse.py - Doc file CSB (Cocos Studio FlatBuffers, magic "2.1.0.0") trong res.npk.

Truoc day chi parse 2.189 layout JSON (widgetTree). Nhung res.npk con 11.809 file
`*.bin_14000000` = CSB nhi phan (CSLoader.createNodeWithFlatBuffersFile trong source).
File nay doc CSB khong can flatc: tu doc vtable theo schema CSParseBinary_generated.h
cua cocos2d-x v3.

Moi node xuat ra: name, class, pos (local), anchor, size, scale, visible, touch,
text, image (path/plist), sub-csb (ProjectNode), children.

Dung:
  python csb_parse.py <file.bin_14000000>           # in cay
  python csb_parse.py <file> --json                 # JSON
"""
import struct, sys, json

U16 = struct.Struct('<H'); I32 = struct.Struct('<i'); U32 = struct.Struct('<I')
F32 = struct.Struct('<f')


class Buf:
    def __init__(self, b):
        self.b = b

    def u32(self, o): return U32.unpack_from(self.b, o)[0]
    def i32(self, o): return I32.unpack_from(self.b, o)[0]
    def f32(self, o): return F32.unpack_from(self.b, o)[0]

    # --- table helpers ---
    def field_off(self, tab, slot):
        """Tra ve vi tri tuyet doi cua field `slot` (vtable offset 4,6,8..) hoac None."""
        vt = tab - self.i32(tab)
        vlen = U16.unpack_from(self.b, vt)[0]
        if slot >= vlen:
            return None
        fo = U16.unpack_from(self.b, vt + slot)[0]
        return tab + fo if fo else None

    def ref(self, tab, slot):
        o = self.field_off(tab, slot)
        return None if o is None else o + self.u32(o)

    def string(self, tab, slot):
        p = self.ref(tab, slot)
        if p is None:
            return None
        n = self.u32(p)
        return self.b[p + 4:p + 4 + n].decode('utf-8', 'replace')

    def vec(self, tab, slot):
        p = self.ref(tab, slot)
        if p is None:
            return []
        n = self.u32(p)
        return [p + 4 + 4 * i + self.u32(p + 4 + 4 * i) for i in range(n)]

    def vec_str(self, tab, slot):
        out = []
        for p in self.vec(tab, slot):
            n = self.u32(p)
            out.append(self.b[p + 4:p + 4 + n].decode('utf-8', 'replace'))
        return out

    def f2(self, tab, slot):
        o = self.field_off(tab, slot)
        return None if o is None else (self.f32(o), self.f32(o + 4))

    def u8(self, tab, slot, d):
        o = self.field_off(tab, slot)
        return d if o is None else self.b[o]


# slot cua field text / anh chinh theo tung loai options (CSParseBinary_generated.h)
TEXT_SLOT = {'Button': 14, 'Text': 12, 'TextBMFont': 8, 'TextField': 14,
             'TextAtlas': 6}
IMAGE_SLOT = {'Button': 6, 'ImageView': 6, 'Sprite': 6, 'CheckBox': 6,
              'LoadingBar': 6, 'Slider': 6}


def _res(buf, tab, slot):
    p = buf.ref(tab, slot)
    if p is None:
        return None
    path = buf.string(p, 4)
    plist = buf.string(p, 6)
    if not path:
        return None
    return {'path': path, 'plist': plist or None}


def _text(buf, tab, slot):
    # TextAtlas: slot 6 la ResourceData, text that o slot 8 (stringValue)
    if slot == 6:
        return buf.string(tab, 8)
    return buf.string(tab, slot)


BAD_CLASSES = {}


def parse_node(buf, nt):
    cls = buf.string(nt, 4) or ''
    node = {'class': cls}
    try:
        _fill(buf, nt, cls, node)
    except (struct.error, IndexError, UnicodeError):
        # options cua class nay khong theo WidgetOptions (custom node) -> bo qua phan options
        BAD_CLASSES[cls] = BAD_CLASSES.get(cls, 0) + 1
        node['opts_error'] = True
    kids = [parse_node(buf, c) for c in buf.vec(nt, 6)]
    if kids:
        node['children'] = kids
    return node


def _fill(buf, nt, cls, node):
    opt = buf.ref(nt, 8)
    data = buf.ref(opt, 4) if opt is not None else None
    if data is not None:
        w = buf.ref(data, 4)          # widgetOptions / nodeOptions luon o slot 4
        if w is not None:
            node['name'] = buf.string(w, 4)
            node['tag'] = (lambda o: buf.i32(o) if o else 0)(buf.field_off(w, 16))
            node['pos'] = buf.f2(w, 18) or (0.0, 0.0)
            node['scale'] = buf.f2(w, 20) or (1.0, 1.0)
            node['anchor'] = buf.f2(w, 22) or (0.0, 0.0)
            node['size'] = buf.f2(w, 26) or (0.0, 0.0)
            node['visible'] = bool(buf.u8(w, 12, 1))
            node['touch'] = bool(buf.u8(w, 34, 0))
            cb = buf.string(w, 42)
            if cb:
                node['callback'] = cb
            lc = buf.ref(w, 44)
            if lc is not None:
                px, py = buf.u8(lc, 4, 0), buf.u8(lc, 6, 0)
                if px or py:
                    po = buf.field_off(lc, 8); qo = buf.field_off(lc, 10)
                    node['pct'] = (buf.f32(po) if (px and po) else None,
                                   buf.f32(qo) if (py and qo) else None)
        if cls in TEXT_SLOT:
            t = _text(buf, data, TEXT_SLOT[cls])
            if t:
                node['text'] = t
        if cls in IMAGE_SLOT:
            r = _res(buf, data, IMAGE_SLOT[cls])
            if r:
                node['image'] = r
        if cls == 'ProjectNode':
            fn = buf.string(data, 6)
            if fn:
                node['csb'] = fn


def parse(blob):
    buf = Buf(blob)
    root = buf.u32(0)
    ver = buf.string(root, 4)
    if not ver or not ver[0].isdigit():
        raise ValueError('not a CSB: version=%r' % ver)
    tex = buf.vec_str(root, 6)
    nt = buf.ref(root, 10)
    return {'version': ver, 'textures': tex,
            'tree': parse_node(buf, nt) if nt is not None else None}


def walk(node, parent_bl=(0.0, 0.0), parent_scale=(1.0, 1.0), parent_size=None, path=''):
    """Duyet cay, tinh toa do canvas (goc duoi-trai man hinh) cua TAM node.

    Chuan cocos2d-x / Cocos Studio 2.x (CSB): `pos` = vi tri DIEM ANCHOR cua node
    trong he toa do noi bo cua cha, goc (0,0) = goc DUOI-TRAI cua cha (khac JSON 1.x
    la tinh tu anchor cua cha). He noi bo cua cha bi nhan boi scale cua cha.
    Bo qua rotation/skew (UI hau nhu khong xoay).
    Neu node bat layoutComponent % -> pos = pct * size cha.
    """
    pos = list(node.get('pos', (0.0, 0.0)))
    pct = node.get('pct')
    if pct and parent_size:
        if pct[0] is not None: pos[0] = pct[0] * parent_size[0]
        if pct[1] is not None: pos[1] = pct[1] * parent_size[1]
    ax, ay = node.get('anchor', (0.0, 0.0))
    w, h = node.get('size', (0.0, 0.0))
    sx, sy = node.get('scale', (1.0, 1.0))
    wsx, wsy = parent_scale[0] * sx, parent_scale[1] * sy      # scale the gioi cua node
    anchor_w = (parent_bl[0] + pos[0] * parent_scale[0], parent_bl[1] + pos[1] * parent_scale[1])
    bl = (anchor_w[0] - ax * w * wsx, anchor_w[1] - ay * h * wsy)
    center = (bl[0] + w * wsx / 2, bl[1] + h * wsy / 2)
    p = (path + '/' + (node.get('name') or '?')) if path else (node.get('name') or 'root')
    yield p, node, center, (abs(w * wsx), abs(h * wsy))
    for c in node.get('children', []):
        yield from walk(c, bl, (wsx, wsy), (w, h), p)


def _print(node, ind=0):
    bits = [node.get('class', ''), repr(node.get('name'))]
    for k in ('pos', 'size', 'anchor'):
        if k in node:
            bits.append('%s=(%g,%g)' % (k, *node[k]))
    for k in ('text', 'csb', 'callback'):
        if k in node:
            bits.append('%s=%r' % (k, node[k]))
    if 'image' in node:
        bits.append('img=%s' % node['image']['path'])
    print('  ' * ind + ' '.join(bits))
    for c in node.get('children', []):
        _print(c, ind + 1)


if __name__ == '__main__':
    d = parse(open(sys.argv[1], 'rb').read())
    if '--json' in sys.argv:
        print(json.dumps(d, ensure_ascii=False, indent=1))
    else:
        print('version', d['version'], 'textures', d['textures'][:5])
        _print(d['tree'])
