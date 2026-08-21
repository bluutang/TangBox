"""Finding a show's tile picture, and fitting it to a tile."""

from nostalgiabox.artwork import crop_box, tile_image_for


def _episode(tmp_path, show="Rugrats", season="Season 01"):
    ep = tmp_path / "Nick Jr" / show / season / "ep.mp4"
    ep.parent.mkdir(parents=True)
    ep.touch()
    return ep


def test_a_tile_jpg_beside_the_seasons_is_the_shows_picture(tmp_path):
    episode = _episode(tmp_path)
    art = tmp_path / "Nick Jr" / "Rugrats" / "tile.jpg"
    art.touch()
    assert tile_image_for(episode, tmp_path / "Nick Jr") == art


def test_a_png_is_accepted_too(tmp_path):
    episode = _episode(tmp_path)
    art = tmp_path / "Nick Jr" / "Rugrats" / "tile.png"
    art.touch()
    assert tile_image_for(episode, tmp_path / "Nick Jr") == art


def test_jpg_wins_when_both_are_present(tmp_path):
    episode = _episode(tmp_path)
    (tmp_path / "Nick Jr" / "Rugrats" / "tile.png").touch()
    jpg = tmp_path / "Nick Jr" / "Rugrats" / "tile.jpg"
    jpg.touch()
    assert tile_image_for(episode, tmp_path / "Nick Jr") == jpg


def test_a_show_with_no_picture_is_none(tmp_path):
    episode = _episode(tmp_path)
    assert tile_image_for(episode, tmp_path / "Nick Jr") is None


def test_an_episode_loose_in_the_channel_folder_has_no_show_and_no_picture(tmp_path):
    root = tmp_path / "Nick Jr"
    root.mkdir()
    loose = root / "ep.mp4"
    loose.touch()
    assert tile_image_for(loose, root) is None


def test_an_episode_from_somewhere_else_entirely_is_none(tmp_path):
    # An advert, say. Must not raise.
    episode = _episode(tmp_path)
    assert tile_image_for(episode, tmp_path / "Somewhere Else") is None


def test_a_directory_called_tile_jpg_is_not_a_picture(tmp_path):
    episode = _episode(tmp_path)
    (tmp_path / "Nick Jr" / "Rugrats" / "tile.jpg").mkdir()
    assert tile_image_for(episode, tmp_path / "Nick Jr") is None


# -- fitting a picture to the tile ------------------------------------------
# The tile picture is 4:3. Anything else is cropped to fill, centred, because
# letterbox bars inside a tile this small waste the only space a child can use.


def test_a_four_three_picture_is_not_cropped_at_all():
    assert crop_box(1024, 768, 264, 198) == (0, 0, 1024, 768)


def test_a_widescreen_picture_loses_its_sides():
    # 16:9 into 4:3: full height, centred horizontally.
    left, top, right, bottom = crop_box(1920, 1080, 264, 198)
    assert (top, bottom) == (0, 1080)
    assert right - left == 1440
    assert left == 240 and right == 1680


def test_a_tall_picture_loses_its_top_and_bottom():
    left, top, right, bottom = crop_box(600, 900, 264, 198)
    assert (left, right) == (0, 600)
    assert bottom - top == 450
    assert top == 225 and bottom == 675


def test_the_crop_is_never_bigger_than_the_picture():
    for src_w, src_h in ((100, 100), (1920, 1080), (640, 480), (300, 1200)):
        left, top, right, bottom = crop_box(src_w, src_h, 264, 198)
        assert 0 <= left < right <= src_w, (src_w, src_h)
        assert 0 <= top < bottom <= src_h, (src_w, src_h)


def test_the_kept_area_is_always_the_tile_shape():
    for src_w, src_h in ((1920, 1080), (600, 900), (1024, 768), (4000, 100)):
        left, top, right, bottom = crop_box(src_w, src_h, 264, 198)
        assert abs((right - left) / (bottom - top) - 264 / 198) < 0.02
