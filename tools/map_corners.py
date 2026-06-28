"""
Corner mapping tool for Drift Playground 2021.
Uses global hotkeys that work even when AC is in the foreground.

Controls (work anywhere, even with AC focused):
  F7  — TIGHT    (sharp, short corner)
  F8  — MEDIUM   (wider, hold the angle a bit longer)
  F9  — HAIRPIN  (very sharp, near 180 degrees)
  F10 — SWEEPING (long gradual curve, maintain angle)
  F11 — FEEDER   (slight turn that feeds into the next tight corner)
  F12 — Undo last mark
  F6  — Finish and save

Usage: python -m tools.map_corners
"""
import os
import json
import time
import sys
import keyboard

from telemetry.sim_info import SimInfo

OUTPUT_PATH = os.path.join("data", "corner_map.json")

corners = []
corner_num = 1
done = False


def mark(sim, corner_type: str):
    global corner_num
    pos = round(sim.graphics.normalizedCarPosition, 4)
    speed = sim.physics.speedKmh
    entry = {"corner": corner_num, "position": pos, "type": corner_type}
    corners.append(entry)
    print(f"\n  Corner {corner_num} [{corner_type}] marked at position {pos}  (speed: {speed:.1f} km/h)")
    corner_num += 1


def undo():
    global corner_num
    if corners:
        removed = corners.pop()
        corner_num -= 1
        print(f"\n  Removed Corner {removed['corner']} [{removed['type']}] at position {removed['position']}")
    else:
        print("\n  Nothing to undo")


def finish():
    global done
    done = True


def main():
    global done

    sim = SimInfo()
    print("Connecting to AC...")
    while not sim.connect():
        print("  AC not running — retrying in 2 seconds...")
        time.sleep(2)
    print("Connected.\n")
    print("Drive a slow lap and classify each corner:")
    print("  F7  — TIGHT    (sharp, short corner)")
    print("  F8  — MEDIUM   (wider, hold the angle a bit longer)")
    print("  F9  — HAIRPIN  (very sharp, near 180 degrees)")
    print("  F10 — SWEEPING (long gradual curve, maintain angle)")
    print("  F11 — FEEDER   (slight turn feeding into the next tight corner)")
    print("  F12 — Undo last mark")
    print("  F6  — Finish and save\n")

    keyboard.add_hotkey("F7", mark, args=(sim, "TIGHT"))
    keyboard.add_hotkey("F8", mark, args=(sim, "MEDIUM"))
    keyboard.add_hotkey("F9", mark, args=(sim, "HAIRPIN"))
    keyboard.add_hotkey("F10", mark, args=(sim, "SWEEPING"))
    keyboard.add_hotkey("F11", mark, args=(sim, "FEEDER"))
    keyboard.add_hotkey("F12", undo)
    keyboard.add_hotkey("F6", finish)

    while not done:
        pos = sim.graphics.normalizedCarPosition
        speed = sim.physics.speedKmh
        sys.stdout.write(f"\r  Position: {pos:.4f}  Speed: {speed:.1f} km/h  Corners marked: {len(corners)}   ")
        sys.stdout.flush()
        time.sleep(1 / 30)

    keyboard.unhook_all()

    # Drop last entry if it wraps back to near start
    if len(corners) > 1 and corners[-1]["position"] < corners[0]["position"] + 0.05:
        corners.pop()

    os.makedirs("data", exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump(corners, f, indent=2)

    print(f"\n\nSaved {len(corners)} corners to {os.path.abspath(OUTPUT_PATH)}")
    print("\nCorner map:")
    for c in corners:
        print(f"  Corner {c['corner']} [{c['type']}]: position {c['position']}")

    sim.close()


if __name__ == "__main__":
    main()
