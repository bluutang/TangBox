"""The player's picture layer, as far as it can be checked off a Raspberry Pi.

What the pictures LOOK like needs a television. What can be checked anywhere is
that the right file is asked for, at the right place, and that the layer is
emptied when the guide goes away.
"""

from pathlib import Path

from nostalgiabox.player import MockPlayer, Player


class _OldPlayer(Player):
    """A player written before the picture layer existed."""

    def play(self, path, *, start=0.0): ...
    def play_loop(self, path): ...
    def stop(self): ...
    def set_volume(self, volume): ...
    def set_mute(self, muted): ...
    def get_time_pos(self): return None
    def show_text(self, text, duration): ...
    def set_overlay(self, overlay_id, ass, res_x, res_y): ...
    def clear_overlay(self, overlay_id): ...
    def close(self): ...


def test_a_player_that_cannot_draw_pictures_ignores_them_quietly():
    # show_image is concrete with a no-op default, not abstract. Making it
    # abstract would stop a player like this one being instantiated at all.
    player = _OldPlayer()
    player.show_image(0, Path("tile.jpg"), 0, 0, 264, 198)
    player.clear_images()


def test_the_mock_records_where_a_picture_was_put():
    player = MockPlayer()
    player.show_image(3, Path("/media/Rugrats/tile.jpg"), 76, 43, 264, 198)
    assert player.images[3] == (Path("/media/Rugrats/tile.jpg"), 76, 43, 264, 198)


def test_clearing_empties_the_whole_picture_layer():
    player = MockPlayer()
    player.show_image(0, Path("a.jpg"), 0, 0, 10, 10)
    player.show_image(1, Path("b.jpg"), 0, 0, 10, 10)
    player.clear_images()
    assert player.images == {}


def test_drawing_over_a_slot_replaces_what_was_there():
    player = MockPlayer()
    player.show_image(0, Path("a.jpg"), 0, 0, 10, 10)
    player.show_image(0, Path("b.jpg"), 5, 5, 20, 20)
    assert player.images == {0: (Path("b.jpg"), 5, 5, 20, 20)}


def test_clearing_an_already_empty_layer_is_harmless():
    player = MockPlayer()
    player.clear_images()
    player.clear_images()
    assert player.images == {}
