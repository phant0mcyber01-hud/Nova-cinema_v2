from __future__ import annotations

from pydantic import AliasChoices, BaseModel, Field

from backend.core.config import DATE_PATTERN, TIME_PATTERN


class ShowIn(BaseModel):
    """`session` is accepted as a legacy alias for `start_time`.

    The stage-2 admin UI still posts `session`; stage 4 replaces that form and
    the alias can go with it.  A stray `seats_count` is ignored -- the hall is
    now global, not per screening.
    """

    movie_id: int
    show_date: str = Field(pattern=DATE_PATTERN)
    start_time: str = Field(
        pattern=TIME_PATTERN, validation_alias=AliasChoices("start_time", "session")
    )
    ticket_price: int | None = Field(default=None, ge=1)
    status: str = Field(default="active", pattern=r"^(active|inactive|cancelled)$")


class ShowBulkIn(BaseModel):
    """Create the same set of times across a date range in one call."""

    movie_id: int
    date_from: str = Field(pattern=DATE_PATTERN)
    date_to: str = Field(pattern=DATE_PATTERN)
    times: list[str] = Field(min_length=1, max_length=24)
    ticket_price: int | None = Field(default=None, ge=1)
