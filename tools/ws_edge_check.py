"""Widescreen culling check over level_tour.py pictures.

    ws_edge_check.py build/levels/16x9

For every rt-*.bmp: the share of picture rows that are lit just inside the
edge of the original 4:3 picture and black just outside it. Scenery that
stops exactly there (the title culling to 4:3) gives most rows; ordinary
geometry a few percent. Lines above 0.25 are marked <<<. Menus, options
and load screens are 4:3 by design and show up too.
"""
import sys, glob, os, json
import numpy as np
from PIL import Image
base = sys.argv[1]
rows = []
for d in sorted(glob.glob(base + '/*/')):
    for f in sorted(glob.glob(d + 'rt-*.bmp')):
        a = np.asarray(Image.open(f).convert('L'), dtype=np.int16)
        H, W = a.shape
        w43 = round(W * 0.75); ox = (W - w43) // 2
        # rows that are not letterbox
        live = a.max(axis=1) > 6
        a = a[live]
        if a.shape[0] < 10:
            continue
        blk = (a < 6)
        res = []
        for b, outside in ((ox, -1), (ox + w43, 1)):
            # per row: inside pixel lit, outside pixel black, along the boundary
            ins = ~blk[:, b + 2] if outside < 0 else ~blk[:, b - 3]
            out = blk[:, b - 3] if outside < 0 else blk[:, b + 2]
            cut = (ins & out).mean()
            res.append(round(float(cut), 3))
        side_black = float(np.r_[blk[:, :ox].ravel(), blk[:, ox + w43:].ravel()].mean())
        mid_black = float(blk[:, ox:ox + w43].mean())
        rows.append((os.path.basename(d.rstrip('/')), os.path.basename(f), res, round(side_black, 3), round(mid_black, 3)))
for r in rows:
    flag = ' <<<' if max(r[2]) > 0.25 else ''
    print(r[0], r[1], 'cutL/R', r[2], 'black side/mid', r[3], r[4], flag)
