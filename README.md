# CoDrifter — AI Voice Co-Driver for Assetto Corsa

CoDrifter is a real-time AI voice co-driver for Assetto Corsa. It reads live telemetry from the game, detects driving mistakes before they cost lap time, calls them out via voice in under 300ms, and generates a full AI-powered debrief after every session.

---

## What It Does

You're mid-corner, the car starts to straighten. Before you've even registered it, CoDrifter says:

> *"Wait — let it rotate first."*

That call happens in under 300ms from mistake detection to first audio byte. It feels like a real co-driver is watching.

After the session ends, Claude analyzes the full telemetry log and generates a structured debrief — best and worst sectors, which mistakes occurred most, lap time consistency, and the top 3 actionable improvements.

---

## Architecture

```
Session CSV (every session)
        ↓
Offline XGBoost retraining
        ↓
Smarter mistake detection over time

Corner approach data (every session)
        ↓
Track learning JSON (persisted per track)
        ↓
Personal baseline calibration
        ↓
Hot-entry threshold = driver's own average + 15%


Assetto Corsa (Windows Shared Memory)
            ↓
    telemetry/reader.py        — reads 60+ fields at 60hz, logs every frame to CSV
            ↓
    prediction/features.py     — 30-frame rolling window → 20 engineered features
            ↓
    prediction/model.py        — XGBoost classifier, < 5ms inference per frame
            ↓
    voice/coach.py             — ElevenLabs Flash v2.5, < 300ms end-to-end latency
            ↓
    voice/approach.py          — position-based corner entry/exit callouts
            ↓
    [session ends]
            ↓
    debrief/claude_debrief.py  — Claude Sonnet post-session analysis
```

Everything from telemetry read to voice output runs in under 300ms. API calls and CSV writes are fully threaded — the 60hz main loop never blocks.

---

## Tech Stack

| Component | Technology |
|---|---|
| Language | Python 3.11 |
| Telemetry | Assetto Corsa Shared Memory (Windows) |
| ML Model | XGBoost — real-time drift mistake classification |
| Voice | ElevenLabs Flash v2.5 — low-latency streaming TTS |
| AI Debrief | Claude Sonnet (Anthropic API) — post-session analysis |
| UI | PyQt6 — desktop app with live telemetry dashboard |
| Packaging | PyInstaller + Inno Setup 6 |

---

## Prediction Model

The core of CoDrifter is an XGBoost classifier that runs on every telemetry frame at 60hz.

**How it works:**

Each frame, `prediction/features.py` takes a 30-frame rolling window (~0.5 seconds of history) and engineers 20 features from it — things like rate of yaw change, wheel slip delta, speed trend, and throttle/steering correlation. These capture the *dynamics* of what the car is doing, not just a single snapshot.

The XGBoost model classifies that feature vector into one of four drift-specific classes:

| Class | What it means |
|---|---|
| `LOSING_ANGLE` | Car is straightening mid-corner — rotation is bleeding out |
| `SPEED_LOSS` | Losing speed without meaningful rear slip — inefficient |
| `SNAP_RISK` | Yaw rate is erratic — car is close to spinning |
| `CLEAN` | No mistake detected |

If the prediction exceeds a configurable confidence threshold (default 90%), a voice callout fires.

**Why 90% confidence?** At lower thresholds the model calls too many borderline frames that aren't actually mistakes. At 90% it only speaks up when it's certain — which keeps the co-driver feeling useful rather than noisy.

**Extended telemetry fields** logged per frame include yaw rate, local velocity (X/Y), wheel slip per corner, tyre temperature per corner, TC active, and ABS active. These give the model genuine insight into rotational dynamics — far more signal than speed/throttle/brake alone. The richer the training data, the more precisely it can distinguish a controlled slide from a genuine mistake.

---

## Voice Callouts

Two callout systems run in parallel:

**Mistake callouts** — fire when the prediction model exceeds the confidence threshold. Each mistake type has 4 randomized variations so the co-driver doesn't repeat the same line. Cooldown rules prevent spam: 5 seconds per mistake type, 2 seconds minimum between any callout, suppressed in pit lane or with engine off.

