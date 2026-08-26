"""The booking window is 8 rolling days: today plus 7 more, recomputed live.

The client's own example: today is Wed 25 Aug, the last selectable day is
1 Sep. That is 8 calendar dates (25,26,27,28,29,30,31,1) -- today counts as
one of the 7 days ahead, not as an extra day on top of them. Nothing is
cached or reset by a cron job: every request reads the cinema's current wall
clock (`cinema_now`), so the window is naturally different tomorrow without
any code path dedicated to "refreshing" it.
"""
from __future__ import annotations

from datetime import timedelta

from tests.conftest import cinema_today


async def test_the_window_is_today_plus_seven_more_days(client):
    response = await client.get("/api/settings")
    assert response.status_code == 200
    data = response.json()
    assert data["booking_days_ahead"] == 8
    expected = [(cinema_today() + timedelta(days=offset)).isoformat() for offset in range(8)]
    assert data["booking_dates"] == expected
    assert len(data["booking_dates"]) == 8


async def test_the_booking_slots_window_agrees_with_the_settings_window(client):
    """`/api/booking/dates` is the screen the viewer actually books from."""
    dates = (await client.get("/api/booking/dates")).json()["dates"]
    settings = (await client.get("/api/settings")).json()
    assert [item["date"] for item in dates] == settings["booking_dates"]


async def test_the_clients_own_worked_example_end_to_end(client, monkeypatch):
    """25 Aug (Wed) -> 1 Sep max, crossing a month boundary -- exactly as asked."""
    from datetime import date, datetime, timedelta as td

    from backend.services import booking as booking_service

    wednesday_25_august = datetime(2027, 8, 25, 12, 0)  # a Wednesday
    monkeypatch.setattr(booking_service, "utcnow", lambda: wednesday_25_august)

    data = (await client.get("/api/settings")).json()
    assert data["booking_dates"][0] == "2027-08-25"
    assert data["booking_dates"][-1] == "2027-09-01"
    assert len(data["booking_dates"]) == 8


async def test_the_window_rolls_forward_exactly_one_day_at_a_time(client, monkeypatch):
    """The defining behaviour: 24h later, yesterday's first day is gone and a
    new last day has appeared -- with no admin action, no cron, no cache to bust.
    """
    from datetime import datetime

    from backend.services import booking as booking_service

    day_one = datetime(2027, 8, 25, 9, 0)
    monkeypatch.setattr(booking_service, "utcnow", lambda: day_one)
    first = (await client.get("/api/settings")).json()["booking_dates"]

    day_two = datetime(2027, 8, 26, 9, 0)
    monkeypatch.setattr(booking_service, "utcnow", lambda: day_two)
    second = (await client.get("/api/settings")).json()["booking_dates"]

    assert second[0] == first[1], "today becomes what was tomorrow"
    assert second[0] not in [first[0]], "yesterday's first day is no longer offered"
    assert second[-1] == "2027-09-02", "a new day appears at the far end"
    assert len(first) == len(second) == 8
