import json
import math
import os
import numpy as np
import pandas as pd
from dotenv import load_dotenv
import anthropic

from prediction.features import extract_features_from_df
from prediction.labels import label_dataframe, MISTAKE_CLASSES as ALL_CLASSES, _is_real_corner

load_dotenv()

MODEL = "claude-sonnet-4-6"
MISTAKE_CLASSES = ["LOSING_ANGLE", "SPEED_LOSS", "SNAP_RISK"]

SETTINGS_PATH  = os.path.join("data", "settings.json")
TRACK_MAPS_DIR = os.path.join("data", "track_maps")
CORNER_ACTIVE_RADIUS_M = 25.0   # matches prediction/labels.py and voice/approach.py


def _read_map(path: str) -> tuple[str, list[dict]]:
    """Read a track map file, returning (name, real-corners-only)."""
    try:
        with open(path) as f:
            raw = json.load(f)
        corners = [c for c in raw.get("corners", []) if _is_real_corner(c)]
        return raw.get("name", ""), corners
    except Exception:
        return "", []


def _load_active_corner_map() -> tuple[str, list[dict]]:
    """Return (track_name, corners) for the active track. Falls back to the first
    map with real corners so attribution always matches what labels.py used."""
    slug = ""
    try:
        with open(SETTINGS_PATH) as f:
            slug = json.load(f).get("active_track", "")
    except Exception:
        pass

    # Prefer the active track if it has real corners
    if slug:
        path = os.path.join(TRACK_MAPS_DIR, f"{slug}.json")
        if os.path.exists(path):
            name, corners = _read_map(path)
            if corners:
                return name or slug, corners

    # Fall back to the first map with real corners (mirrors labels._load_corner_xz scan)
    if os.path.isdir(TRACK_MAPS_DIR):
        for fname in sorted(os.listdir(TRACK_MAPS_DIR)):
            if not fname.endswith(".json"):
                continue
            name, corners = _read_map(os.path.join(TRACK_MAPS_DIR, fname))
            if corners:
                return name or fname[:-5], corners
    return "", []


def _nearest_corner(x: float, z: float, corners: list[dict]) -> int | None:
    """Index of the nearest corner within CORNER_ACTIVE_RADIUS_M, else None."""
    best, best_d = None, CORNER_ACTIVE_RADIUS_M
    for i, c in enumerate(corners):
        d = math.hypot(x - c["x"], z - c["z"])
        if d <= best_d:
            best, best_d = i, d
    return best


def _detect_mistakes(df: pd.DataFrame, corners: list[dict]) -> tuple[dict, dict, dict]:
    """Run the real label pipeline and attribute mistakes to corners.

    Returns (total_events, per_corner_events, per_corner_anglehold) where an 'event' is a
    rising edge into a non-CLEAN label (matching the old edge-count semantics).
    """
    total = {k: 0 for k in MISTAKE_CLASSES}
    per_corner: dict[int, dict] = {}
    anglehold: dict[int, dict] = {}

    if len(df) < 60:
        return total, per_corner, anglehold

    feats = extract_features_from_df(df)
    if len(feats) == 0:
        return total, per_corner, anglehold
    labels = label_dataframe(df, feats).reset_index(drop=True)
    raw = df.tail(len(feats)).reset_index(drop=True)

    label_names = labels.map(lambda i: ALL_CLASSES[i])
    prev = "CLEAN"
    has_pos = "world_position_x" in raw.columns and corners
    wx = raw["world_position_x"].values if has_pos else None
    wz = raw["world_position_z"].values if has_pos else None
    yaw = raw["yaw_rate"].abs().values if "yaw_rate" in raw.columns else None

    for i, name in enumerate(label_names):
        ci = _nearest_corner(wx[i], wz[i], corners) if has_pos else None
        # angle-hold: track sustained |yaw| per corner (from all in-corner frames)
        if ci is not None and yaw is not None:
            a = anglehold.setdefault(ci, {"sum": 0.0, "n": 0})
            a["sum"] += float(yaw[i]); a["n"] += 1
        # count rising edges into a mistake class
        if name != "CLEAN" and name != prev:
            total[name] += 1
            if ci is not None:
                pc = per_corner.setdefault(ci, {k: 0 for k in MISTAKE_CLASSES})
                pc[name] += 1
        prev = name

    return total, per_corner, anglehold


