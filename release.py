"""
release.py — bump version, commit, tag, push, then build.

Usage:
    python release.py patch          # 1.0.0 → 1.0.1
    python release.py minor          # 1.0.0 → 1.1.0
    python release.py major          # 1.0.0 → 2.0.0
    python release.py 1.2.3          # set exact version

What it does:
    1. Reads current version from version.py
    2. Calculates new version
    3. Writes version.py
    4. Patches the AppVersion line in installer/build.iss
    5. git commit + tag vX.Y.Z + push --follow-tags
    6. Optionally runs build.bat (pass --build flag)

The GitHub release and asset upload are still manual — create the release
on github.com, tag it vX.Y.Z, and upload installer/CoDrifter_Setup.exe.
"""

import re
import subprocess
import sys


VERSION_FILE = "version.py"
ISS_FILE = "installer/build.iss"
ISS_PATTERN = re.compile(r'(#define AppVersion\s+")([\d.]+)(")')


def _read_version() -> str:
    with open(VERSION_FILE) as f:
        m = re.search(r'__version__\s*=\s*"([\d.]+)"', f.read())
    if not m:
        raise ValueError(f"Cannot parse version from {VERSION_FILE}")
    return m.group(1)


def _bump(current: str, part: str) -> str:
    major, minor, patch = (int(x) for x in current.split("."))
    if part == "major":
        return f"{major + 1}.0.0"
    if part == "minor":
        return f"{major}.{minor + 1}.0"
    if part == "patch":
        return f"{major}.{minor}.{patch + 1}"
    # treat as explicit version string
    parts = part.split(".")
    if len(parts) != 3 or not all(p.isdigit() for p in parts):
        raise ValueError(f"Invalid version or part: {part!r}")
    return part


def _write_version_py(new_ver: str):
    with open(VERSION_FILE, "w") as f:
        f.write(f'__version__ = "{new_ver}"\n')


def _patch_iss(new_ver: str):
    with open(ISS_FILE, encoding="utf-8") as f:
        content = f.read()
    new_content, n = ISS_PATTERN.subn(lambda m: f'{m.group(1)}{new_ver}{m.group(3)}', content)
    if n == 0:
        raise ValueError(f"AppVersion line not found in {ISS_FILE}")
    with open(ISS_FILE, "w", encoding="utf-8") as f:
        f.write(new_content)


def _run(cmd: list[str]):
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(result.stderr or result.stdout)
        raise SystemExit(f"Command failed: {' '.join(cmd)}")
    if result.stdout.strip():
        print(result.stdout.strip())


def main():
    args = sys.argv[1:]
    do_build = "--build" in args
    parts = [a for a in args if a != "--build"]

    if len(parts) != 1:
        print(__doc__)
        raise SystemExit(1)

    part = parts[0]
    current = _read_version()
    new_ver = _bump(current, part)

    print(f"Bumping {current} → {new_ver}")

    _write_version_py(new_ver)
    _patch_iss(new_ver)

    print(f"Updated {VERSION_FILE} and {ISS_FILE}")

    _run(["git", "add", VERSION_FILE, ISS_FILE])
    _run(["git", "commit", "-m", f"Release v{new_ver}"])
    _run(["git", "tag", f"v{new_ver}"])
    _run(["git", "push", "--follow-tags"])

    print(f"\nv{new_ver} committed, tagged, and pushed.")

    if do_build:
        print("\nRunning build.bat...")
        subprocess.run(["cmd", "/c", "build.bat"], check=True)
    else:
        print("\nNext steps:")
        print(f"  1. Run build.bat to create the installer")
        print(f"  2. Create GitHub release tagged v{new_ver}")
        print(f"  3. Upload installer\\CoDrifter_Setup.exe as the release asset")


if __name__ == "__main__":
    main()
