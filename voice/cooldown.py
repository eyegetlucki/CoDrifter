import time

SAME_MISTAKE_COOLDOWN = 5.0   # seconds before repeating the same mistake type
ANY_CALLOUT_COOLDOWN = 2.0    # minimum gap between any two callouts


class CooldownManager:
    def __init__(self):
        self._last_callout_time: float = 0.0
        self._last_per_type: dict[str, float] = {}

    def is_allowed(self, mistake_type: str, is_in_pit: bool, is_engine_running: bool) -> bool:
        if is_in_pit or not is_engine_running:
            return False

        now = time.monotonic()

        if now - self._last_callout_time < ANY_CALLOUT_COOLDOWN:
            return False

        last_for_type = self._last_per_type.get(mistake_type, 0.0)
        if now - last_for_type < SAME_MISTAKE_COOLDOWN:
            return False

        return True

    def record(self, mistake_type: str):
        now = time.monotonic()
        self._last_callout_time = now
        self._last_per_type[mistake_type] = now
