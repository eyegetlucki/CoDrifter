import os
import threading
import queue
from dotenv import load_dotenv
from elevenlabs.client import ElevenLabs
from elevenlabs import play

from voice.callouts import get_callout
from voice.cooldown import CooldownManager
from voice.approach import CornerApproachDetector

load_dotenv()

VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID")
MODEL_ID = "eleven_flash_v2_5"


class VoiceCoach:
    def __init__(self, enabled: bool = False, same_mistake_cooldown: float = 5.0,
                 any_callout_cooldown: float = 2.0, approach_enabled: bool = True,
                 enabled_mistakes: dict | None = None):
        self._client = ElevenLabs(api_key=os.getenv("ELEVENLABS_API_KEY"))
        self._cooldown = CooldownManager(same_mistake_cooldown, any_callout_cooldown)
        self._approach = CornerApproachDetector()
        self._queue: queue.Queue = queue.Queue(maxsize=1)
        self._thread = threading.Thread(target=self._worker, daemon=True)
        self._thread.start()
        self.enabled: bool = enabled
        self.approach_enabled: bool = approach_enabled
        self._track_slug: str = ""
        self.enabled_mistakes: dict = enabled_mistakes or {
            "LOSING_ANGLE": True, "SPEED_LOSS": True, "SNAP_RISK": True,
        }

    def load_corner_map(self, track_slug: str = ""):
        self._track_slug = track_slug
        self._approach.load(track_slug)

    def update_settings(self, same_mistake_cooldown: float, any_callout_cooldown: float,
                        approach_enabled: bool, enabled_mistakes: dict):
        self._cooldown.update_cooldowns(same_mistake_cooldown, any_callout_cooldown)
        self.approach_enabled = approach_enabled
        self.enabled_mistakes = enabled_mistakes

    def _speak(self, text: str):
        audio = self._client.text_to_speech.convert(
            voice_id=VOICE_ID,
            text=text,
            model_id=MODEL_ID,
            output_format="mp3_44100_128",
        )
        play(audio)

    def _worker(self):
        while True:
            item = self._queue.get()
            if item is None:
                break
            try:
                self._speak(item)
            except Exception as e:
                print(f"\n[voice] Error: {e}")
            finally:
                self._queue.task_done()

    def call_out(self, mistake_type: str, is_in_pit: bool, is_engine_running: bool):
        if not self.enabled:
            return
        if not self.enabled_mistakes.get(mistake_type, True):
            return
        if not self._cooldown.is_allowed(mistake_type, is_in_pit, is_engine_running):
            return

        text = get_callout(mistake_type)
        if not text:
            return

        self._cooldown.record(mistake_type)

        try:
            self._queue.put_nowait(text)
        except queue.Full:
            pass

    def is_in_corner(self, x: float, z: float) -> bool:
        return self._approach.is_in_corner(x, z)

    def check_exit(self, x: float, z: float, speed_kmh: float, is_in_pit: bool, is_engine_running: bool, yaw_rate: float = 0.0):
        if not self.enabled or not self.approach_enabled:
            return
        if is_in_pit or not is_engine_running:
            return
        text = self._approach.check_exit(x, z, speed_kmh, yaw_rate)
        if text and self._cooldown.is_allowed("EXIT", is_in_pit, is_engine_running):
            self._cooldown.record("EXIT")
            try:
                self._queue.put_nowait(text)
            except queue.Full:
                pass

    def check_clips(self, x: float, z: float, speed_kmh: float, is_in_pit: bool, is_engine_running: bool, yaw_rate: float = 0.0):
        if not self.enabled or not self.approach_enabled:
            return
        if is_in_pit or not is_engine_running:
            return
        text = self._approach.check_clips(x, z, speed_kmh, yaw_rate)
        if text and self._cooldown.is_allowed("CLIP", is_in_pit, is_engine_running):
            self._cooldown.record("CLIP")
            try:
                self._queue.put_nowait(text)
            except queue.Full:
                pass

    def check_approach(self, x: float, z: float, speed_kmh: float, is_in_pit: bool, is_engine_running: bool, yaw_rate: float = 0.0):
        if not self.enabled or not self.approach_enabled:
            return
        if is_in_pit or not is_engine_running:
            return
        text = self._approach.check(x, z, speed_kmh, yaw_rate)
        if text and self._cooldown.is_allowed("APPROACH", is_in_pit, is_engine_running):
            self._cooldown.record("APPROACH")
            try:
                self._queue.put_nowait(text)
            except queue.Full:
                pass

    def stop(self):
        self._approach.save_learning(self._track_slug)
        self._queue.put(None)
        self._thread.join(timeout=5)
