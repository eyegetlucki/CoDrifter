import random
from collections import deque

CALLOUTS = {
    "LOSING_ANGLE": [
        "More throttle — you're losing the angle",
        "Keep it sideways — add throttle",
        "Don't let it straighten — more gas",
        "Angle's dying — push the throttle",
    ],
    "SPEED_LOSS": [
        "You're bleeding speed — commit",
        "Too much scrub — get on the throttle",
        "Speed's dropping — drive it out",
        "Losing momentum — commit to the exit",
    ],
    "SNAP_RISK": [
        "Careful — you're on the edge",
        "Easy — she's about to snap",
        "Watch it — too much rotation",
        "Back off — you're going to spin",
    ],
}


_recent: deque[str] = deque(maxlen=3)  # anti-repeat: no mistake line repeats within 3 callouts


def get_callout(mistake_type: str) -> str | None:
    options = CALLOUTS.get(mistake_type)
    if not options:
        return None
    fresh = [o for o in options if o not in _recent]
    choice = random.choice(fresh) if fresh else random.choice(options)
    _recent.append(choice)
    return choice
