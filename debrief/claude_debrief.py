import json
import os
import pandas as pd
from dotenv import load_dotenv
import anthropic

load_dotenv()

MODEL = "claude-sonnet-4-6"
MISTAKE_CLASSES = ["LOSING_ANGLE", "SPEED_LOSS", "SNAP_RISK"]


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

    # Mistake frequency — infer from telemetry signals (approximate, without model rerun)
    # SNAP_RISK: yaw_rate_std spikes — use rolling std on yaw_rate
    snap_events = 0
    losing_angle_events = 0
    speed_loss_events = 0

    if "yaw_rate" in driving.columns and len(driving) > 60:
        yaw = driving["yaw_rate"].reset_index(drop=True)
        yaw_std = yaw.rolling(30).std().fillna(0)
        lateral = (driving["local_velocity_x"].abs() if "local_velocity_x" in driving.columns
                   else pd.Series([0] * len(driving))).reset_index(drop=True)
        speed_s = driving["speed_kmh"].reset_index(drop=True)

        snap_mask = (yaw_std > 0.25) & (lateral > 3.0) & (speed_s > 20)
        snap_events = int((snap_mask.diff().fillna(False) & snap_mask).sum())

        yaw_delta = yaw.diff(30).fillna(0)
        throttle_s = driving["throttle"].reset_index(drop=True)
        losing_mask = (yaw_delta < -0.3) & (yaw.abs() > 0.15) & (throttle_s < 0.5) & (speed_s > 15)
        losing_angle_events = int((losing_mask.diff().fillna(False) & losing_mask).sum())

    if "wheel_slip_rl" in driving.columns and len(driving) > 60:
        speed_s = driving["speed_kmh"].reset_index(drop=True)
        rear_slip = ((driving["wheel_slip_rl"].abs() + driving["wheel_slip_rr"].abs()) / 2).reset_index(drop=True)
        throttle_s = driving["throttle"].reset_index(drop=True)
        speed_delta = speed_s.diff(30).fillna(0)
        loss_mask = (speed_delta < -8.0) & (rear_slip < 5.0) & (throttle_s < 0.35) & (speed_s > 20)
        speed_loss_events = int((loss_mask.diff().fillna(False) & loss_mask).sum())

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
        "mistake_events": {
            "LOSING_ANGLE": losing_angle_events,
            "SPEED_LOSS": speed_loss_events,
            "SNAP_RISK": snap_events,
        },
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

    return f"""You are a drift racing coach reviewing a session on Drift Playground 2021.
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
  - SNAP_RISK (erratic yaw, about to spin): {summary['mistake_events']['SNAP_RISK']}
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
improvements: exactly 3 drift-specific, actionable coaching points.
coaching_tip: one specific thing to focus on next session.
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

    print("  TOP 3 IMPROVEMENTS:")
    for i, imp in enumerate(improvements[:3], 1):
        print(f"    {i}. {imp}")
    print()

    print(f"  COACHING TIP:")
    print(f"    {tip}")
    print()

    print(f"  VS PREVIOUS SESSION: {vs_prev}")
    print("=" * 60)
