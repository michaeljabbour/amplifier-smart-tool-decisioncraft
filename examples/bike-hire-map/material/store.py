"""In-memory store of bikes and holds."""
BIKES = {"S1": "small", "M1": "medium", "M2": "medium", "L1": "large"}
HOLDS = {}
STATUS = {}


def hold_bike(date, size, minutes):
    for bike, s in BIKES.items():
        if s == size and (date, bike) not in HOLDS:
            HOLDS[(date, bike)] = minutes
            return bike
    return None


def mark_out(bike):
    STATUS[bike] = "out"
    return True


def mark_in(bike):
    STATUS[bike] = "in"
    return True
