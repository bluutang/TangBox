"""Generate the CRT picture effect as an mpv GLSL user shader.

Old kids' shows were made for 4:3 tube TVs, so to sell the nostalgia we bend the
picture the way a real CRT did: a gentle barrel "bulge", rounded corners, a soft
vignette toward the edges, and faint scanlines. mpv applies this as a GLSL user
shader on the video plane (the 4:3 image stays pillar-boxed inside the frame).

The shader is written out with the numbers from :class:`~nostalgiabox.config.CrtConfig`
baked in, so it is fully tunable from ``config.yaml`` without editing GLSL. If the
shader ever fails to compile on a given GPU, mpv simply logs it and keeps
playing - the effect is cosmetic and never blocks playback.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path

from .config import CrtConfig

log = logging.getLogger(__name__)

# mpv/libplacebo user-shader ("hook") template. Hooks the MAIN video plane and
# remaps texture coordinates for the curvature, then masks/rounds/shades.
_SHADER_TEMPLATE = """//!HOOK MAIN
//!BIND HOOKED
//!DESC nostalgiabox CRT (curvature + rounded corners + vignette + scanlines)

// Tunables baked in from config.yaml
#define CURVATURE {curvature:.5f}
#define CORNER_RADIUS {corner_radius:.5f}
#define VIGNETTE {vignette:.5f}
#define SCANLINES {scanlines}
#define SCAN_INTENSITY {scanline_intensity:.5f}

vec4 hook() {{
    vec2 uv = HOOKED_pos;
    vec2 cc = uv - 0.5;
    float dist2 = dot(cc, cc);

    // Barrel distortion: push pixels outward with distance from centre.
    vec2 warped = uv + cc * dist2 * CURVATURE;

    // Rounded-rectangle mask over the (warped) frame, anti-aliased at the edge.
    vec2 p = warped - 0.5;
    vec2 d = abs(p) - (vec2(0.5) - CORNER_RADIUS);
    float outside = length(max(d, vec2(0.0))) - CORNER_RADIUS;
    float aa = 1.5 / max(HOOKED_size.x, HOOKED_size.y);
    float mask = 1.0 - smoothstep(0.0, aa, outside);
    if (mask <= 0.0)
        return vec4(0.0, 0.0, 0.0, 1.0);

    vec4 col = HOOKED_tex(clamp(warped, 0.0, 1.0));

    // Vignette: darken toward the edges/corners.
    float vig = clamp(1.0 - VIGNETTE * dist2 * 4.0, 0.0, 1.0);
    col.rgb *= vig;

    // Scanlines: subtle horizontal darkening at the source line pitch.
    if (SCANLINES > 0) {{
        float s = 0.5 + 0.5 * cos(warped.y * HOOKED_size.y * 3.14159265);
        col.rgb *= 1.0 - SCAN_INTENSITY * s;
    }}

    col.rgb *= mask;
    return col;
}}
"""


@dataclass(frozen=True)
class CrtPreset:
    """One rung of the intensity ladder: a name to flash, and the look itself."""

    name: str
    crt: CrtConfig


# The fixed reference rungs. HEAVY CRT is deliberately the old CrtConfig
# defaults - the look the box shipped with before it was tuned down - so
# "heavy" means a real thing somebody once chose, not an invented number.
_SOFT_FRAME = CrtConfig(
    curvature=0.02, corner_radius=0.06, vignette=0.10,
    scanlines=True, scanline_intensity=0.015,
)
_HEAVY_CRT = CrtConfig(
    curvature=0.12, corner_radius=0.065, vignette=0.25,
    scanlines=True, scanline_intensity=0.12,
)

#: Which rung `config.yaml` occupies. The box starts here.
CONFIG_RUNG = 2


def crt_ladder(configured: CrtConfig) -> tuple[CrtPreset, ...]:
    """The looks the INPUT button steps through, gentlest first.

    The configured look is a rung in its own right rather than merely the
    starting point, so it is always one press away. Being stranded on a look
    you cannot get back from without restarting the box would make the feature
    worse than useless on a sofa.
    """
    return (
        CrtPreset("NONE", CrtConfig(enabled=False)),
        CrtPreset("SOFT FRAME", _SOFT_FRAME),
        CrtPreset("GLASS & GRAIN", configured),
        CrtPreset("HEAVY CRT", _HEAVY_CRT),
    )


def render_shader(crt: CrtConfig) -> str:
    return _SHADER_TEMPLATE.format(
        curvature=crt.curvature,
        corner_radius=crt.corner_radius,
        vignette=crt.vignette,
        scanlines=1 if crt.scanlines else 0,
        scanline_intensity=crt.scanline_intensity,
    )


def write_ladder_shaders(
    ladder: tuple[CrtPreset, ...], out_dir: Path
) -> tuple[Path | None, ...]:
    """Write one shader file per rung, returning a path for each.

    Every rung gets its OWN filename. mpv keys its compiled-shader cache on the
    path, so reusing one filename and rewriting it would leave the picture
    unchanged when the look is switched - the bug this shape avoids.
    """
    paths: list[Path | None] = []
    for index, rung in enumerate(ladder):
        paths.append(write_shader(rung.crt, out_dir / f"crt-{index}.glsl"))
    return tuple(paths)


def default_shader_path() -> Path:
    """A stable, writable location to cache the generated shader."""
    cache_home = os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache")
    return Path(cache_home) / "nostalgiabox" / "crt.glsl"


def write_shader(crt: CrtConfig, out_path: Path | None = None) -> Path | None:
    """Write the shader for ``crt`` and return its path (or None if disabled)."""
    if not crt.enabled:
        return None
    out_path = out_path or default_shader_path()
    try:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(render_shader(crt), encoding="utf-8")
        return out_path
    except OSError:
        log.warning("could not write CRT shader; continuing without it", exc_info=True)
        return None


__all__ = [
    "CrtPreset",
    "crt_ladder",
    "write_ladder_shaders",
    "CONFIG_RUNG",
    "render_shader",
    "write_shader",
    "default_shader_path",
]
