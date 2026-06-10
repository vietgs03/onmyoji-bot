#!/usr/bin/env python3
"""operator_loop.py - TAY: thuc thi lenh tu ANALYST (mat) qua agent_bus.

Vong lap: chup man -> luu logs/duplex/step_N.png -> gui bus hoi analyst ->
cho directive -> thuc thi (tap x y [method] / back / drag / wait / done) -> lap.
Analyst la agent NHIN ANH THAT nen operator khong can tu doan.
"""
import json, os, sys, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in ('automation', 'scripts', 'ml'):
    sys.path.insert(0, os.path.join(ROOT, p))
import cv2
from agent import Agent
from agent_bus import send, read_new

DUPLEX = os.path.join(ROOT, 'logs', 'duplex')
os.makedirs(DUPLEX, exist_ok=True)

def main():
    a = Agent()
    a.c._cmd('movewin 0 0')
    step = 0
    max_steps = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    read_new('operator')  # xoa message ton dong
    while step < max_steps:
        img = a.shot()
        if img is None:
            send('operator', 'analyst', 'report', 'shot=None (game chet?)')
            time.sleep(3); continue
        shot_path = os.path.join(DUPLEX, f'step_{step}.png')
        cv2.imwrite(shot_path, img)
        send('operator', 'analyst', 'question',
             f'step {step}: man hinh tai {shot_path}. Lenh tiep theo?',
             {'step': step, 'shot': shot_path})
        # cho directive (poll bus, timeout 600s)
        t0 = time.time(); cmd = None
        while time.time() - t0 < 600:
            for m in read_new('operator'):
                if m.get('type') == 'directive':
                    cmd = m
            if cmd: break
            time.sleep(2)
        if cmd is None:
            print('timeout cho analyst'); break
        d = cmd.get('data') or {}
        act = d.get('act', '')
        print(f'[step {step}] act={act} {d}')
        if act == 'done':
            send('operator', 'analyst', 'report', 'operator ket thuc theo lenh done')
            break
        elif act == 'tap':
            method = d.get('method', 'bg')
            fn = {'bg': a.c.bgclick, 'polite': a.c.politeclick, 'fg': a.c.fgclick}[method]
            fn(int(d['x']), int(d['y']))
            time.sleep(float(d.get('wait', 2.0)))
        elif act == 'back':
            a.c.bgclick(45, 68); time.sleep(1.5)
        elif act == 'drag':
            a.c._cmd(f"senddrag {d['x0']} {d['y0']} {d['x1']} {d['y1']}")
            time.sleep(1.5)
        elif act == 'wait':
            time.sleep(float(d.get('sec', 3)))
        step += 1
    print('operator loop xong')

if __name__ == '__main__':
    main()
