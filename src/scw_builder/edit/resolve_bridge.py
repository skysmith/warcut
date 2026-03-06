from __future__ import annotations

from pathlib import Path


def write_resolve_script_stub(output_path: Path, episode_id: str) -> Path:
    script = f"""from pathlib import Path

def main():
    raise SystemExit(
        "Resolve bridge for {episode_id} is a stub in v1. Run Resolve and "
        "replace this with GetResolve() timeline creation logic."
    )

if __name__ == "__main__":
    main()
"""
    output_path.write_text(script, encoding="utf-8")
    return output_path
