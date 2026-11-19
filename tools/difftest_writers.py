"""Who wrote the bytes that differ? planewrites.bin (FBOS_DIFFTEST with
RECOMP_DIFFTEST_WATCHPLANE) + runs.txt (difftest_emulate) + bin/fbos-difftest.map.

    difftest_writers.py <snapshot dir>"""
import bisect, collections, re, struct, sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
d = Path(sys.argv[1])
raw = (d / 'planewrites.bin').read_bytes()
img = struct.unpack_from('<Q', raw, 0)[0]
recs = [struct.unpack_from('<QII', raw, 8 + i * 16)[:2] for i in range((len(raw) - 8) // 16)]
syms = []
for line in (root / 'bin/fbos-difftest.map').read_text(errors='replace').splitlines():
    m = re.match(r'\s*[0-9a-f]{4}:[0-9a-f]{8}\s+(\S+)\s+([0-9a-f]{16})\s', line)
    if m:
        syms.append((int(m.group(2), 16), m.group(1)))
syms.sort()
keys = [a for a, _ in syms]
def sym(rip):
    i = bisect.bisect_right(keys, rip) - 1
    return '%s+0x%X' % (syms[i][1], rip - syms[i][0]) if i >= 0 else hex(rip)
last = {}
for rip, va in recs:
    for k in range(8):
        last[va + k] = rip          # a write covers up to 8 bytes from its fault address
diff = []
for line in (d / 'runs.txt').read_text().splitlines():
    kind, a, n = line.split()
    if kind in ('both', 'native'):
        diff += range(int(a, 16), int(a, 16) + int(n))
print('plane writes logged: %d, image base %X' % (len(recs), img))
funcs, rips = collections.Counter(), collections.Counter()
for b in diff:
    r = last.get(b)
    if r is None:
        continue
    s = sym(r)
    funcs[s.split('+')[0]] += 1
    rips[s] += 1
print('last native writer of differing bytes, by function:')
for f, n in funcs.most_common(12):
    print('  %6d  %s' % (n, f))
print('by instruction:')
for f, n in rips.most_common(15):
    print('  %6d  %s' % (n, f))
allf = collections.Counter(sym(r).split('+')[0] for r, _ in recs)
print('all plane writers:', ', '.join('%s:%d' % kv for kv in allf.most_common(12)))
