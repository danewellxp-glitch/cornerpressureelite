"""Extrai responses gismo do .mitm golden para fixtures JSON.

Uso (após o spike trazer o `.mitm`):

    python scripts/extract_fixtures.py
    python scripts/extract_fixtures.py --mitm docs/sprints/captures/foo.mitm

Saída: `tests/providers/sportradar/fixtures/<endpoint>_<match_id>.json`,
1 arquivo por (endpoint, match_id) — primeira ocorrência apenas.

Harness Fase A §5.8.

Requer `mitmproxy` instalado (`pip install mitmproxy`) — não é dependência
do projeto principal, é só para este utilitário.
"""
import argparse
import json
import re
import sys
from pathlib import Path

# Permite rodar da raiz do projeto.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

WANTED_ENDPOINTS = {
    "match_info",
    "match_detailsextended",
    "match_timeline",
    "match_timelinedelta",
    "stats_match_situation",
    "stats_match_form",
    "stats_season_meta",
    "stats_season_uniqueteamstats",
    "stats_season_tables",
    "stats_cup_brackets",
}

# Caminho do .mitm relativo à raiz do repo
DEFAULT_MITM = Path(
    "../docs/sprints/captures/2026-05-12-betano-flow.mitm"
)
DEFAULT_OUT = Path("tests/providers/sportradar/fixtures")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--mitm",
        default=str(DEFAULT_MITM),
        help=f"Caminho do .mitm (default: {DEFAULT_MITM})",
    )
    ap.add_argument(
        "--out",
        default=str(DEFAULT_OUT),
        help=f"Diretório de fixtures (default: {DEFAULT_OUT})",
    )
    ap.add_argument(
        "--overwrite",
        action="store_true",
        help="Sobrescreve fixtures existentes (default: pula)",
    )
    args = ap.parse_args()

    try:
        from mitmproxy import io as mitm_io
    except ImportError:
        print(
            "ERRO: mitmproxy não instalado. Rode: pip install mitmproxy",
            file=sys.stderr,
        )
        return 2

    mitm_path = Path(args.mitm).resolve()
    out_dir = Path(args.out).resolve()

    if not mitm_path.exists():
        print(f"ERRO: arquivo .mitm não encontrado: {mitm_path}",
              file=sys.stderr)
        return 1

    out_dir.mkdir(parents=True, exist_ok=True)

    path_re = re.compile(r"/gismo/([^/]+)/([^/?]+)")
    written = 0
    skipped_existing = 0
    skipped_unwanted = 0

    with open(mitm_path, "rb") as f:
        for flow in mitm_io.FlowReader(f).stream():
            if not hasattr(flow, "response") or not flow.response:
                continue
            if "widgets.fn.sportradar.com" not in flow.request.host:
                continue
            m = path_re.search(flow.request.path)
            if not m:
                continue
            endpoint, raw_id = m.group(1), m.group(2)
            if endpoint not in WANTED_ENDPOINTS:
                skipped_unwanted += 1
                continue
            # IDs como "gm-12345" (cup_brackets) viram safe-name
            safe_id = raw_id.replace("/", "_")
            fname = out_dir / f"{endpoint}_{safe_id}.json"
            if fname.exists() and not args.overwrite:
                skipped_existing += 1
                continue
            try:
                data = flow.response.json()
            except Exception as e:
                print(f"warn: response não-JSON em {endpoint}/{raw_id}: "
                      f"{e}", file=sys.stderr)
                continue
            with open(fname, "w", encoding="utf-8") as out_f:
                json.dump(data, out_f, indent=2, ensure_ascii=False)
            written += 1
            print(f"wrote {fname.relative_to(Path.cwd())}")

    print(f"\nResumo: {written} fixtures escritas, "
          f"{skipped_existing} já existiam, "
          f"{skipped_unwanted} endpoints fora do escopo")
    return 0


if __name__ == "__main__":
    sys.exit(main())
