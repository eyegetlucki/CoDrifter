import random

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


def get_callout(mistake_type: str) -> str | None:
    options = CALLOUTS.get(mistake_type)
    return random.choice(options) if options else None
