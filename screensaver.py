import math
import random
import time
from dataclasses import dataclass
from typing import List, Tuple

import pygame

# --- RE constants ---
PERIOD = 2500
PHASE_MAX = 0x7FFF
POOL_SIZE = 250
FPS = 60

# Adjust to your UniFi LCM resolution if known
WIDTH, HEIGHT = 240, 240
CENTER_X, CENTER_Y = WIDTH // 2, HEIGHT // 2

BLACK = 0xFF000000

# From sub_8039BD8: v32 = [-16744705, -16776961, -10615924]
# Convert signed -> unsigned ARGB32 by masking.
PALETTE = [(-16744705) & 0xFFFFFFFF, (-16776961) & 0xFFFFFFFF, (-10615924) & 0xFFFFFFFF]


def argb_to_rgba(argb: int) -> Tuple[int, int, int, int]:
    argb &= 0xFFFFFFFF
    a = (argb >> 24) & 0xFF
    r = (argb >> 16) & 0xFF
    g = (argb >> 8) & 0xFF
    b = argb & 0xFF
    return r, g, b, a


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def clamp01(t: float) -> float:
    if t < 0.0:
        return 0.0
    if t > 1.0:
        return 1.0
    return t


def blend_argb(c0: int, c1: int, t: float) -> int:
    """Approximation of sub_804B470: linear interpolate ARGB channels."""
    t = clamp01(t)
    r0, g0, b0, a0 = argb_to_rgba(c0)
    r1, g1, b1, a1 = argb_to_rgba(c1)
    r = int(lerp(r0, r1, t))
    g = int(lerp(g0, g1, t))
    b = int(lerp(b0, b1, t))
    a = int(lerp(a0, a1, t))
    return ((a & 0xFF) << 24) | ((r & 0xFF) << 16) | ((g & 0xFF) << 8) | (b & 0xFF)


@dataclass
class Particle:
    # current
    x: float
    y: float
    size: int
    color: int

    # endpoints
    x0: float
    y0: float
    x1: float
    y1: float

    # timing
    t0: int
    t1: int
    t2: int
    t3: int

    # palette color
    color_alt: int


def rand_int(lo: int, hi: int) -> int:
    if hi < lo:
        lo, hi = hi, lo
    return random.randint(lo, hi)


def choose_next_time(prev: int) -> int:
    # Mirrors sub_8039B3C usage: pick within [prev..prev+2500]
    return rand_int(prev, prev + PERIOD)


def spawn_particle() -> Particle:
    radius = rand_int(70, 90)
    angle_deg = rand_int(1, 360)
    theta = angle_deg * math.pi / 180.0

    x0 = CENTER_X + radius * math.cos(theta)
    y0 = CENTER_Y + radius * math.sin(theta)

    x1 = rand_int(int(x0) - 70, int(x0) + 70)
    y1 = rand_int(int(y0) - 70, int(y0) + 70)

    # keep on-screen (firmware may clip elsewhere; this matches typical LCM look)
    x0 = max(0, min(WIDTH - 1, x0))
    y0 = max(0, min(HEIGHT - 1, y0))
    x1 = max(0, min(WIDTH - 1, x1))
    y1 = max(0, min(HEIGHT - 1, y1))

    size = rand_int(1, max(1, radius // 20))

    t0 = rand_int(1, PERIOD)
    t1 = choose_next_time(t0)
    t2 = choose_next_time(t1)
    t3 = choose_next_time(t2)

    color_alt = PALETTE[rand_int(0, 2)]

    return Particle(
        x=x0, y=y0, size=size, color=BLACK,
        x0=x0, y0=y0, x1=x1, y1=y1,
        t0=t0, t1=t1, t2=t2, t3=t3,
        color_alt=color_alt,
    )


def phase_to_tick(phase: int) -> int:
    return int(PERIOD * phase / float(PHASE_MAX))


def update_wrap_and_expire(particles: List[Particle]) -> List[Particle]:
    # Mirrors sub_8039D44 wrap behavior
    out: List[Particle] = []
    for p in particles:
        if p.t3 <= PERIOD:
            continue
        p.t0 -= PERIOD
        p.t1 -= PERIOD
        p.t2 -= PERIOD
        p.t3 -= PERIOD
        out.append(p)
    return out


def envelope_color(p: Particle, tick: int) -> int:
    if tick < p.t0:
        return BLACK
    if tick > p.t3:
        return BLACK

    # fade-in: black -> alt
    if tick <= p.t1 and p.t1 != p.t0:
        t = (tick - p.t0) / float(p.t1 - p.t0)
        return blend_argb(BLACK, p.color_alt, t)

    # fade-out: alt -> black
    if tick >= p.t2 and p.t3 != p.t2:
        t = (tick - p.t2) / float(p.t3 - p.t2)
        return blend_argb(p.color_alt, BLACK, t)

    # plateau
    return p.color_alt


def interp_pos(p: Particle, tick: int) -> Tuple[float, float]:
    if tick <= p.t0:
        return p.x0, p.y0
    if tick >= p.t3:
        return p.x1, p.y1
    denom = (p.t3 - p.t0) or 1
    t = (tick - p.t0) / float(denom)
    return lerp(p.x0, p.x1, t), lerp(p.y0, p.y1, t)


def draw_particle(screen: pygame.Surface, p: Particle):
    r, g, b, a = argb_to_rgba(p.color)
    if a == 0:
        return

    radius = max(1, p.size)

    # alpha-safe draw via small SRCALPHA surface
    surf = pygame.Surface((radius * 2 + 1, radius * 2 + 1), pygame.SRCALPHA)
    pygame.draw.circle(surf, (r, g, b, a), (radius, radius), radius)
    screen.blit(surf, (int(p.x) - radius, int(p.y) - radius))


def main():
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("UniFi LCM Screensaver (RE-based replica)")

    clock = pygame.time.Clock()

    particles: List[Particle] = [spawn_particle() for _ in range(POOL_SIZE)]
    prev_phase = 0
    start = time.perf_counter()

    # If your device leaves trails, set this True and tune fade_alpha (0..255)
    trails = False
    fade_alpha = 24
    trail_layer = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)

    running = True
    while running:
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                running = False
            elif ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE:
                running = False

        # Sawtooth phase; tune cycle_seconds to match on-device speed
        elapsed = time.perf_counter() - start
        cycle_seconds = 1.0
        frac = (elapsed % cycle_seconds) / cycle_seconds
        phase = int(frac * PHASE_MAX)

        if prev_phase > phase:
            particles = update_wrap_and_expire(particles)
        prev_phase = phase

        tick = phase_to_tick(phase)

        while len(particles) < POOL_SIZE:
            particles.append(spawn_particle())

        # Update
        for p in particles:
            p.color = envelope_color(p, tick)
            p.x, p.y = interp_pos(p, tick)

        # Render
        if trails:
            # fade previous frame slightly
            trail_layer.fill((0, 0, 0, fade_alpha))
            screen.blit(trail_layer, (0, 0), special_flags=pygame.BLEND_RGBA_SUB)
        else:
            screen.fill((0, 0, 0))

        for p in particles:
            if p.color != BLACK:
                draw_particle(screen, p)

        pygame.display.flip()
        clock.tick(FPS)

    pygame.quit()


if __name__ == "__main__":
    main()
