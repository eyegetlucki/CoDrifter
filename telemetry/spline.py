"""
AC fast_lane.ai spline parser.
Extracts real track length in meters so callout warning distances are accurate.
"""
import os
import struct


def parse_fast_lane(path: str) -> float | None:
    """
    Parse an AC fast_lane.ai binary spline and return total track length in meters.
    Returns None if the file is missing, too small, or the result fails sanity check.

    AC spline format: 16 bytes per point — (x, y, z, segment_length) as float32.
    The segment_length field is the distance from this point to the next.
    Some files have a 4-byte header before the point data; we try both and pick
    whichever gives a sensible track length.
    """
    if not os.path.exists(path):
        return None

    try:
        with open(path, "rb") as f:
            data = f.read()
    except OSError:
        return None

    if len(data) < 16:
        return None

    def _sum_lengths(raw: bytes) -> float:
        n = len(raw) // 16
        total = 0.0
        for i in range(n):
            seg = struct.unpack_from("<f", raw, i * 16 + 12)[0]
            if seg > 0:
                total += seg
        return total

    # Try without header first (whole file as point data)
    candidate_no_header = _sum_lengths(data)

    # Try skipping a 4-byte header
    candidate_with_header = _sum_lengths(data[4:]) if len(data) >= 20 else 0.0

    # AC units are meters, but some tracks store lengths in cm.
    # We check both candidates scaled as-is and /100 (cm→m).
    SANE_MIN = 200.0    # m — no real drift track is shorter than 200m
    SANE_MAX = 20000.0  # m — upper bound well above any realistic track

    for raw_total in (candidate_no_header, candidate_with_header):
        for scale in (1.0, 0.01):
            length = raw_total * scale
            if SANE_MIN <= length <= SANE_MAX:
                return round(length, 1)

    return None


def find_spline(ac_track_folder: str) -> str | None:
    """
    Locate fast_lane.ai in a given AC track folder.
    AC tracks use either 'aim/' or 'ai/' — checks both.
    Returns the full file path or None.
    """
    for sub in ("aim", "ai"):
        candidate = os.path.join(ac_track_folder, sub, "fast_lane.ai")
        if os.path.exists(candidate):
            return candidate
    return None
