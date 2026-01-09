# UniFi LCM Screensaver / Particle Flow (Reverse Engineered)

## Overview

This project documents and reproduces the flow by which UniFi LCM devices arrive at their animated
particle-based screensaver state. The screensaver is the final rendering output of a multi-stage
pipeline that begins with device state evaluation and ends with real-time particle animation.

The implementation is derived from reverse-engineering observed LCM behavior rather than official
documentation.

---

## High-Level Flow
Device State → LCM Runtime → Animation State → Particle System → Screensaver Output


Only when states 1–3 are inactive does the idle path activate.

---

### 3. Animation State Resolution
Once idle is selected:
- A base animation profile is loaded
- Global parameters are initialized:
  - Tick rate
  - Color palette
  - Brightness constraints
  - Motion bounds

This layer does **not** render pixels directly. It defines the rules the particle system must follow.

---

### 4. Particle System Generation
The animation state drives a particle engine:
- Particles are spawned pseudo-randomly within bounds
- Each particle has:
  - Position
  - Velocity
  - Lifetime
  - Intensity / color
- Motion is smooth and non-linear to avoid mechanical appearance

Particles evolve deterministically based on:
- Time delta
- Seeded randomness
- Boundary conditions

---

### 5. Rendering and Output (Screensaver)
The particle system is rasterized to the LCM LED matrix:
- Particle intensity maps to LED brightness
- Overlapping particles blend additively
- Frame updates occur at a fixed cadence

This rendered output **is the screensaver**.

No additional “screensaver mode” exists — the particles are simply the lowest-priority visual
expression of the system.

---

## Key Design Characteristics

- **State-driven, not event-driven**
- **Deterministic but visually organic**
- **Idle as a derived condition**
- **Particles as an abstraction layer**, not a visual gimmick

---

## Why Particles?

Particles provide:
- Continuous motion without semantic meaning
- Low cognitive load
- Graceful degradation across LED resolutions
- Easy parameterization without new assets

This makes them ideal as an idle visualization.

---

## End Result

The screensaver is the natural end state of the LCM visual pipeline when:
- No alerts exist
- No status animations are required
- No user interaction is detected

At that point, the particle system becomes the sole renderer.

---

## Disclaimer

This project is based on observational reverse engineering of UniFi LCM behavior.
It is not affiliated with or endorsed by Ubiquiti.
