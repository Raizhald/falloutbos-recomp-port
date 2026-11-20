"""Replay one guest call in an x86 emulator and compare it with the recompiled run.

    difftest_emulate.py <snapshot dir> [--xbe game/default.xbe] [--limit N]

The snapshot dir holds pre-regs.txt / pre-mem.bin / post-regs.txt /
post-mem.bin written by an FBOS_DIFFTEST build (src/game/difftest.c). This
loads the "pre" state into Unicorn, overlays the executable sections from the
XBE (the original instructions), runs from the function's address until it
returns to the recorded return address, and compares the emulator's memory
and registers with the recompiled code's "post" state.

Classes of difference, per byte:
  both   -- emulator and recompiled code both changed it, to different values
            (a wrong computation: this is what to chase)
  emu    -- only the emulator changed it (the lifted code missed a write)
  native -- only the recompiled run changed it (a stray write -- or another
            guest thread writing during the call: noise is possible here)
Writes report.txt next to the snapshot.
"""
import argparse
import struct
import sys
from pathlib import Path

from unicorn import Uc, UcError, UC_ARCH_X86, UC_MODE_32, UC_HOOK_MEM_UNMAPPED, \
    UC_HOOK_CODE, UC_HOOK_INTR, UC_HOOK_MEM_WRITE, UC_HOOK_BLOCK
from unicorn.x86_const import (UC_X86_REG_EAX, UC_X86_REG_EBX, UC_X86_REG_ECX,
                               UC_X86_REG_EDX, UC_X86_REG_ESI, UC_X86_REG_EDI,
                               UC_X86_REG_ESP, UC_X86_REG_EBP, UC_X86_REG_EIP)

REGS = {'eax': UC_X86_REG_EAX, 'ebx': UC_X86_REG_EBX, 'ecx': UC_X86_REG_ECX,
        'edx': UC_X86_REG_EDX, 'esi': UC_X86_REG_ESI, 'edi': UC_X86_REG_EDI,
        'esp': UC_X86_REG_ESP}


def f80(v):
    """A double as Unicorn's x87 register value (mantissa, sign+exponent)."""
    import math
    if v == 0.0:
        return (0, 0x8000 if math.copysign(1.0, v) < 0 else 0)
    sign = 0x8000 if v < 0 else 0
    if math.isinf(v):
        return (1 << 63, sign | 0x7FFF)
    if math.isnan(v):
        return (3 << 62, 0x7FFF)
    m, e = math.frexp(abs(v))           # v = m * 2**e, m in [0.5, 1)
    return (int(m * (1 << 64)), sign | (e - 1 + 16383))


def from_f80(t):
    mant, se = t
    exp = se & 0x7FFF
    if exp == 0 and mant == 0:
        return -0.0 if se & 0x8000 else 0.0
    if exp == 0x7FFF:
        return float('nan') if mant & ((1 << 62) - 1) else (float('-inf') if se & 0x8000 else float('inf'))
    v = mant / float(1 << 63) * 2.0 ** (exp - 16383)
    return -v if se & 0x8000 else v


def read_regs(path):
    out = {}
    for line in Path(path).read_text().split('\n'):
        if '=' in line:
            k, v = line.strip().split('=', 1)
            if k.startswith('fp') and k[2:].isdigit():
                out[k] = struct.unpack('<d', struct.pack('<Q', int(v, 16)))[0]
            else:
                out[k] = int(v, 16) if k != 'fp_top' else int(v)
    return out


def read_mem(path):
    data = Path(path).read_bytes()
    regions, o = [], 0
    while o + 8 <= len(data):
        va, n = struct.unpack_from('<II', data, o)
        o += 8
        regions.append((va, data[o:o + n]))
        o += n
    return regions


