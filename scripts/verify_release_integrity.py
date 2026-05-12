from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "manifest.json"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def git_tracked_files() -> list[str] | None:
    try:
        out = subprocess.check_output(
            ["git", "-C", str(ROOT), "ls-files"],
            text=True,
            encoding="utf-8",
            errors="replace",
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        return None
    return [line.strip() for line in out.splitlines() if line.strip()]


def main() -> None:
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    errors: list[str] = []

    tracked_files = git_tracked_files()
    tracked = set(tracked_files or [])
    manifest_targets = {entry["target"].replace("\\", "/") for entry in data.get("files", [])}
    top_targets = {entry["target"].replace("\\", "/") for entry in data.get("top_level_files", [])}

    expected_top = {
        ".gitignore",
        "LICENSE",
        "README.md",
        "REPRODUCE.md",
        "MANIFEST.md",
        ".gitattributes",
        "strong_evidence_overview.csv",
        "ap_prototype_status.txt",
        "CITATION.cff",
        "GITHUB_RELEASE_CHECKLIST.md",
    }
    for name in expected_top:
        if tracked_files is not None and name not in tracked:
            errors.append(f"missing tracked top-level file: {name}")
        if not (ROOT / name).exists():
            errors.append(f"missing top-level file: {name}")

    for entry in data.get("files", []) + data.get("top_level_files", []):
        target = entry["target"].replace("\\", "/")
        path = ROOT / target
        if not path.exists():
            errors.append(f"manifest target missing: {target}")
            continue
        actual_size = path.stat().st_size
        actual_sha = sha256_file(path)
        if actual_size != entry["bytes"]:
            errors.append(f"size mismatch: {target}: manifest={entry['bytes']} actual={actual_size}")
        if actual_sha.lower() != entry["sha256"].lower():
            errors.append(f"sha256 mismatch: {target}")

    for target in manifest_targets:
        if tracked_files is not None and target not in tracked:
            errors.append(f"manifest file not tracked by git: {target}")

    patch = data.get("prototype_delta", {})
    if patch:
        patch_path = ROOT / patch["patch"].replace("\\", "/")
        if not patch_path.exists():
            errors.append(f"prototype delta patch missing: {patch_path}")
        else:
            if patch_path.stat().st_size != patch["bytes"]:
                errors.append("prototype delta size mismatch")
            if sha256_file(patch_path).lower() != patch["sha256"].lower():
                errors.append("prototype delta sha256 mismatch")

    if tracked_files is not None:
        untracked_relevant = sorted(
            p for p in tracked
            if p not in manifest_targets
            and p not in top_targets
            and p != "manifest.json"
            and not p.startswith("experiments/")
            and not p.startswith("paper_quality_charts_v02/")
            and not p.startswith("prototype_delta/")
            and not p.startswith("scripts/")
        )
        if untracked_relevant:
            errors.append(f"unexpected tracked root files not listed in top_level_files: {untracked_relevant}")

    if errors:
        print("Release integrity check FAILED:")
        for error in errors:
            print(f"- {error}")
        raise SystemExit(1)

    print("Release integrity check passed.")
    if tracked_files is None:
        print("tracked_files=unavailable (zip/extracted tree mode)")
    else:
        print(f"tracked_files={len(tracked)}")
    print(f"manifest_files={len(manifest_targets)}")
    print(f"top_level_files={len(top_targets)}")
    print(f"total_judgement_records={data.get('total_judgement_records')}")


if __name__ == "__main__":
    main()
