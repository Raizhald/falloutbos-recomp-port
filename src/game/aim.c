/*
 * Mouse aim: the player turns toward the mouse pointer.
 *
 * The toolkit's mouse+keyboard layer (mouse = cursor in mkb.ini) reports
 * where the pointer is in the window every time the title polls the pad;
 * this turns that into a facing for player 1, written straight into the
 * player object, so attacks, shots and throws go toward the pointer.
 *
 * What the title keeps where (Carbon, found by diffing RAM dumps taken while
 * turning the player and the camera -- RECOMP_MEMDUMP_DIR + menu_peek.py):
 *   0x005502E8  player 1's controller -> its player object (and the object
 *               points back to the controller, 0x00550060, at +0xD8)
 *   object+0xE0 position x, y, z (z is height)
 *   object+0xF0 facing, 16-bit binary angle in the low half: the facing
 *               vector is (cos a, sin a), a = facing * 2pi / 65536
 *   0x00550470  the controller's last movement direction (cos, sin)
 *   0x0027E6B0  camera rotation, 3x3, and +0x24 its translation: a world
 *               point p is at v = p * R + t in view space (x right, y down,
 *               z forward)
 *   0x005D4250  vertical field of view, degrees (sub_00086980)
 * The pointer goes back through the camera onto the ground plane at the
 * player's height; the facing is the direction from the player to there.
 *
 * When: while attacking (the attack bindings are held), and when the
 * pointer has moved and the player is not walking -- walking keeps the
 * game's own facing (the way you walk), so movement still feels like the
 * pad. RECOMP_AIM=0 turns it off.
 */
#include <math.h>
#include <stdlib.h>
#include <string.h>
#include <stdio.h>

#include "recomp_types.h"
#include "../input/mkb_input.h"

#define CTL_PLAYER1   0x005502E8u
#define CTL_BASE      0x00550060u
#define CTL_MOVE_DIR  0x00550470u
#define CAM_ROT       0x0027E6B0u
#define CAM_TRANS     0x0027E6D4u
#define CAM_FOV_DEG   0x005D4250u
#define OBJ_CTL       0xD8u
#define OBJ_POS       0xE0u
#define OBJ_FACING    0xF0u

float fbos_ws_factor(void);             /* recomp_manual.c */

static int s_force = -1;                /* RECOMP_MKB_CURSOR_TEST: always aim */

static int ok_va(uint32_t va) { return va >= 0x00010000u && va < 0x03FF0000u; }

/* Ground point under the pointer; 0 when it does not meet the ground. */
static int pointer_ground(float x, float y, float aspect, float pz, float out[2])
{
    float ws = fbos_ws_factor();
    float pa = 4.0f / 3.0f * ws;        /* the picture's shape */
    float nx, ny, ty, tx, d[3], e[3], s;
    int i;

    /* The picture is centred in the window with bars on two sides. */
    if (aspect > pa)
        x = (x - 0.5f) * aspect / pa + 0.5f;
    else
        y = (y - 0.5f) * pa / aspect + 0.5f;
    nx = (x * 2.0f - 1.0f) * ws;        /* in units of the 4:3 half-width */
    ny = y * 2.0f - 1.0f;               /* down */
    {
        float fov = MEMF(CAM_FOV_DEG);
        if (!(fov > 10.0f && fov < 150.0f))
            fov = 52.0f;
        ty = tanf(fov * 0.5f * 3.14159265f / 180.0f);
        tx = ty * 4.0f / 3.0f;
    }
    for (i = 0; i < 3; i++) {
        const uint32_t row = CAM_ROT + (uint32_t)i * 12u;
        d[i] = MEMF(row) * nx * tx + MEMF(row + 4) * ny * ty + MEMF(row + 8);
        e[i] = -(MEMF(CAM_TRANS) * MEMF(row) + MEMF(CAM_TRANS + 4) * MEMF(row + 4)
                 + MEMF(CAM_TRANS + 8) * MEMF(row + 8));
    }
    if (!(d[2] < -1e-4f))
        return 0;                       /* the ray does not go down */
    s = (pz - e[2]) / d[2];
    if (!(s > 0.0f && s < 1e6f))
        return 0;
    out[0] = e[0] + s * d[0];
    out[1] = e[1] + s * d[1];
    return 1;
}

static void aim_hook(int active, float x, float y, float aspect)
{
    static float last_x = -1.0f, last_y = -1.0f;
    static int moved_frames;
    static uint32_t stable_obj;
    static int stable;
    uint32_t obj;
    float hit[2], dx, dy, a;
    int attacking, walking;

    if (!active) {
        last_x = last_y = -1.0f;
        return;
    }
    obj = MEM32(CTL_PLAYER1);
    if (!ok_va(obj) || MEM32(obj + OBJ_CTL) != CTL_BASE) {
        stable = 0;
        return;                         /* no player (menus, loading) */
    }
    /* Nothing is written until the same player object has been there for
     * two seconds of polls: a level that is still loading is left alone. */
    if (obj != stable_obj) {
        stable_obj = obj;
        stable = 0;
    }
    if (stable < 120) {
        stable++;
        return;
    }
    {
        float px = MEMF(obj + OBJ_POS), py = MEMF(obj + OBJ_POS + 4);
        if (!(fabsf(px) < 1e6f && fabsf(py) < 1e6f))
            return;
    }

    if (fabsf(x - last_x) > 0.002f || fabsf(y - last_y) > 0.002f)
        moved_frames = 90;              /* ~1.5 s after the pointer moves */
    else if (moved_frames > 0)
        moved_frames--;
    last_x = x;
    last_y = y;
    attacking = mkb_target_held("a") || mkb_target_held("b");
    walking = mkb_target_held("lup") || mkb_target_held("ldown")
           || mkb_target_held("lleft") || mkb_target_held("lright");
    if (mkb_target_held("rt"))
        return;                         /* target lock: the game aims */
    if (!s_force && !attacking && (walking || moved_frames <= 0))
        return;

    if (!pointer_ground(x, y, aspect, MEMF(obj + OBJ_POS + 8), hit))
        return;
    dx = hit[0] - MEMF(obj + OBJ_POS);
    dy = hit[1] - MEMF(obj + OBJ_POS + 4);
    if (dx * dx + dy * dy < 4.0f)
        return;                         /* pointer on the player */
    a = atan2f(dy, dx);
    {
        uint32_t f = MEM32(obj + OBJ_FACING);
        uint32_t bam = (uint32_t)lroundf(a * 65536.0f / 6.28318531f) & 0xFFFFu;
        MEM32(obj + OBJ_FACING) = (f & 0xFFFF0000u) | bam;
        if (!walking) {
            MEMF(CTL_MOVE_DIR) = cosf(a);
            MEMF(CTL_MOVE_DIR + 4) = sinf(a);
        }
    }
}

void fbos_aim_init(void)
{
    const char *e = getenv("RECOMP_AIM");
    if (e && *e == '0')
        return;
    s_force = getenv("RECOMP_MKB_CURSOR_TEST") != NULL;
    mkb_set_cursor_hook(aim_hook);
}
