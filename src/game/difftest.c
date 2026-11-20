/* Differential test hook (FBOS_DIFFTEST builds only).
 *
 * Every direct call goes through RECOMP_ABI_CALL; in this build that macro
 * asks recomp_difftest_pre() first. On the RECOMP_DIFFTEST_NTH-th call
 * (default 30) of the function at RECOMP_DIFFTEST_VA, counted from
 * RECOMP_DIFFTEST_AFTER seconds into the run, it writes the guest
 * registers and all committed guest memory (RAM 0..64 MB and the contiguous
 * window at 0x80000000) to RECOMP_DIFFTEST_DIR, runs the recompiled function,
 * and writes them again afterwards. tools/difftest_emulate.py then runs the
 * ORIGINAL x86 code from the "pre" state in an emulator and compares its
 * result with the "post" state: wherever they differ, the lifted code did
 * something the processor does not.
 *
 * Memory file format, repeated: uint32 guest VA, uint32 byte count, bytes.
 * Register file: one "name=hex" per line.
 */
#ifdef RECOMP_DIFFTEST

#include <windows.h>
#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <stddef.h>
#include "recomp_types.h"

extern ptrdiff_t xbox_GetMemoryOffset(void);

static int s_init, s_done;
static uint32_t s_va, s_nth = 30, s_count;
static ULONGLONG s_after_ms, s_start;
static DWORD s_thread;
static char s_dir[512];
/* RECOMP_DIFFTEST_TRACE_VA: while the watched call runs, log the entry state
 * of every call to this function (registers, 128 bytes at eax, 256 at edx,
 * 32 bytes of stack) to trace.bin -- the emulator logs the same, and the first
 * record that differs says whether the input or the function is wrong. */
/* RECOMP_DIFFTEST_WATCH=<guest va>: a hardware write breakpoint (DR0, one
 * byte) on that guest byte while the watched call runs; every write logs the
 * host instruction address to watch.txt (map it with bin/fbos-difftest.map). */
static uint32_t s_watch;
static FILE *s_watch_log;
static int s_watch_n;
static uintptr_t s_watch_host;

static LONG CALLBACK dt_veh(PEXCEPTION_POINTERS ep)
{
    DWORD code = ep->ExceptionRecord->ExceptionCode;
    CONTEXT *c = ep->ContextRecord;
    if (code == 0xE0FF0001u) {                  /* arm */
        c->Dr0 = s_watch_host;
        c->Dr7 = (c->Dr7 & ~0xF0003ull) | 0x1ull | (0x1ull << 16);
        return EXCEPTION_CONTINUE_EXECUTION;
    }
    if (code == 0xE0FF0002u) {                  /* disarm */
        c->Dr7 &= ~0x3ull;
        return EXCEPTION_CONTINUE_EXECUTION;
    }
    if (code == EXCEPTION_SINGLE_STEP && (c->Dr6 & 1)) {
        c->Dr6 &= ~0xFull;
        if (s_watch_log && s_watch_n++ < 400)
            fprintf(s_watch_log, "%016llX %02X eax=%08X ecx=%08X edx=%08X ebx=%08X esi=%08X edi=%08X\n",
                    (unsigned long long)c->Rip,
                    (unsigned)*(volatile uint8_t *)s_watch_host,
                    g_eax, g_ecx, g_edx, g_ebx, g_esi, g_edi);
        return EXCEPTION_CONTINUE_EXECUTION;
    }
    return EXCEPTION_CONTINUE_SEARCH;
}

/* RECOMP_DIFFTEST_WATCHPLANE=1: every write into the destination plane of the
 * watched call (arg1 .. arg1 + arg3*arg4 -- Bink's C9010) is logged as
 * (host rip, guest address) to planewrites.bin: the plane is made read-only,
 * each write faults, the page is opened for one single-stepped instruction. */
static int s_wp;
static uintptr_t s_wp_lo, s_wp_hi;
static uintptr_t s_wp_open;
static struct { uint64_t rip; uint32_t va, pad; } *s_wp_log;
static size_t s_wp_n, s_wp_cap = 8u << 20;

