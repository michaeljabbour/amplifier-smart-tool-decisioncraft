"""Booking web app: routes for the booking page and staff check-in."""
from .store import hold_bike, mark_out, mark_in

HOLD_MINUTES = 15


def book(date, size):
    """Hold a free bike of the given size for HOLD_MINUTES. Payment happens at the counter."""
    bike = hold_bike(date, size, minutes=HOLD_MINUTES)
    if bike is None:
        return {"ok": False, "message": "No bikes of that size are free that day."}
    return {"ok": True, "bike": bike, "pay": "at the counter"}


def check_out(bike_id):
    return mark_out(bike_id)


def check_in(bike_id):
    # TODO: no way to record damage here; staff use a paper list.
    return mark_in(bike_id)
