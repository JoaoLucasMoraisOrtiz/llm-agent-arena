"""CLI da arena.

  python -m arena.cli --db runs/smoke.db sinteticas --por-base 1
  python -m arena.cli --db runs/smoke.db smoke --jornadas 5
  python -m arena.cli --db runs/liga.db liga --rodadas 4 --jornadas 12
  python -m arena.cli --db runs/liga.db relatorio
"""
import argparse
import asyncio
import random
from pathlib import Path

from .cenarios import carregar_bases, gerar_sintetica
from .db import DB
import json

from .liga import avaliar, continuo, inicializar_linhagens, rodada
from .llm import LLM
from .relatorio import exportar_transcricoes, resumo


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="runs/arena.db")
    ap.add_argument("--seed", type=int, default=7)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("sinteticas"); s.add_argument("--por-base", type=int, default=1)
    s = sub.add_parser("smoke"); s.add_argument("--jornadas", type=int, default=5); s.add_argument("--concorrencia", type=int, default=5)
    s.add_argument("--inicio", default=None)
    s = sub.add_parser("liga")
    s.add_argument("--rodadas", type=int, default=2); s.add_argument("--jornadas", type=int, default=12)
    s.add_argument("--concorrencia", type=int, default=4); s.add_argument("--inicio", type=int, default=1)
    s = sub.add_parser("avaliar")
    s.add_argument("--lado", default="vendedor"); s.add_argument("--versao", type=int, default=None)
    s.add_argument("--n", type=int, default=12); s.add_argument("--modos", default="v0,completo,so_playbook,so_licoes")
    s.add_argument("--concorrencia", type=int, default=8)
    s = sub.add_parser("continuo")
    s.add_argument("--jornadas", type=int, default=16); s.add_argument("--concorrencia", type=int, default=6)
    s.add_argument("--avaliar-a-cada", type=int, default=6); s.add_argument("--n-avaliacao", type=int, default=8)
    s.add_argument("--permitir-mudanca-regras", action="store_true")
    s = sub.add_parser("deriva"); s.add_argument("--rodadas", default=None, help="ex.: 1-14 (padrão: todas)")
    sub.add_parser("regras")
    sub.add_parser("relatorio")
    a = ap.parse_args()

    Path(a.db).parent.mkdir(parents=True, exist_ok=True)
    db = DB(a.db)
    llm = LLM(db) if a.cmd not in ("deriva", "regras", "relatorio") else None
    rng = random.Random(a.seed)
    saida = Path(a.db).with_suffix("")

    if a.cmd == "sinteticas":
        bases = carregar_bases()
        tarefas = [gerar_sintetica(llm, db, b, random.Random(rng.random())) for b in bases.values() for _ in range(a.por_base)]
        for e in await asyncio.gather(*tarefas):
            print(f"  {e['id']}: {e['nome']} ({e['setor']}, {e['porte']}, maturidade {e['maturidade_digital']})")
    elif a.cmd == "smoke":
        inicializar_linhagens(db)
        r = await rodada(llm, db, 0, "vendedor", a.jornadas, rng, concorrencia=a.concorrencia, consolidar_fim=False,
                         inicio_fixo=a.inicio)
        print(r)
    elif a.cmd == "liga":
        inicializar_linhagens(db)
        for i in range(a.inicio, a.inicio + a.rodadas):
            lado = "vendedor" if i % 2 == 1 else "comprador"
            print(f"== rodada {i} (aprende: {lado}) ==")
            r = await rodada(llm, db, i, lado, a.jornadas, rng, concorrencia=a.concorrencia)
            print(f"   placar médio {r['placar_medio']:+.2f} em {r['validas']} jornadas válidas; "
                  f"tokens contados até agora: {llm.gasto_global:,}")
    elif a.cmd == "continuo":
        from .congelamento import conferir
        print(f"regras congeladas: {conferir(db, a.permitir_mudanca_regras)}")
        await continuo(llm, db, rng, a.jornadas, a.concorrencia, a.avaliar_a_cada, a.n_avaliacao, saida)
    elif a.cmd == "deriva":
        from .deriva import com_alarme
        rs = [r["rodada"] for r in db.todos("SELECT DISTINCT rodada FROM jornadas WHERE rodada < 900 ORDER BY rodada")]
        if a.rodadas:
            i, f = (int(x) for x in a.rodadas.split("-"))
            rs = [r for r in rs if i <= r <= f]
        for r in rs:
            p = com_alarme(db, r)
            print(json.dumps({k: v for k, v in p.items() if k != "faixas"}, ensure_ascii=False))
    elif a.cmd == "regras":
        from .congelamento import hash_regras
        print(hash_regras())
    elif a.cmd == "avaliar":
        tab = await avaliar(llm, db, a.lado, a.versao, a.n, a.modos.split(","), rng, concorrencia=a.concorrencia)
        print(json.dumps(tab, ensure_ascii=False, indent=1))
        (saida / f"avaliacao_{a.lado}.json").parent.mkdir(parents=True, exist_ok=True)
        (saida / f"avaliacao_{a.lado}.json").write_text(json.dumps(tab, ensure_ascii=False, indent=1))
    if a.cmd in ("smoke", "liga", "relatorio", "continuo"):
        exportar_transcricoes(db, saida / "transcricoes")
        (saida / "relatorio.md").write_text(resumo(db), encoding="utf-8")
        print(f"relatório: {saida / 'relatorio.md'}")


if __name__ == "__main__":
    asyncio.run(main())