static LONG CALLBACK dt_wp_veh(PEXCEPTION_POINTERS ep)
{
    DWORD code = ep->ExceptionRecord->ExceptionCode;
    CONTEXT *c = ep->ContextRecord;
    DWORD old;
    if (code == EXCEPTION_ACCESS_VIOLATION && s_wp &&
        ep->ExceptionRecord->ExceptionInformation[0] == 1) {
        uintptr_t a = (uintptr_t)ep->ExceptionRecord->ExceptionInformation[1];
        if (a >= (s_wp_lo & ~(uintptr_t)4095) && a < s_wp_hi) {
            if (s_wp_n < s_wp_cap) {
                s_wp_log[s_wp_n].rip = (uint64_t)c->Rip;
                s_wp_log[s_wp_n].va = (uint32_t)(a - (uintptr_t)xbox_GetMemoryOffset());
                s_wp_n++;
            }
            s_wp_open = a & ~(uintptr_t)4095;
            VirtualProtect((void *)s_wp_open, 4096, PAGE_READWRITE, &old);
            c->EFlags |= 0x100;
            return EXCEPTION_CONTINUE_EXECUTION;
        }
    }
    if (code == EXCEPTION_SINGLE_STEP && s_wp_open) {
        VirtualProtect((void *)s_wp_open, 4096, PAGE_READONLY, &old);
        s_wp_open = 0;
        return EXCEPTION_CONTINUE_EXECUTION;
    }
    return EXCEPTION_CONTINUE_SEARCH;
}

/* RECOMP_DIFFTEST_BATCH=1: test many functions in one run, one at a time.
 * The first call of each function not yet tested (and not listed in
 * RECOMP_DIFFTEST_SKIP, hex VAs one per line) after RECOMP_DIFFTEST_AFTER
 * seconds is snapshotted into RECOMP_DIFFTEST_DIR as above, then
 * <dir>/ready is written (holding the VA). Nothing more is snapshotted until
 * a harness (tools/difftest_batch.py) has emulated it and removed ready;
 * the game runs on meanwhile. A call that has not returned after 30 s (a
 * loop that runs for ever) is given up. */
#define DT_BITS (0x00200000u >> 2)          /* functions start below 2 MB */
static int s_batch;
static uint8_t *s_tested;                   /* bit per 4-byte-aligned... per VA */
static int s_b_state;                       /* 0 idle, 1 in the call, 2 waiting */
static ULONGLONG s_b_since, s_b_check;
static uint32_t s_b_esp;

static int dt_tested(uint32_t va)
{
    return va >= 0x00200000u || (s_tested[va >> 3] >> (va & 7)) & 1;
}
static void dt_mark(uint32_t va)
{
    if (va < 0x00200000u)
        s_tested[va >> 3] |= (uint8_t)(1u << (va & 7));
}

static void dt_batch_init(void)
{
    const char *skip = getenv("RECOMP_DIFFTEST_SKIP");
    FILE *f;
    char line[64];
    int n = 0;
    s_tested = (uint8_t *)calloc(0x00200000u / 8, 1);
    if (!s_tested) { s_batch = 0; return; }
    if (skip && (f = fopen(skip, "r")) != NULL) {
        while (fgets(line, sizeof line, f)) {
            uint32_t va = (uint32_t)strtoul(line, NULL, 16);
            if (va) { dt_mark(va); n++; }
        }
        fclose(f);
    }
    fprintf(stderr, "[DIFFTEST] batch mode, %d functions skipped -> %s\n", n, s_dir);
}

static void dt_dump(const char *tag);

