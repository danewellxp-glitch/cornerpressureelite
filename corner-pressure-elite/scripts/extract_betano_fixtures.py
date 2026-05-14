"""Extrai responses do .mitm golden em fixtures JSON.

Lê `docs/sprints/captures/2026-05-12-betano-flow.mitm` (configurável via
--mitm) e grava cada response JSON relevante em
`corner-pressure-elite/tests/providers/betano/fixtures/<name>_<eventId>.json`.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from mitmproxy import io

# Mapeamento substring-do-path → nome do arquivo
WANTED = {
    "info/aggregated": "info_aggregated",
    "/stats/detailed": "stats_detailed",
    "/stats/players": "stats_players",
    "/momentum/": "momentum",
    "/lineups/": "lineups",
    "/h2h/": "h2h",
    "/danae-webapi/api/live/events": "live_event_latest",
    "/danae-webapi/api/live/overview/latest": "live_overview_latest",
}
# /config/ tem que ser checado por último porque é prefixo curto e bate em
# muitos paths; só queremos `/api/statsstream/{id}/config/`.
WANTED_LAST = {
    "/api/statsstream/": {"config/": "config"},
}


def classify(path: str) -> tuple[str, str] | None:
    for sub, name in WANTED.items():
        if sub in path:
            return name, path
    for prefix, subs in WANTED_LAST.items():
        if prefix in path:
            for sub, name in subs.items():
                if path.endswith(sub):
                    return name, path
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--mitm",
        default="docs/sprints/captures/2026-05-12-betano-flow.mitm",
        help="caminho relativo ao repo root",
    )
    ap.add_argument(
        "--out",
        default="corner-pressure-elite/tests/providers/betano/fixtures",
    )
    ap.add_argument("--repo-root", default=str(Path(__file__).resolve().parents[2]))
    args = ap.parse_args()

    root = Path(args.repo_root)
    mitm_path = root / args.mitm
    out_dir = root / args.out
    out_dir.mkdir(parents=True, exist_ok=True)

    if not mitm_path.exists():
        print(f"ERROR: .mitm não existe: {mitm_path}", file=sys.stderr)
        return 2

    written = 0
    seen: set[str] = set()
    with mitm_path.open("rb") as f:
        for flow in io.FlowReader(f).stream():
            if not hasattr(flow, "response") or not flow.response:
                continue
            path = flow.request.path
            cls = classify(path)
            if cls is None:
                continue
            name, full_path = cls
            m = re.search(r"/(\d{6,12})(?:/|\?|$)", full_path)
            evid = m.group(1) if m else "unknown"
            key = f"{name}_{evid}"
            if key in seen:
                continue
            try:
                data = flow.response.json()
            except Exception:
                continue
            (out_dir / f"{key}.json").write_text(
                json.dumps(data, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            seen.add(key)
            written += 1
            print(f"wrote {key}.json  (path={full_path[:80]})")

    print(f"\nTotal: {written} fixture(s) em {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
