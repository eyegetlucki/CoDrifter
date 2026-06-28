# CoDrifter — AI Voice Co-Driver for Assetto Corsa

CoDrifter is a real-time AI voice co-driver for Assetto Corsa. It reads live telemetry from the game, detects driving mistakes before they cost lap time, calls them out via voice in under 300ms, and generates a full AI-powered debrief after every session.

---

## What It Does

As you approach a corner carrying too much speed, CoDrifter says:

> *"Wait — let it rotate first."*

That call happens in under 300ms from mistake detection to first audio byte. It feels like a real co-driver is watching.

After the session ends, Claude analyzes the full telemetry log and generates a structured debrief — best and worst sectors, which mistakes occurred most, lap time consistency, and the top 3 actionable improvements.

---

## Architecture

```
Assetto Corsa (Windows Shared Memory)
            ↓
    telemetry/reader.py        — reads 60 fields at 60hz, logs to CSV
            ↓
    prediction/model.py        — XGBoost classifier, < 5ms inference
            ↓
    voice/coach.py             — ElevenLabs Flash v2.5, < 300ms latency
            ↓
    [session ends]
            ↓
    debrief/claude_debrief.py  — Claude Sonnet post-session analysis
```

---

## Tech Stack

| Component | Technology |
|---|---|
| Language | Python 3.11 |
| Telemetry | Assetto Corsa Shared Memory (Windows) |
| ML Model | XGBoost — real-time mistake classification |
| Voice | ElevenLabs Flash v2.5 — low-latency streaming TTS |
| AI Debrief | Claude Sonnet (Anthropic API) — post-session analysis |
| UI | PyQt6 — desktop app with live telemetry dashboard |
| Packaging | PyInstaller + Inno Setup 6 |

---

## Mistake Detection

CoDrifter classifies each telemetry frame into one of four drift-specific categories:

| Class | Description |
|---|---|
| `LOSING_ANGLE` | Car straightening mid-corner unintentionally |
| `SPEED_LOSS` | Bleeding speed without rear slip |
| `SNAP_RISK` | Erratic yaw — on the edge of spinning |
| `CLEAN` | No mistake detected |

The XGBoost model uses a 30-frame rolling window of engineered features including yaw rate, local velocity, wheel slip, and tyre temperature. Inference time is under 5ms per frame.

---

## Voice Callouts

Callouts fire when a mistake is detected above a configurable confidence threshold (default 90%). A 5-second per-type cooldown and 2-second minimum gap between any callouts prevent spam.

Corner approach and exit callouts fire on a position-based system using a mapped corner file — 13 corners mapped on Drift Playground 2021.

---

## Post-Session Debrief

After each session, Claude Sonnet reads a summarized version of the telemetry log and returns a structured debrief covering:

- Best and worst sectors
- Most frequent mistakes
- Lap time consistency score
- Top 3 actionable improvements
- Comparison to previous session

---

## Desktop App

The PyQt6 desktop app wraps all components with a dark-themed UI:

- **Dashboard** — live speed, gear, RPM, input bars, AI prediction badge, lap times, telemetry trace
- **History** — browse past sessions with lap stats
- **Debrief** — rendered Claude debrief after each session
- **Tracks** — map corner entry/exit positions with configurable hotkeys
- **Settings** — API keys, voice volume, cooldown timings, confidence threshold, model training

---

## Performance Requirements

| Requirement | Target |
|---|---|
| Telemetry read rate | 60hz |
| XGBoost inference | < 5ms per frame |
| Voice latency | < 300ms |
| Main loop blocking | Never — all API calls threaded |

---

## Project Structure

```
CoDrifter/
├── app.py                    # Entry point
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
│   ├── labels.py             # Threshold-based auto-labeling
│   ├── trainer.py            # Offline XGBoost training
│   └── model.py              # Real-time inference
│
├── voice/
│   ├── coach.py              # ElevenLabs Flash v2.5 integration
│   ├── callouts.py           # Callout text per mistake type
│   ├── cooldown.py           # Spam prevention logic
│   └── approach.py           # Position-based corner callouts
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
    ├── telemetry_worker.py   # QThread worker — bridges telemetry to UI
    ├── theme.py              # Color palette + QSS stylesheet
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