/* 1: snapshot this call (post follows). */
static int dt_batch_pre(uint32_t va)
{
    ULONGLONG now;
    if (s_b_state == 1) {
        if (GetTickCount64() - s_b_since > 30000) {
            fprintf(stderr, "[DIFFTEST] 0x%08X has not returned in 30 s: given up\n", s_va);
            s_b_state = 0;
        }
        return 0;
    }
    if (dt_tested(va))
        return 0;
    now = GetTickCount64();
    if (now - s_start < s_after_ms)
        return 0;
    if (s_b_state == 2) {
        char path[600];
        if (now - s_b_check < 50)
            return 0;
        s_b_check = now;
        snprintf(path, sizeof path, "%s\\ready", s_dir);
        if (GetFileAttributesA(path) != INVALID_FILE_ATTRIBUTES)
            return 0;
        s_b_state = 0;
    }
    /* Two threads can get here at once: one snapshot at a time. */
    {
        static volatile LONG lock;
        if (InterlockedCompareExchange(&lock, 1, 0) != 0)
            return 0;
        if (s_b_state != 0 || dt_tested(va)) {
            InterlockedExchange(&lock, 0);
            return 0;
        }
        s_b_state = 1;
        InterlockedExchange(&lock, 0);
    }
    dt_mark(va);
    s_va = va;
    s_thread = GetCurrentThreadId();
    s_b_esp = g_esp;
    dt_dump("pre");
    s_b_state = 1;
    s_b_since = GetTickCount64();
    return 1;
}

static void dt_batch_post(uint32_t va)
{
    char path[600];
    FILE *f;
    if (s_b_state != 1 || va != s_va || GetCurrentThreadId() != s_thread)
        return;
    dt_dump("post");
    snprintf(path, sizeof path, "%s\\ready", s_dir);
    if ((f = fopen(path, "w")) != NULL) {
        fprintf(f, "%08X\n", va);
        fclose(f);
    }
    s_b_state = 2;
    s_b_check = GetTickCount64();
}

static uint32_t s_trace_va;
static int s_trace_all;
static FILE *s_trace_exit;
static uint32_t s_trace_esp[64];
static int s_trace_depth;
static int s_active;
static FILE *s_trace;

static void dt_dump_range(FILE *f, uint8_t *base, uint32_t lo, uint32_t hi)
{
    uint32_t a = lo;
    while (a < hi) {
        MEMORY_BASIC_INFORMATION mi;
        uint32_t end, n;
        if (!VirtualQuery(base + a, &mi, sizeof mi))
            break;
        end = (uint32_t)((uint8_t *)mi.BaseAddress + mi.RegionSize - base);
        if (end > hi || end <= a)
            end = hi;
        n = end - a;
        if (mi.State == MEM_COMMIT &&
            !(mi.Protect & (PAGE_NOACCESS | PAGE_GUARD)) && mi.Protect) {
            fwrite(&a, 4, 1, f);
            fwrite(&n, 4, 1, f);
            fwrite(base + a, 1, n, f);
        }
        a = end;
    }
}

static void dt_dump(const char *tag)
{
    char path[600];
    FILE *f;
    uint8_t *base = (uint8_t *)xbox_GetMemoryOffset();

    snprintf(path, sizeof path, "%s\\%s-regs.txt", s_dir, tag);
    if ((f = fopen(path, "w")) != NULL) {
        fprintf(f, "eax=%08X\nebx=%08X\necx=%08X\nedx=%08X\nesi=%08X\nedi=%08X\n"
                   "esp=%08X\nva=%08X\nreturn=%08X\nfp_top=%d\n",
                g_eax, g_ebx, g_ecx, g_edx, g_esi, g_edi, g_esp, s_va,
                MEM32(g_esp), g_fp_top);
        /* The x87 state as the recompiled code keeps it (physical registers,
         * doubles): the math helpers take their arguments in ST0. */
        {
            int k;
            for (k = 0; k < 8; k++) {
                uint64_t bits;
                memcpy(&bits, &g_fp_stack[k], 8);
                fprintf(f, "fp%d=%016llX\n", k, (unsigned long long)bits);
            }
            fprintf(f, "fp_cw=%04X\n", (unsigned)g_fp_control_word);
        }
        fclose(f);
    }
    snprintf(path, sizeof path, "%s\\%s-mem.bin", s_dir, tag);
    if ((f = fopen(path, "wb")) != NULL) {
        dt_dump_range(f, base, 0x00000000u, 0x04000000u);
        dt_dump_range(f, base, 0x80000000u, 0x84000000u);
        fclose(f);
    }
}

