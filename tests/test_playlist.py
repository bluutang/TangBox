import random

import pytest

from nostalgiabox.playlist import ShuffleBag


def test_bag_yields_every_item_once_per_cycle():
    items = list(range(10))
    bag = ShuffleBag(items, random.Random(1))
    drawn = [bag.next() for _ in range(10)]
    assert sorted(drawn) == items  # every item exactly once


def test_bag_reshuffles_after_exhaustion():
    items = list(range(5))
    bag = ShuffleBag(items, random.Random(2))
    two_cycles = [bag.next() for _ in range(10)]
    assert sorted(two_cycles[:5]) == items
    assert sorted(two_cycles[5:]) == items


def test_no_immediate_repeat_across_cycle_boundary():
    items = list(range(6))
    # Try many seeds; none should ever produce a back-to-back repeat.
    for seed in range(200):
        bag = ShuffleBag(items, random.Random(seed))
        seq = [bag.next() for _ in range(30)]
        for a, b in zip(seq, seq[1:]):
            assert a != b, f"immediate repeat with seed {seed}: {seq}"


def test_single_item_bag_repeats():
    bag = ShuffleBag(["only"], random.Random(0))
    assert bag.next() == "only"
    assert bag.next() == "only"


def test_empty_bag():
    bag = ShuffleBag([], random.Random(0))
    assert bag.is_empty
    assert len(bag) == 0


def test_deterministic_with_seed():
    a = ShuffleBag(list(range(8)), random.Random(42))
    b = ShuffleBag(list(range(8)), random.Random(42))
    assert [a.next() for _ in range(16)] == [b.next() for _ in range(16)]


def test_peek_shows_the_next_item_without_handing_it_out():
    bag = ShuffleBag(["a", "b", "c"], random.Random(1))
    assert bag.peek() == bag.next()


def test_peeking_twice_gives_the_same_answer():
    bag = ShuffleBag(["a", "b", "c"], random.Random(1))
    assert bag.peek() == bag.peek()


def test_peek_refills_an_exhausted_bag_rather_than_failing():
    bag = ShuffleBag(["a", "b"], random.Random(1))
    bag.next()
    bag.next()
    assert bag.peek() in ("a", "b")


def test_peeking_an_empty_bag_raises_rather_than_inventing_an_item():
    bag = ShuffleBag([], random.Random(1))
    with pytest.raises(IndexError):
        bag.peek()