**Corner callouts** — position-based, fired from a mapped corner file. Entry callouts are context-aware: CoDrifter reads your speed and yaw rate as you enter the warning bubble and diagnoses your approach — too fast, not yet sideways, or both. After 3 passes on a corner it learns your personal average entry speed and uses that as the threshold rather than a hardcoded number. Learned averages are saved per track and loaded back each session so accuracy improves over time. Exit callouts fire at the apex/exit point with type-specific advice.

Per-corner speed learning is stored in `data/track_learning/<slug>.json` and is track-specific — Klutch Kickers and Drift Playground each build their own baselines independently.

---

## Post-Session Debrief

After each session, Claude Sonnet reads a summarized version of the telemetry log — not raw CSV rows, a structured digest — and returns a debrief covering:

- Best and worst sectors
- Most frequent mistake types
- Lap time consistency score
- Top 3 actionable improvements
- Comparison to the previous session

The debrief renders in the app automatically after a session ends if auto-debrief is enabled in Settings.

---

## Desktop App

The PyQt6 desktop app wraps all components with a dark-themed UI:

- **Dashboard** — live speed, gear, RPM, throttle/brake/steering bars, AI prediction badge, lap times, rolling telemetry trace
- **History** — browse past sessions with lap count, best lap, and average lap
- **Debrief** — rendered Claude debrief with per-section cards
- **Tracks** — map corner entry/exit positions with configurable hotkey binds, corner type tagging
- **Settings** — API keys, voice volume, cooldown timings, confidence threshold, callout toggles, model training trigger

---

## Performance Requirements

| Requirement | Target |
|---|---|
| Telemetry read rate | 60hz — never drop below 30hz |
| Feature engineering | < 2ms per frame |
| XGBoost inference | < 5ms per frame |
| Voice latency | < 300ms end-to-end |
| Main loop blocking | Never — all I/O and API calls threaded |
| CSV write | Every frame via async background thread |

---

## Project Structure

```
CoDrifter/
├── app.py                    # Entry point (PyQt6 desktop app)
├── main.py                   # CLI entry point
├── build.spec                # PyInstaller spec
├── build.bat                 # One-command build → installer
├── installer/build.iss       # Inno Setup 6 installer script
│
├── telemetry/
│   ├── sim_info.py           # AC shared memory interface (DO NOT MODIFY)
│   ├── reader.py             # 60hz read loop + async CSV writer
│   └── models.py             # TelemetryFrame dataclass
│
├── prediction/
│   ├── features.py           # 30-frame rolling window feature engineering
│   ├── labels.py             # Threshold-based auto-labeling for training data
│   ├── trainer.py            # Offline XGBoost training script
│   └── model.py              # Real-time inference + confidence thresholding
│
├── voice/
│   ├── coach.py              # ElevenLabs Flash v2.5 integration
│   ├── callouts.py           # Callout text per mistake type
│   ├── cooldown.py           # Spam prevention — per-type and global cooldowns
│   └── approach.py           # Position-based corner entry/exit callouts
│
├── debrief/
│   └── claude_debrief.py     # Post-session Claude Sonnet analysis
│
└── ui/
    ├── main_window.py        # App shell, sidebar nav, session lifecycle
    ├── dashboard_tab.py      # Live telemetry dashboard
    ├── history_tab.py        # Session history browser
    ├── debrief_tab.py        # Debrief renderer
    ├── tracks_tab.py         # Corner mapping tool
    ├── settings_tab.py       # Settings UI
    ├── telemetry_worker.py   # QThread worker — bridges telemetry to UI signals
    ├── theme.py              # Color palette + global QSS stylesheet
    └── settings_manager.py   # JSON settings persistence
```

---

## Requirements

- Windows 10/11 (shared memory is Windows-only)
- Assetto Corsa
- ElevenLabs API key (Flash v2.5 voice)
- Anthropic API key (Claude Sonnet debrief)

API keys are entered in the Settings tab after installation — no manual file editing required.

---

## Build

```bat
build.bat
```

Runs PyInstaller then Inno Setup and outputs `installer/CoDrifter_Setup.exe`.

---

*Part of a broader AI engineering portfolio — [SharpIQ](https://github.com/eyegetlucki/SharpIQ) · [Foil & Felony](https://github.com/eyegetlucki/FoilAndFelony) · [Betcha Know!](https://github.com/eyegetlucki/betchaknow)*