int recomp_difftest_pre(uint32_t va)
{
    if (!s_init) {
        const char *e = getenv("RECOMP_DIFFTEST_VA");
        const char *n = getenv("RECOMP_DIFFTEST_NTH");
        const char *d = getenv("RECOMP_DIFFTEST_DIR");
        const char *t = getenv("RECOMP_DIFFTEST_AFTER");   /* seconds */
        s_init = 1;
        s_start = GetTickCount64();
        s_after_ms = t ? (ULONGLONG)(atof(t) * 1000.0) : 0;
        s_va = e ? (uint32_t)strtoul(e, NULL, 16) : 0;
        if (n) s_nth = (uint32_t)strtoul(n, NULL, 10);
        {
            const char *tv = getenv("RECOMP_DIFFTEST_TRACE_VA");
            const char *w = getenv("RECOMP_DIFFTEST_WATCH");
            s_wp = getenv("RECOMP_DIFFTEST_WATCHPLANE") != NULL;
            s_watch = w ? (uint32_t)strtoul(w, NULL, 16) : 0;
            s_trace_all = tv && !strcmp(tv, "ALL");
            s_trace_va = tv && !s_trace_all ? (uint32_t)strtoul(tv, NULL, 16) : 0;
        }
        snprintf(s_dir, sizeof s_dir, "%s", d ? d : ".");
        s_batch = getenv("RECOMP_DIFFTEST_BATCH") != NULL;
        if (s_batch)
            dt_batch_init();
        if (s_va)
            fprintf(stderr, "[DIFFTEST] watching 0x%08X, call %u -> %s\n",
                    s_va, s_nth, s_dir);
    }
    /* RECOMP_DIFFTEST_TRACE_VA=ALL: every call made while the watched call
     * runs, as (va, eax..edi, esp, 32 bytes at esp) -- calltrace.bin. */
    if (s_active && s_trace_all && GetCurrentThreadId() == s_thread && s_trace) {
        uint32_t r[8];
        uint8_t *base = (uint8_t *)xbox_GetMemoryOffset();
        r[0] = va; r[1] = g_eax; r[2] = g_ebx; r[3] = g_ecx; r[4] = g_edx;
        r[5] = g_esi; r[6] = g_edi; r[7] = g_esp;
        fwrite(r, 4, 8, s_trace);
        fwrite(base + g_esp, 1, 32, s_trace);
        return 0;
    }
    if (s_active && s_trace_va && va == s_trace_va &&
        GetCurrentThreadId() == s_thread && s_trace) {
        uint32_t r[8];
        uint8_t *base = (uint8_t *)xbox_GetMemoryOffset();
        r[0] = g_eax; r[1] = g_ebx; r[2] = g_ecx; r[3] = g_edx;
        r[4] = g_esi; r[5] = g_edi; r[6] = g_esp; r[7] = 0;
        fwrite(r, 4, 8, s_trace);
        fwrite(base + g_eax, 1, 128, s_trace);
        fwrite(base + g_edx, 1, 256, s_trace);
        fwrite(base + g_esp - 0x1E0, 1, 0x200, s_trace);   /* the callee's frame-to-be */
        if (s_trace_exit && s_trace_depth < 64) {
            s_trace_esp[s_trace_depth++] = g_esp;
            return 1;                   /* post logs the exit state */
        }
        return 0;
    }
    if (s_batch)
        return dt_batch_pre(va);
    if (s_done || !s_va || va != s_va)
        return 0;
    if (GetTickCount64() - s_start < s_after_ms)
        return 0;
    if (++s_count != s_nth)
        return 0;
    s_thread = GetCurrentThreadId();
    dt_dump("pre");
    if (s_trace_va || s_trace_all) {
        char path[600];
        snprintf(path, sizeof path, "%s\\%s", s_dir,
                 s_trace_all ? "calltrace.bin" : "trace.bin");
        s_trace = fopen(path, "wb");
        if (s_trace_va) {
            snprintf(path, sizeof path, "%s\\trace_exit.bin", s_dir);
            s_trace_exit = fopen(path, "wb");
        }
    }
    if (s_watch) {
        char path[600];
        snprintf(path, sizeof path, "%s\\watch.txt", s_dir);
        s_watch_log = fopen(path, "w");
        s_watch_host = (uintptr_t)xbox_GetMemoryOffset() + s_watch;
        if (s_watch_log)
            fprintf(s_watch_log, "watch guest %08X host %016llX image %016llX\n", s_watch,
                    (unsigned long long)s_watch_host,
                    (unsigned long long)(uintptr_t)GetModuleHandleA(NULL));
        AddVectoredExceptionHandler(1, dt_veh);
        RaiseException(0xE0FF0001u, 0, 0, NULL);
    }
    if (s_wp) {
        uintptr_t base = (uintptr_t)xbox_GetMemoryOffset();
        DWORD old;
        uint32_t lo = MEM32(g_esp + 4), n = MEM32(g_esp + 12) * MEM32(g_esp + 16);
        s_wp_log = malloc(s_wp_cap * sizeof *s_wp_log);
        s_wp_lo = base + lo;
        s_wp_hi = (base + lo + n + 4095) & ~(uintptr_t)4095;
        AddVectoredExceptionHandler(1, dt_wp_veh);
        VirtualProtect((void *)(s_wp_lo & ~(uintptr_t)4095),
                       s_wp_hi - (s_wp_lo & ~(uintptr_t)4095), PAGE_READONLY, &old);
    }
    s_active = 1;
    return 1;
}

