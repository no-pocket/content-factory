from datetime import date, time

import pytest

from app.publication_calendar import local_timestamp, month_grid


def test_calendar_has_full_weeks_and_correct_dates():
    grid = month_grid(2026, 11)
    assert all(len(week) == 7 for week in grid)
    assert sum(day != 0 for week in grid for day in week) == 30
    assert grid[0][-1] == 1


def test_local_time_converts_to_utc_and_rejects_nonexistent_time():
    assert local_timestamp(date(2026, 11, 10), time(12), 'America/Sao_Paulo') == 1794322800
    with pytest.raises(ValueError):
        local_timestamp(date(2026, 3, 8), time(2, 30), 'America/New_York')