def xbe_code_sections(path):
    d = Path(path).read_bytes()
    base = struct.unpack_from('<I', d, 0x104)[0]
    n = struct.unpack_from('<I', d, 0x11C)[0]
    sh = struct.unpack_from('<I', d, 0x120)[0] - base
    out = []
    for i in range(n):
        flags, va, vs, raw, rs, name = struct.unpack_from('<IIIIII', d, sh + i * 56)
        if flags & 0x4:                      # executable
            out.append((va, d[raw:raw + rs]))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('dir', type=Path)
    ap.add_argument('--xbe', type=Path,
                    default=Path(__file__).resolve().parents[1] / 'game/default.xbe')
    ap.add_argument('--limit', type=int, default=2_000_000_000)
    ap.add_argument('--writers', nargs=2, metavar=('LO', 'HI'),
                    help='record which instruction last wrote each byte in [LO,HI) (hex) '
                         'and report the writers of the bytes that differ')
    ap.add_argument('--trace', metavar='VA',
                    help='log entry state of every call to VA (hex) like the native '
                         'RECOMP_DIFFTEST_TRACE_VA log, and compare with trace.bin')
    ap.add_argument('--calltrace', action='store_true',
                    help='log every function entry (functions.json) and compare with the '
                         'native calltrace.bin (RECOMP_DIFFTEST_TRACE_VA=ALL)')
    ap.add_argument('--restore-code', action='store_true',
                    help='overwrite executable sections with the XBE bytes (off: Bink keeps '
                         'run-time tables inside its executable sections)')
    a = ap.parse_args()

    pre_r, post_r = read_regs(a.dir / 'pre-regs.txt'), read_regs(a.dir / 'post-regs.txt')
    pre, post = read_mem(a.dir / 'pre-mem.bin'), read_mem(a.dir / 'post-mem.bin')
    report = []
    say = lambda s: (report.append(s), print(s, flush=True))

    uc = Uc(UC_ARCH_X86, UC_MODE_32)
    for va, blob in pre:
        uc.mem_map(va, len(blob))
        uc.mem_write(va, blob)
    code_same = code_diff = 0
    for va, blob in xbe_code_sections(a.xbe):
        try:
            cur = uc.mem_read(va, len(blob))
        except UcError:
            say('code section %08X not mapped in the snapshot' % va)
            continue
        if bytes(cur) == blob:
            code_same += 1
        else:
            code_diff += 1
            if a.restore_code:
                uc.mem_write(va, blob)
    say('code sections: %d as in the XBE, %d changed at run time%s'
        % (code_same, code_diff, ' (restored)' if a.restore_code else ' (kept)'))

    for k, r in REGS.items():
        uc.reg_write(r, pre_r[k])
    uc.reg_write(UC_X86_REG_EBP, pre_r['esp'])
    # The x87 state the recompiled code had (the math helpers take their
    # arguments in ST0); without it they compute from an empty stack.
    if 'fp0' in pre_r:
        from unicorn import x86_const as X
        for k in range(8):
            uc.reg_write(getattr(X, 'UC_X86_REG_FP%d' % k), f80(pre_r['fp%d' % k]))
        uc.reg_write(X.UC_X86_REG_FPSW, (pre_r['fp_top'] & 7) << 11)
        uc.reg_write(X.UC_X86_REG_FPCW, pre_r.get('fp_cw', 0x27F))
        uc.reg_write(X.UC_X86_REG_FPTAG, 0)     # all valid
    ret = pre_r['return']
    say('call %08X, return to %08X, esp %08X' % (pre_r['va'], ret, pre_r['esp']))

    faults = []

    def on_unmapped(uc_, access, addr, size, value, user):
        faults.append((uc_.reg_read(UC_X86_REG_EIP), access, addr, size))
        return False

    def on_intr(uc_, intno, user):
        faults.append((uc_.reg_read(UC_X86_REG_EIP), 'int', intno, 0))
        uc_.emu_stop()

    writer = {}
    if a.writers:
        lo, hi = int(a.writers[0], 16), int(a.writers[1], 16)

        def on_write(uc_, access, addr, size, value, user):
            eip = uc_.reg_read(UC_X86_REG_EIP)
            for k in range(size):
                writer[addr + k] = eip
        uc.hook_add(UC_HOOK_MEM_WRITE, on_write, begin=lo, end=hi - 1)
    emu_trace = []
    if a.trace:
        tva = int(a.trace, 16)

        def on_trace(uc_, addr, size, user):
            r = [uc_.reg_read(x) for x in (UC_X86_REG_EAX, UC_X86_REG_EBX, UC_X86_REG_ECX,
                                           UC_X86_REG_EDX, UC_X86_REG_ESI, UC_X86_REG_EDI,
                                           UC_X86_REG_ESP)] + [0]
            rec = struct.pack('<8I', *r)
            for ptr, n in ((r[0], 128), (r[3], 256), (r[6] - 0x1E0, 0x200)):
                try:
                    rec += bytes(uc_.mem_read(ptr, n))
                except UcError:
                    rec += b'\0' * n
            emu_trace.append(rec)
            ret = struct.unpack('<I', bytes(uc_.mem_read(r[6], 4)))[0]
            pending.append((r[6], ret))
            if ret not in ret_hooked:
                ret_hooked.add(ret)
                uc_.hook_add(UC_HOOK_CODE, on_ret, begin=ret, end=ret)

        def on_ret(uc_, addr, size, user):
            esp = uc_.reg_read(UC_X86_REG_ESP)
            if pending and pending[-1][1] == addr and esp == pending[-1][0] + 4:
                e, _ = pending.pop()
                dst, stride = struct.unpack('<II', bytes(uc_.mem_read(e + 4, 8)))
                out = b''.join(bytes(uc_.mem_read(dst + k * stride, 8)) for k in range(8))
                emu_exit.append(out + bytes(uc_.mem_read(e - 0x200, 0x200)))
        pending, ret_hooked, emu_exit = [], set(), []
        uc.hook_add(UC_HOOK_CODE, on_trace, begin=tva, end=tva)
    ctrace = []
    if a.calltrace:
        import json
        fj = Path(__file__).resolve().parents[1] / 'build/disasm/functions.json'
        starts = {int(f['start'], 16) for f in json.loads(fj.read_text())}
        first = [True]

        def on_block(uc_, addr, size, user):
            if addr in starts:
                if first[0]:            # the watched function itself
                    first[0] = False
                    return
                r = [addr] + [uc_.reg_read(x) for x in (
                    UC_X86_REG_EAX, UC_X86_REG_EBX, UC_X86_REG_ECX, UC_X86_REG_EDX,
                    UC_X86_REG_ESI, UC_X86_REG_EDI, UC_X86_REG_ESP)]
                ctrace.append(struct.pack('<8I', *r) + bytes(uc_.mem_read(r[7], 32)))
        uc.hook_add(UC_HOOK_BLOCK, on_block)
    uc.hook_add(UC_HOOK_MEM_UNMAPPED, on_unmapped)
    uc.hook_add(UC_HOOK_INTR, on_intr)
    # Stop at the return address only when this call's frame is gone: a
    # nested call can come back to the same address (a callback into the
    # caller), and stopping there compared a half-finished call.
    def on_ret_addr(uc_, addr, size, user):
        if uc_.reg_read(UC_X86_REG_ESP) > pre_r['esp']:
            uc_.emu_stop()
    uc.hook_add(UC_HOOK_CODE, on_ret_addr, begin=ret, end=ret)
    try:
        uc.emu_start(pre_r['va'], 0xFFFFFFFF, count=a.limit)
    except UcError as e:
        say('emulation stopped: %s at eip %08X' % (e, uc.reg_read(UC_X86_REG_EIP)))
    for f in faults[:10]:
        say('  fault: eip %08X kind %s addr %08X size %d' % f)
    eip = uc.reg_read(UC_X86_REG_EIP)
    say('emulator ended at %08X (%s)' % (eip, 'returned' if eip == ret else 'DID NOT RETURN'))

    for k, r in REGS.items():
        e, n = uc.reg_read(r), post_r[k]
        if k == 'esp':
            e += 0                           # both are after the callee's ret
        say('  %-4s emulator %08X  recompiled %08X %s' % (k, e, n, '' if e == n else '<-- differs'))

    # ST0 is a result only when the call leaves one more value on the x87
    # stack (a float return); otherwise it is a freed register.
    if 'fp0' in post_r and (post_r['fp_top'] & 7) == ((pre_r['fp_top'] + 7) & 7):
        from unicorn import x86_const as X
        top = (uc.reg_read(X.UC_X86_REG_FPSW) >> 11) & 7
        st0 = from_f80(uc.reg_read(getattr(X, 'UC_X86_REG_FP%d' % top)))
        nst0 = post_r['fp%d' % (post_r['fp_top'] & 7)]
        same = (st0 == nst0 or (st0 != st0 and nst0 != nst0)
                or abs(st0 - nst0) <= 1e-9 * max(abs(st0), abs(nst0)))
        say('  st0  emulator %.17g (top %d)  recompiled %.17g (top %d) %s'
            % (st0, top, nst0, post_r['fp_top'] & 7,
               '' if same and top == (post_r['fp_top'] & 7) else '<-- differs'))

    post_map = {va: blob for va, blob in post}
    cls = {'both': [], 'emu': [], 'native': []}
    for va, before in pre:
        after = post_map.get(va)
        if after is None or len(after) != len(before):
            say('region %08X changed shape between snapshots; skipped' % va)
            continue
        emu = bytes(uc.mem_read(va, len(before)))
        if emu == after:
            continue
        # Byte-wise classes, compressed to runs; equal pages skipped whole.
        i, n = 0, len(before)
        while i < n:
            if i % 4096 == 0 and emu[i:i + 4096] == after[i:i + 4096]:
                i += 4096
                continue
            if emu[i] == after[i]:
                i += 1
                continue
            j = i
            while j < n and emu[j] != after[j]:
                j += 1
            ec = any(emu[k] != before[k] for k in range(i, j))
            nc = any(after[k] != before[k] for k in range(i, j))
            kind = 'both' if ec and nc else 'emu' if ec else 'native'
            # The aligned dword around a short run, as both sides have it:
            # tells a float rounding apart from a wrong value.
            a0 = i & ~3
            if j - a0 <= 4 and a0 + 4 <= n:
                words = (emu[a0:a0 + 4], after[a0:a0 + 4])
            else:
                words = None
            cls[kind].append((va + i, j - i, words))
            i = j
    for kind, runs in cls.items():
        total = sum(n for _, n, _w in runs)
        say('%-6s %6d runs, %8d bytes' % (kind, len(runs), total))
        for va, n, words in runs[:25]:
            if words and kind == 'both':
                fe, fn = struct.unpack('<f', words[0])[0], struct.unpack('<f', words[1])[0]
                say('    %08X +%d  emu %s nat %s  (float %.9g / %.9g)'
                    % (va, n, words[0].hex(), words[1].hex(), fe, fn))
            else:
                say('    %08X +%d' % (va, n))
    if a.writers:
        import collections
        hist = collections.Counter()
        for va, n, _w in cls['both'] + cls['emu']:
            for k in range(n):
                hist[writer.get(va + k, 0)] += 1
        say('writers of differing bytes (emulator, original code):')
        for eip, n in hist.most_common(20):
            say('    eip %08X  %d bytes' % (eip, n))
        # every distinct writer seen in range, to see what the healthy paths are
        allw = collections.Counter(writer.values())
        say('all writers in range: ' + ' '.join('%08X:%d' % kv for kv in allw.most_common(30)))
    if a.calltrace:
        nat = (a.dir / 'calltrace.bin').read_bytes()
        native = [nat[i:i + 64] for i in range(0, len(nat) - 63, 64)]
        say('calltrace: emulator %d calls, recompiled %d calls' % (len(ctrace), len(native)))
        names = ('va', 'eax', 'ebx', 'ecx', 'edx', 'esi', 'edi', 'esp')
        bad = 0
        for i, (e, n) in enumerate(zip(ctrace, native)):
            if e == n:
                continue
            er, nr = struct.unpack_from('<8I', e), struct.unpack_from('<8I', n)
            diff = ['%s %08X/%08X' % (names[k], er[k], nr[k]) for k in range(8) if er[k] != nr[k]]
            if e[32:] != n[32:]:
                diff.append('args ' + e[32:].hex() + ' / ' + n[32:].hex())
            say('  call %d to %08X/%08X differs: %s' % (i, er[0], nr[0], '; '.join(diff)))
            if i:
                pr = struct.unpack_from('<8I', ctrace[i - 1])
                say('    previous call: %08X' % pr[0])
            bad += 1
            if bad >= 6:
                break
        if not bad:
            say('  identical for the first %d calls' % min(len(ctrace), len(native)))
    if a.trace:
        RS = 32 + 128 + 256 + 0x200
        nat = (a.dir / 'trace.bin').read_bytes()
        native = [nat[i:i + RS] for i in range(0, len(nat) - RS + 1, RS)]
        say('trace %s: emulator %d calls, recompiled %d calls' % (a.trace, len(emu_trace), len(native)))
        shown = 0
        for i, (e, n) in enumerate(zip(emu_trace, native)):
            if e == n:
                continue
            parts = []
            er, nr = struct.unpack_from('<8I', e), struct.unpack_from('<8I', n)
            names = ('eax', 'ebx', 'ecx', 'edx', 'esi', 'edi', 'esp')
            for k in range(7):
                if er[k] != nr[k]:
                    parts.append('%s %08X/%08X' % (names[k], er[k], nr[k]))
            for label, lo, hi in (('coef', 32, 160), ('quant', 160, 416), ('stack', 416, 416 + 0x200)):
                if e[lo:hi] != n[lo:hi]:
                    idx = [j for j in range(lo, hi) if e[j] != n[j]]
                    parts.append('%s bytes %s (%d)' % (label, ','.join(str(j - lo) for j in idx[:12]), len(idx)))
            say('  call %d differs: %s' % (i, '; '.join(parts)))
            if label and 'coef' in ' '.join(parts):
                ce = struct.unpack_from('<64h', e, 32); cn = struct.unpack_from('<64h', n, 32)
                say('    emu coef: ' + ' '.join(map(str, ce)))
                say('    nat coef: ' + ' '.join(map(str, cn)))
            shown += 1
            if shown >= 8:
                break
        if not shown:
            say('  all %d traced calls have identical inputs' % min(len(emu_trace), len(native)))
        xp = a.dir / 'trace_exit.bin'
        if xp.exists():
            XS = 64 + 0x200
            nx = xp.read_bytes()
            nexit = [nx[i:i + XS] for i in range(0, len(nx) - XS + 1, XS)]
            say('exit records: emulator %d, recompiled %d' % (len(emu_exit), len(nexit)))
            shown = 0
            for i, (e, n) in enumerate(zip(emu_exit, nexit)):
                if e[:64] == n[:64]:
                    continue
                fe = [j for j in range(64, XS) if e[j] != n[j]]
                say('  call %d: output block differs; frame bytes differing: %d (offsets below entry esp: %s)'
                    % (i, len(fe), ','.join(hex(0x200 - (j - 64)) for j in fe[:16])))
                for k in range(8):
                    say('    row %d emu %s  nat %s' % (k, e[k*8:k*8+8].hex(), n[k*8:k*8+8].hex()))
                ce = struct.unpack_from('<64h', emu_trace[i], 32)
                say('    coef: ' + ' '.join(map(str, ce)))
                q = struct.unpack_from('<64i', emu_trace[i], 160)
                say('    quant: ' + ' '.join(map(str, q)))
                # the column-pass buffer: 64 dwords at entry_esp - 0x13C + 0x3C = entry_esp - 0x100
                te = struct.unpack_from('<64i', e, 64 + 0x100)
                tn = struct.unpack_from('<64i', n, 64 + 0x100)
                say('    temp emu: ' + ' '.join(map(str, te)))
                say('    temp nat: ' + ' '.join(map(str, tn)))
                shown += 1
                if shown >= 3:
                    break
            if not shown:
                say('  all exit blocks identical')
    (a.dir / 'report.txt').write_text('\n'.join(report) + '\n')
    # Machine-readable runs for further analysis.
    with open(a.dir / 'runs.txt', 'w') as f:
        for kind, runs in cls.items():
            for va, n, _w in runs:
                f.write('%s %08X %d\n' % (kind, va, n))


if __name__ == '__main__':
    main()