void recomp_difftest_post(uint32_t va)
{
    if (s_batch) {
        dt_batch_post(va);
        return;
    }
    if (va == s_trace_va && s_trace_depth > 0) {
        /* exit of a traced call: the 8x8 block at arg1 (stride arg2) and the
         * frame below the entry esp, where its temporaries still lie. */
        uint8_t *base = (uint8_t *)xbox_GetMemoryOffset();
        uint32_t e = s_trace_esp[--s_trace_depth];
        uint32_t dst = MEM32(e + 4), stride = MEM32(e + 8), k;
        for (k = 0; k < 8; k++)
            fwrite(base + dst + k * stride, 1, 8, s_trace_exit);
        fwrite(base + e - 0x200, 1, 0x200, s_trace_exit);
        return;
    }
    s_active = 0;
    if (s_wp) {
        DWORD old;
        char path[600];
        FILE *f;
        VirtualProtect((void *)(s_wp_lo & ~(uintptr_t)4095),
                       s_wp_hi - (s_wp_lo & ~(uintptr_t)4095), PAGE_READWRITE, &old);
        s_wp = 0;
        snprintf(path, sizeof path, "%s\\planewrites.bin", s_dir);
        if ((f = fopen(path, "wb")) != NULL) {
            uint64_t img = (uint64_t)(uintptr_t)GetModuleHandleA(NULL);
            fwrite(&img, 8, 1, f);
            fwrite(s_wp_log, sizeof *s_wp_log, s_wp_n, f);
            fclose(f);
        }
        fprintf(stderr, "[DIFFTEST] %zu plane writes logged\n", s_wp_n);
    }
    if (s_watch) {
        RaiseException(0xE0FF0002u, 0, 0, NULL);
        if (s_watch_log) { fclose(s_watch_log); s_watch_log = NULL; }
    }
    if (s_trace) { fclose(s_trace); s_trace = NULL; }
    if (s_trace_exit) { fclose(s_trace_exit); s_trace_exit = NULL; }
    dt_dump("post");
    s_done = 1;
    fprintf(stderr, "[DIFFTEST] 0x%08X call %u dumped (thread %lu)\n", s_va,
            s_nth, (unsigned long)s_thread);
    fflush(stderr);
}

#endif /* RECOMP_DIFFTEST */
