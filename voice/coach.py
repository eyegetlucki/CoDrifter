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
    def __init__(self):
        self._client = ElevenLabs(api_key=os.getenv("ELEVENLABS_API_KEY"))
        self._cooldown = CooldownManager()
        self._approach = CornerApproachDetector()
        self._approach.load()
        self._queue: queue.Queue = queue.Queue(maxsize=1)
        self._thread = threading.Thread(target=self._worker, daemon=True)
        self._thread.start()

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

    def is_in_corner(self, normalized_pos: float) -> bool:
        return self._approach.is_in_corner(normalized_pos)

    def check_exit(self, normalized_pos: float, speed_kmh: float, is_in_pit: bool, is_engine_running: bool):
        if is_in_pit or not is_engine_running:
            return
        text = self._approach.check_exit(normalized_pos, speed_kmh)
        if text and self._cooldown.is_allowed("EXIT", is_in_pit, is_engine_running):
            self._cooldown.record("EXIT")
            try:
                self._queue.put_nowait(text)
            except queue.Full:
                pass

    def check_approach(self, normalized_pos: float, speed_kmh: float, is_in_pit: bool, is_engine_running: bool):
        if is_in_pit or not is_engine_running:
            return
        text = self._approach.check(normalized_pos, speed_kmh)
        if text and self._cooldown.is_allowed("APPROACH", is_in_pit, is_engine_running):
            self._cooldown.record("APPROACH")
            try:
                self._queue.put_nowait(text)
            except queue.Full:
                pass

    def stop(self):
        self._queue.put(None)
        self._thread.join(timeout=5)
