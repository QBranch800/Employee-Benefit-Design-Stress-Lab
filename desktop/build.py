from __future__ import annotations

import argparse
import os
import plistlib
import shutil
import subprocess
import sys
from pathlib import Path

import PyInstaller.__main__

from benefit_stress_lab.config import MODEL_VERSION

ROOT = Path(__file__).resolve().parents[1]
DESKTOP = ROOT / "desktop"
DIST = ROOT / "dist"
WORK = ROOT / "build"
NAME = "Benefit Design Stress Lab"
SLUG = "BenefitDesignStressLab"
LOG = Path.home() / ".benefit-stress-lab" / "desktop.log"
INNO_SETUP = r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe"


def bundled(source: str, target: str) -> str:
    return f"{ROOT / source}{os.pathsep}{target}"


def executable() -> Path:
    if sys.platform == "darwin":
        return DIST / f"{NAME}.app" / "Contents" / "MacOS" / NAME
    return DIST / NAME / (f"{NAME}.exe" if sys.platform == "win32" else NAME)


def build() -> None:
    for cache in (ROOT / "app").rglob("__pycache__"):
        shutil.rmtree(cache)
    arguments = [
        str(DESKTOP / "launcher.py"),
        "--name",
        NAME,
        "--windowed",
        "--noconfirm",
        "--clean",
        "--distpath",
        str(DIST),
        "--workpath",
        str(WORK / "pyinstaller"),
        "--specpath",
        str(WORK),
        "--paths",
        str(ROOT / "src"),
        "--add-data",
        bundled("app", "app"),
        "--add-data",
        bundled(".streamlit/config.toml", ".streamlit"),
        "--add-data",
        bundled("METHODOLOGY.md", "."),
        "--collect-all",
        "streamlit",
        "--collect-all",
        "plotly",
        "--collect-submodules",
        "benefit_stress_lab",
        "--copy-metadata",
        "streamlit",
        "--hidden-import",
        "webview",
    ]
    if sys.platform == "darwin":
        arguments += ["--osx-bundle-identifier", "com.qbranch800.benefitdesignstresslab"]
    icon = DESKTOP / ("icon.icns" if sys.platform == "darwin" else "icon.ico")
    if icon.exists():
        arguments += ["--icon", str(icon)]
    PyInstaller.__main__.run(arguments)
    if sys.platform == "darwin":
        stamp_version(DIST / f"{NAME}.app")


def stamp_version(app: Path) -> None:
    plist = app / "Contents" / "Info.plist"
    with plist.open("rb") as handle:
        info = plistlib.load(handle)
    info["CFBundleShortVersionString"] = MODEL_VERSION
    info["CFBundleVersion"] = MODEL_VERSION
    with plist.open("wb") as handle:
        plistlib.dump(info, handle)
    subprocess.run(["codesign", "--force", "--deep", "--sign", "-", str(app)], check=True)


def check() -> None:
    completed = subprocess.run([str(executable()), "--check"], timeout=1200)
    if completed.returncode != 0:
        if LOG.exists():
            print(LOG.read_text(encoding="utf-8", errors="replace")[-8000:])
        raise SystemExit("The packaged app failed its self-check.")
    print("The packaged app passed its self-check.")


def package() -> Path:
    if sys.platform == "darwin":
        staging = WORK / "dmg"
        shutil.rmtree(staging, ignore_errors=True)
        staging.mkdir(parents=True)
        shutil.copytree(DIST / f"{NAME}.app", staging / f"{NAME}.app", symlinks=True)
        os.symlink("/Applications", staging / "Applications")
        target = DIST / f"{SLUG}-macOS.dmg"
        target.unlink(missing_ok=True)
        subprocess.run(
            [
                "hdiutil",
                "create",
                "-volname",
                NAME,
                "-srcfolder",
                str(staging),
                "-ov",
                "-format",
                "UDZO",
                str(target),
            ],
            check=True,
        )
        return target
    if sys.platform == "win32":
        compiler = shutil.which("iscc") or INNO_SETUP
        script = str(DESKTOP / "installer.iss")
        subprocess.run([compiler, f"/DAppVersion={MODEL_VERSION}", script], check=True)
        return DIST / f"{SLUG}-Setup.exe"
    raise SystemExit("Packaging is supported on macOS and Windows only.")


def main() -> None:
    parser = argparse.ArgumentParser(description=f"Build the {NAME} desktop app.")
    parser.add_argument("--check", action="store_true", help="run the packaged app's self-check")
    parser.add_argument(
        "--no-package", action="store_true", help="skip the installer or disk image"
    )
    options = parser.parse_args()
    build()
    if options.check:
        check()
    if not options.no_package:
        print("Created", package())


if __name__ == "__main__":
    main()
