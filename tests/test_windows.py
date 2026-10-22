import itertools
from datetime import UTC, datetime, timedelta

import pytest

from market_data.windows import split_into_windows

START = datetime(2026, 10, 1, tzinfo=UTC)


def hours(n: int) -> timedelta:
    return timedelta(hours=n)


def test_720_hours_become_three_windows():
    windows = split_into_windows(START, START + hours(720))
    sizes = [(end - start) // hours(1) for start, end in windows]
    assert sizes == [300, 300, 120]


def test_windows_are_contiguous_and_cover_the_whole_range():
    end = START + hours(720)
    windows = split_into_windows(START, end)
    assert windows[0][0] == START
    assert windows[-1][1] == end
    for (_, previous_end), (next_start, _) in itertools.pairwise(windows):
        assert previous_end == next_start


def test_short_range_is_a_single_window():
    assert split_into_windows(START, START + hours(10)) == [(START, START + hours(10))]


def test_exactly_300_hours_is_a_single_window():
    assert len(split_into_windows(START, START + hours(300))) == 1


def test_empty_range_returns_no_windows():
    assert split_into_windows(START, START) == []


def test_naive_datetime_is_rejected():
    naive = datetime(2026, 10, 1)
    with pytest.raises(ValueError):
        split_into_windows(naive, naive + hours(5))
