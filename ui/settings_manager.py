import json
import os

SETTINGS_PATH = os.path.join("data", "settings.json")

DEFAULTS = {
    "coach_enabled": False,
    "voice_volume": 80,
    "voice_id": "",
    "confidence_threshold": 90,
    "same_mistake_cooldown": 5,
    "any_callout_cooldown": 2,
    "corner_approach_enabled": True,
    "auto_debrief": True,
    "mistake_callouts": {
        "LOSING_ANGLE": True,
        "SPEED_LOSS": True,
        "SNAP_RISK": True,
    },
}


class SettingsManager:
    def __init__(self):
        self._data: dict = {}
        self.load()

    def load(self):
        if os.path.exists(SETTINGS_PATH):
            try:
                with open(SETTINGS_PATH) as f:
                    saved = json.load(f)
                self._data = {**DEFAULTS, **saved}
                # Deep merge mistake_callouts
                if "mistake_callouts" in saved:
                    self._data["mistake_callouts"] = {
                        **DEFAULTS["mistake_callouts"],
                        **saved["mistake_callouts"],
                    }
                return
            except Exception:
                pass
        self._data = dict(DEFAULTS)
        self._data["mistake_callouts"] = dict(DEFAULTS["mistake_callouts"])

    def save(self):
        os.makedirs(os.path.dirname(SETTINGS_PATH), exist_ok=True)
        with open(SETTINGS_PATH, "w") as f:
            json.dump(self._data, f, indent=2)

    def get(self, key: str, default=None):
        return self._data.get(key, default)

    def set(self, key: str, value):
        self._data[key] = value
        self.save()

    def get_mistake_callout(self, mistake_type: str) -> bool:
        return self._data.get("mistake_callouts", {}).get(mistake_type, True)

    def set_mistake_callout(self, mistake_type: str, enabled: bool):
        self._data.setdefault("mistake_callouts", {})[mistake_type] = enabled
        self.save()

    def reset_to_defaults(self):
        self._data = dict(DEFAULTS)
        self._data["mistake_callouts"] = dict(DEFAULTS["mistake_callouts"])
        self.save()