def _ms_to_time(ms: int) -> str:
    if ms <= 0:
        return "N/A"
    total_s = ms / 1000
    minutes = int(total_s // 60)
    seconds = total_s % 60
    return f"{minutes}:{seconds:06.3f}"


def _summarize_session(df: pd.DataFrame) -> dict:
    driving = df[df["is_engine_running"] == True].copy()
    driving = driving[driving["speed_kmh"] > 5]

    # Lap detection — count unique non-zero last_lap_ms transitions
    lap_times = df["last_lap_ms"].dropna()
    lap_times = lap_times[lap_times > 0]
    completed_laps = lap_times.nunique()
    best_lap_ms = int(df["best_lap_ms"].max()) if df["best_lap_ms"].max() > 0 else 0

    # Average of completed laps (exclude outliers > 3x best)
    valid_laps = [t for t in lap_times.unique() if best_lap_ms == 0 or t < best_lap_ms * 3]
    avg_lap_ms = int(sum(valid_laps) / len(valid_laps)) if valid_laps else 0

    total_time_ms = int(df["timestamp_ms"].max() - df["timestamp_ms"].min())

    # Speed stats
    speed_stats = {
        "max_kmh": round(float(driving["speed_kmh"].max()), 1) if len(driving) > 0 else 0,
        "avg_kmh": round(float(driving["speed_kmh"].mean()), 1) if len(driving) > 0 else 0,
    }

    # Throttle / steering usage
    throttle_avg = round(float(driving["throttle"].mean()), 3) if len(driving) > 0 else 0
    yaw_rate_avg = round(float(driving["yaw_rate"].abs().mean()), 3) if "yaw_rate" in driving.columns and len(driving) > 0 else 0
    rear_slip_avg = round(float(((driving["wheel_slip_rl"].abs() + driving["wheel_slip_rr"].abs()) / 2).mean()), 3) if "wheel_slip_rl" in driving.columns and len(driving) > 0 else 0

    # Tyre temps
    tyre_summary = {}
    for corner in ["fl", "fr", "rl", "rr"]:
        col = f"tyre_temp_{corner}"
        if col in driving.columns and len(driving) > 0:
            tyre_summary[corner] = round(float(driving[col].mean()), 1)

    # Sector analysis — which sector has the lowest avg speed (weakest sector)
    sector_speeds = {}
    if "sector_index" in driving.columns:
        for s in [0, 1, 2]:
            s_data = driving[driving["sector_index"] == s]
            if len(s_data) > 0:
                sector_speeds[f"Sector {s + 1}"] = round(float(s_data["speed_kmh"].mean()), 1)

    best_sector = max(sector_speeds, key=sector_speeds.get) if sector_speeds else "N/A"
    worst_sector = min(sector_speeds, key=sector_speeds.get) if sector_speeds else "N/A"

    # Mistake detection — reuse the calibrated label pipeline (single source of truth),
    # attributed to the active track's corners for actionable, corner-specific coaching.
    track_name, corners = _load_active_corner_map()
    total_events, per_corner_events, per_corner_anglehold = _detect_mistakes(df, corners)

    # Build a readable per-corner breakdown: mistakes + sustained angle per corner
    per_corner = {}
    for ci in sorted(set(per_corner_events) | set(per_corner_anglehold)):
        ctype = corners[ci].get("type", "?") if ci < len(corners) else "?"
        ah = per_corner_anglehold.get(ci)
        entry = {
            "type": ctype,
            "mistakes": {k: v for k, v in per_corner_events.get(ci, {}).items() if v > 0},
            "avg_angle_rad_s": round(ah["sum"] / ah["n"], 3) if ah and ah["n"] else 0.0,
        }
        per_corner[f"Corner {ci + 1}"] = entry

    return {
        "total_laps": completed_laps,
        "best_lap_ms": best_lap_ms,
        "best_lap_time": _ms_to_time(best_lap_ms),
        "average_lap_ms": avg_lap_ms,
        "average_lap_time": _ms_to_time(avg_lap_ms),
        "total_session_time_ms": total_time_ms,
        "total_frames": len(df),
        "driving_frames": len(driving),
        "speed": speed_stats,
        "throttle_avg": throttle_avg,
        "yaw_rate_avg_abs": yaw_rate_avg,
        "rear_slip_avg": rear_slip_avg,
        "tyre_temps_avg": tyre_summary,
        "sector_avg_speeds": sector_speeds,
        "best_sector": best_sector,
        "worst_sector": worst_sector,
        "track_name": track_name or "Unknown track",
        "mistake_events": total_events,
        "per_corner": per_corner,
    }


def _build_prompt(summary: dict, prev_session: dict | None) -> str:
    prev_block = ""
    if prev_session:
        prev_block = f"""
Previous session for comparison:
- Best lap: {prev_session.get('best_lap_time', 'N/A')}
- Avg lap: {prev_session.get('average_lap_time', 'N/A')}
- Total laps: {prev_session.get('total_laps', 0)}
- Mistake events: {json.dumps(prev_session.get('mistake_events', {}))}
"""

    per_corner_block = ""
    if summary.get("per_corner"):
        lines = []
        for cname, info in summary["per_corner"].items():
            mistakes = ", ".join(f"{k} x{v}" for k, v in info["mistakes"].items()) or "clean"
            lines.append(f"  - {cname} ({info['type']}): avg angle {info['avg_angle_rad_s']} rad/s | {mistakes}")
        per_corner_block = "\n- Per-corner breakdown (higher avg angle = more committed drift):\n" + "\n".join(lines)

    return f"""You are a drift racing coach reviewing a session on {summary.get('track_name', 'this track')}.
Analyze the telemetry summary below and return a structured JSON debrief.

SESSION TELEMETRY SUMMARY:
- Total laps: {summary['total_laps']}
- Best lap: {summary['best_lap_time']} ({summary['best_lap_ms']}ms)
- Average lap: {summary['average_lap_time']} ({summary['average_lap_ms']}ms)
- Session duration: {summary['total_session_time_ms'] / 1000 / 60:.1f} minutes
- Max speed: {summary['speed']['max_kmh']} km/h, avg: {summary['speed']['avg_kmh']} km/h
- Avg throttle: {summary['throttle_avg']:.1%}
- Avg yaw rate (abs): {summary['yaw_rate_avg_abs']:.3f} rad/s
- Avg rear wheel slip: {summary['rear_slip_avg']:.2f}
- Sector average speeds: {json.dumps(summary['sector_avg_speeds'])}
- Best sector by speed: {summary['best_sector']}
- Worst sector by speed: {summary['worst_sector']}
- Tyre temps (avg °C): {json.dumps(summary['tyre_temps_avg'])}
- Detected mistake events:
  - LOSING_ANGLE (car straightening unintentionally): {summary['mistake_events']['LOSING_ANGLE']}
  - SPEED_LOSS (bleeding speed without rear slip): {summary['mistake_events']['SPEED_LOSS']}
  - SNAP_RISK (erratic yaw, about to spin): {summary['mistake_events']['SNAP_RISK']}{per_corner_block}
{prev_block}
Return ONLY valid JSON — no markdown, no explanation, no prefix text. Schema:
{{
  "session_summary": {{
    "total_laps": <int>,
    "best_lap_ms": <int>,
    "average_lap_ms": <int>,
    "total_session_time_ms": <int>
  }},
  "performance": {{
    "best_sector": "<string>",
    "worst_sector": "<string>",
    "consistency_score": <float 0.0-1.0>,
    "mistake_frequency": {{
      "LOSING_ANGLE": <int>,
      "SPEED_LOSS": <int>,
      "SNAP_RISK": <int>
    }}
  }},
  "improvements": ["<string>", "<string>", "<string>"],
  "coaching_tip": "<string>",
  "vs_previous_session": "<Better|Worse|First session|string>"
}}

consistency_score: 1.0 = perfectly consistent laps, 0.0 = wildly inconsistent.
improvements: exactly 3 drift-specific, actionable coaching points. When the per-corner
breakdown shows a corner with the most mistakes or the lowest sustained angle, name that
specific corner (e.g. "You lost angle most through Corner 3 — commit throttle earlier on exit").
coaching_tip: one specific thing to focus on next session, referencing a corner if the data points to one.
vs_previous_session: compare to the previous session if data was provided, otherwise "First session"."""


def _load_previous_session(sessions_dir: str, current_path: str) -> dict | None:
    try:
        csvs = sorted([
            os.path.join(sessions_dir, f)
            for f in os.listdir(sessions_dir)
            if f.endswith(".csv") and f != os.path.basename(current_path)
        ])
        if not csvs:
            return None
        prev_df = pd.read_csv(csvs[-1])
        return _summarize_session(prev_df)
    except Exception:
        return None


def run_debrief(session_csv_path: str) -> dict | None:
    print("\n" + "=" * 60)
    print("  POST-SESSION DEBRIEF")
    print("=" * 60)

    try:
        df = pd.read_csv(session_csv_path)
    except Exception as e:
        print(f"  Could not read session CSV: {e}")
        return None

    if len(df) < 60:
        print("  Session too short for debrief (< 1 second of data).")
        return None

    print("  Analyzing session telemetry...")
    summary = _summarize_session(df)

    sessions_dir = os.path.dirname(session_csv_path)
    prev_summary = _load_previous_session(sessions_dir, session_csv_path)

    prompt = _build_prompt(summary, prev_summary)

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("  ANTHROPIC_API_KEY not set — skipping debrief.")
        return None

    print("  Sending to Claude for analysis...\n")

    client = anthropic.Anthropic(api_key=api_key)

    try:
        message = client.messages.create(
            model=MODEL,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = message.content[0].text.strip()
    except Exception as e:
        print(f"  Claude API error: {e}")
        return None

    try:
        debrief = json.loads(raw)
    except json.JSONDecodeError:
        # Try to extract JSON from response if wrapped in any text
        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start >= 0 and end > start:
            try:
                debrief = json.loads(raw[start:end])
            except json.JSONDecodeError:
                print("  Failed to parse Claude response as JSON.")
                print(f"  Raw response:\n{raw}")
                return None
        else:
            print("  Failed to parse Claude response as JSON.")
            return None

    _print_debrief(debrief, summary)
    return debrief


def _print_debrief(debrief: dict, summary: dict):
    ss = debrief.get("session_summary", {})
    perf = debrief.get("performance", {})
    improvements = debrief.get("improvements", [])
    tip = debrief.get("coaching_tip", "")
    vs_prev = debrief.get("vs_previous_session", "")

    print(f"  Laps completed:    {ss.get('total_laps', summary['total_laps'])}")
    print(f"  Best lap:          {_ms_to_time(ss.get('best_lap_ms', summary['best_lap_ms']))}")
    print(f"  Avg lap:           {_ms_to_time(ss.get('average_lap_ms', summary['average_lap_ms']))}")
    print(f"  Session time:      {ss.get('total_session_time_ms', summary['total_session_time_ms']) / 1000 / 60:.1f} min")
    print()

    print(f"  Best sector:       {perf.get('best_sector', summary['best_sector'])}")
    print(f"  Worst sector:      {perf.get('worst_sector', summary['worst_sector'])}")
    print(f"  Consistency:       {perf.get('consistency_score', 0.0):.0%}")

    mf = perf.get("mistake_frequency", summary["mistake_events"])
    if mf:
        print(f"  Mistake events:    ", end="")
        parts = [f"{k}: {v}" for k, v in mf.items() if v > 0]
        print(", ".join(parts) if parts else "None detected")
    print()

    per_corner = summary.get("per_corner", {})
    if per_corner:
        print("  PER-CORNER BREAKDOWN:")
        for cname, info in per_corner.items():
            mistakes = ", ".join(f"{k} x{v}" for k, v in info["mistakes"].items()) or "clean"
            print(f"    {cname} ({info['type']}): avg angle {info['avg_angle_rad_s']} rad/s  -  {mistakes}")
        print()

    print("  TOP 3 IMPROVEMENTS:")
    for i, imp in enumerate(improvements[:3], 1):
        print(f"    {i}. {imp}")
    print()

    print(f"  COACHING TIP:")
    print(f"    {tip}")
    print()

    print(f"  VS PREVIOUS SESSION: {vs_prev}")
    print("=" * 60)
