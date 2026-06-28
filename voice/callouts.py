CALLOUTS = {
    "LOSING_ANGLE": "More throttle — you're losing the angle",
    "SPEED_LOSS": "You're bleeding speed — commit",
    "SNAP_RISK": "Careful — you're on the edge",
}


def get_callout(mistake_type: str) -> str | None:
    return CALLOUTS.get(mistake_type)
