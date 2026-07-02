import os
import time
import logging
import threading
import queue
import numpy as np
import sounddevice as sd
import miniaudio
from dotenv import load_dotenv
from elevenlabs.client import ElevenLabs

from voice.callouts import get_callout
from voice.cooldown import CooldownManager
from voice.approach import CornerApproachDetector

load_dotenv()

VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID")
MODEL_ID = "eleven_flash_v2_5"

# File logging so voice failures are visible in the packaged app (console=False).
_LOG_DIR = os.path.join("data")
logger = logging.getLogger("codrifter.voice")
if not logger.handlers:
    try:
        os.makedirs(_LOG_DIR, exist_ok=True)
        _handler = logging.FileHandler(os.path.join(_LOG_DIR, "coach.log"), encoding="utf-8")
        _handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
        logger.addHandler(_handler)
        logger.setLevel(logging.INFO)
    except Exception:
        pass


class VoiceCoach:
    def __init__(self, enabled: bool = False, same_mistake_cooldown: float = 5.0,
                 any_callout_cooldown: float = 2.0, approach_enabled: bool = True,
                 enabled_mistakes: dict | None = None, volume: float = 1.0):
        self._client = ElevenLabs(api_key=os.getenv("ELEVENLABS_API_KEY"))
        logger.info(
            "VoiceCoach init — api_key_present=%s voice_id_present=%s",
            bool(os.getenv("ELEVENLABS_API_KEY")), bool(VOICE_ID),
        )
        self._cooldown = CooldownManager(same_mistake_cooldown, any_callout_cooldown)
        self._approach = CornerApproachDetector()
        self._queue: queue.Queue = queue.Queue(maxsize=1)
        self._thread = threading.Thread(target=self._worker, daemon=True)
        self._thread.start()
        self.enabled: bool = enabled
        self.approach_enabled: bool = approach_enabled
        self._volume: float = volume   # 0.0-1.0 playback gain
        self._track_slug: str = ""
        self._last_praise: float = 0.0  # long cooldown so praise stays rare
        self.enabled_mistakes: dict = enabled_mistakes or {
            "LOSING_ANGLE": True, "SPEED_LOSS": True, "SNAP_RISK": True,
        }

    def load_corner_map(self, track_slug: str = ""):
        self._track_slug = track_slug
        self._approach.load(track_slug)

    def update_settings(self, same_mistake_cooldown: float, any_callout_cooldown: float,
                        approach_enabled: bool, enabled_mistakes: dict, volume: float | None = None):
        self._cooldown.update_cooldowns(same_mistake_cooldown, any_callout_cooldown)
        self.approach_enabled = approach_enabled
        self.enabled_mistakes = enabled_mistakes
        if volume is not None:
            self._volume = volume

    def _speak(self, text: str):
        # mp3_44100_128 works on every ElevenLabs tier (pcm_44100 needs Pro+).
        # Decode in-process with miniaudio and play via sounddevice — NO subprocess,
        # so no console window ever appears.
        mp3 = b"".join(self._client.text_to_speech.convert(
            voice_id=VOICE_ID,
            text=text,
            model_id=MODEL_ID,
            output_format="mp3_44100_128",
        ))
        decoded = miniaudio.decode(mp3)
        audio = np.frombuffer(decoded.samples, dtype=np.int16).astype(np.float32) / 32768.0
        audio = audio * self._volume   # apply Voice Volume setting (0.0-1.0 gain)
        if decoded.nchannels > 1:
            audio = audio.reshape(-1, decoded.nchannels)
        sd.play(audio, samplerate=decoded.sample_rate)
        sd.wait()

    def _worker(self):
        while True:
            item = self._queue.get()
            if item is None:
                break
            try:
                self._speak(item)
                logger.info("spoke: %s", item)
            except Exception:
                logger.exception("voice playback failed for: %s", item)
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

    def check_exit(self, x: float, z: float, speed_kmh: float, is_in_pit: bool, is_engine_running: bool,
                   yaw_rate: float = 0.0, mistake_flag: str | None = None):
        if not self.enabled or not self.approach_enabled:
            return
        if is_in_pit or not is_engine_running:
            return
        text = self._approach.check_exit(x, z, speed_kmh, yaw_rate, mistake_flag)
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

    PRAISE_COOLDOWN = 20.0  # seconds — keep positive callouts rare

    def check_coaching(self, x: float, z: float, speed_kmh: float, is_in_pit: bool, is_engine_running: bool,
                       yaw_rate: float = 0.0, steering: float = 0.0, mistake_flag: str | None = None):
        """Angle-depth coaching, positive reinforcement, and mid-link lost-drift — one call."""
        if not self.enabled or not self.approach_enabled:
            return
        if is_in_pit or not is_engine_running:
            return
        result = self._approach.check_corner(x, z, speed_kmh, yaw_rate, steering, mistake_flag)
        if not result:
            return
        kind, text = result  # kind: "LINK" | "ANGLE" | "PRAISE"
        if kind == "PRAISE":
            now = time.monotonic()
            if now - self._last_praise < self.PRAISE_COOLDOWN:
                return
            self._last_praise = now
        if self._cooldown.is_allowed(kind, is_in_pit, is_engine_running):
            self._cooldown.record(kind)
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
