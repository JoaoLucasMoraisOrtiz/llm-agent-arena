import os
from pathlib import Path

import yaml

RAIZ = Path(__file__).resolve().parent
DADOS = RAIZ / "dados"


def carregar(caminho: Path | None = None) -> dict:
    return yaml.safe_load(open(caminho or RAIZ / "config.yaml", encoding="utf-8"))


CFG = carregar(Path(os.environ["ARENA_CONFIG"]) if os.environ.get("ARENA_CONFIG") else None)
