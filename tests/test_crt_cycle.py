"""The CRT intensity cycle: the ladder of looks the INPUT button steps through.

The point of the feature is judging the picture on the actual television, so the
rung built from ``config.yaml`` has to stay reachable - a press must never strand
Brian on a look he cannot get back from without restarting the box.
"""

from nostalgiabox.config import CrtConfig
from nostalgiabox.crt import crt_ladder, write_ladder_shaders

# What config.pi.yaml actually sets, so these tests fail if the shipped middle
# rung ever stops being stronger than SOFT FRAME. Raised with the rest of the
# ladder on 2026-08-25 - every rung read as too subtle on the television.
TUNED = CrtConfig(curvature=0.13, vignette=0.36, scanline_intensity=0.17)


def test_ladder_names_run_from_nothing_to_heavy():
    names = [rung.name for rung in crt_ladder(CrtConfig())]
    assert names == ["NONE", "SOFT FRAME", "GLASS & GRAIN", "HEAVY CRT"]


def test_configured_look_is_the_middle_rung():
    assert crt_ladder(TUNED)[2].crt == TUNED


def test_none_rung_switches_the_shader_off():
    assert crt_ladder(CrtConfig(enabled=True))[0].crt.enabled is False


def test_effect_strengthens_up_the_ladder():
    rungs = crt_ladder(TUNED)
    curvature = [r.crt.curvature for r in rungs[1:]]
    vignette = [r.crt.vignette for r in rungs[1:]]
    assert curvature == sorted(curvature), curvature
    assert vignette == sorted(vignette), vignette


def test_soft_frame_is_gentler_than_the_configured_look():
    rungs = crt_ladder(TUNED)
    assert rungs[1].crt.curvature < rungs[2].crt.curvature
    assert rungs[1].crt.scanline_intensity < rungs[2].crt.scanline_intensity


def test_each_rung_gets_its_own_shader_file(tmp_path):
    paths = write_ladder_shaders(crt_ladder(CrtConfig()), tmp_path)
    assert paths[0] is None, "the NONE rung needs no shader at all"
    assert all(p.is_file() for p in paths[1:])


def test_rungs_do_not_share_a_shader_path(tmp_path):
    paths = write_ladder_shaders(crt_ladder(CrtConfig()), tmp_path)
    written = [p for p in paths if p is not None]
    assert len(set(written)) == len(written), "mpv would serve a cached compile"


def test_each_rung_bakes_in_its_own_numbers(tmp_path):
    paths = write_ladder_shaders(crt_ladder(CrtConfig(curvature=0.04)), tmp_path)
    bodies = [p.read_text() for p in paths if p is not None]
    assert len(set(bodies)) == len(bodies)


# --- the INPUT button, end to end ------------------------------------------

from nostalgiabox.actions import Action, InputEvent  # noqa: E402
from tests.test_app import build_app, send  # noqa: E402


def _banner(player):
    """Whatever text the message banner is currently showing."""
    return " ".join(player.overlays.values())


def test_first_press_steps_up_from_the_configured_look(tmp_path):
    app, player, _ = build_app(tmp_path)
    app.start()
    send(app, Action.CRT_CYCLE)
    assert "HEAVY CRT" in _banner(player)


def test_cycle_wraps_past_the_top_to_nothing(tmp_path):
    app, player, _ = build_app(tmp_path)
    app.start()
    send(app, Action.CRT_CYCLE)   # HEAVY CRT
    send(app, Action.CRT_CYCLE)   # wraps
    assert "NONE" in _banner(player)


def test_four_presses_return_to_the_configured_look(tmp_path):
    app, player, _ = build_app(tmp_path)
    app.start()
    for _ in range(4):
        send(app, Action.CRT_CYCLE)
    assert "GLASS & GRAIN" in _banner(player)


def test_cycling_hands_the_player_a_different_shader(tmp_path):
    app, player, _ = build_app(tmp_path)
    app.start()
    send(app, Action.CRT_CYCLE)
    heavy = player.crt_shader
    send(app, Action.CRT_CYCLE)
    assert heavy is not None
    assert player.crt_shader != heavy


def test_the_none_rung_clears_the_shader_entirely(tmp_path):
    app, player, _ = build_app(tmp_path)
    app.start()
    send(app, Action.CRT_CYCLE)   # HEAVY CRT
    send(app, Action.CRT_CYCLE)   # NONE
    assert player.crt_shader is None


def test_no_rung_blacks_out_the_corners():
    """Vignette has a hard ceiling at 0.5, and passing it fails silently.

    The shader computes `vig = 1 - VIGNETTE * dist2 * 4`, and dist2 reaches
    0.5 in the corners - so 0.5 takes them to exactly black, and beyond it an
    ever-larger ring of the picture clips to nothing. Nothing warns you; the
    corners just quietly stop being picture.
    """
    for rung in crt_ladder(TUNED):
        if not rung.crt.enabled:
            continue
        corner = 1 - rung.crt.vignette * 0.5 * 4
        assert corner > 0.05, f"{rung.name} crushes its corners ({corner:.2f})"
