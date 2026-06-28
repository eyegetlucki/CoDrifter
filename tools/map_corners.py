"""
Corner exit mapping tool — partial re-run starting from a specific corner.

Controls (work anywhere, even with AC focused):
  F7  — mark corner EXIT
  F8  — undo last mark
  F6  — finish and save

Usage: python -m tools.map_corners [start_corner]
Example: python -m tools.map_corners 7   (re-map exits from corner 7 onwards)
"""
import os
import json
import time
import sys
import keyboard

from telemetry.sim_info import SimInfo

OUTPUT_PATH = os.path.join("data", "corner_map.json")

exits = []
exit_index = 0
done = False


def mark_exit(sim, start_corner):
    global exit_index
    pos = round(sim.graphics.normalizedCarPosition, 4)
    speed = sim.physics.speedKmh
    corner_num = start_corner + exit_index
    exits.append(pos)
    exit_index += 1
    print(f"\n  Exit for Corner {corner_num} marked at position {pos}  (speed: {speed:.1f} km/h)")


def undo():
    global exit_index
    if exits:
        exits.pop()
        exit_index -= 1
        print(f"\n  Undone — {exit_index} exits marked")
    else:
        print("\n  Nothing to undo")


def finish():
    global done
    done = True


def main():
    global done

    start_corner = int(sys.argv[1]) if len(sys.argv) > 1 else 1

    if not os.path.exists(OUTPUT_PATH):
        print(f"ERROR: {OUTPUT_PATH} not found.")
        return

    with open(OUTPUT_PATH) as f:
        existing = json.load(f)

    corners_to_map = [c for c in existing if c["corner"] >= start_corner]
    print(f"Will map exits for corners {start_corner} to {existing[-1]['corner']}:")
    for c in corners_to_map:
        print(f"  Corner {c['corner']} [{c['type']}] entry at {c['position']}")
    print()

    sim = SimInfo()
    print("Connecting to AC...")
    while not sim.connect():
        print("  AC not running — retrying in 2 seconds...")
        time.sleep(2)
    print("Connected.\n")
    print("  F7 — mark EXIT (press as you pass each corner apex/exit)")
    print("  F8 — undo last mark")
    print("  F6 — finish and save\n")

    keyboard.add_hotkey("F7", mark_exit, args=(sim, start_corner))
    keyboard.add_hotkey("F8", undo)
    keyboard.add_hotkey("F6", finish)

    while not done:
        pos = sim.graphics.normalizedCarPosition
        speed = sim.physics.speedKmh
        sys.stdout.write(f"\r  Position: {pos:.4f}  Speed: {speed:.1f} km/h  Exits marked: {exit_index}/{len(corners_to_map)}   ")
        sys.stdout.flush()
        time.sleep(1 / 30)

    keyboard.unhook_all()

    # Merge back into existing
    for i, corner in enumerate(existing):
        if corner["corner"] >= start_corner:
            idx = corner["corner"] - start_corner
            if idx < len(exits):
                corner["exit_position"] = exits[idx]

    with open(OUTPUT_PATH, "w") as f:
        json.dump(existing, f, indent=2)

    print(f"\n\nSaved. Updated corner map:")
    for c in existing:
        print(f"  Corner {c['corner']} [{c['type']}]: entry {c['position']} -> exit {c.get('exit_position', 'N/A')}")

    sim.close()


if __name__ == "__main__":
    main()
