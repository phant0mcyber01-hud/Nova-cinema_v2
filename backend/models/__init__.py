"""Importing this package registers every table on Base.metadata."""
from backend.models.booking import AdminNotification, Booking
from backend.models.movie import Movie, Review
from backend.models.settings import Bonus, CinemaSettings, GalleryImage, Melody
from backend.models.show import SeatHold, Show
from backend.models.slot import CapacityHold, SlotTemplate
from backend.models.user import Favorite, User, UserNotification

__all__ = [
    "AdminNotification",
    "Bonus",
    "Booking",
    "CapacityHold",
    "CinemaSettings",
    "Favorite",
    "GalleryImage",
    "Melody",
    "Movie",
    "Review",
    "SeatHold",
    "Show",
    "SlotTemplate",
    "User",
    "UserNotification",
]
