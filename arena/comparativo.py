"""Comparativo entre ligas (ex.: crítico realista × onisciente).

  python -m arena.comparativo runs/liga_A_realista.db runs/liga_B_onisciente.db > runs/comparativo.md
"""
import json
import sqlite3
import statistics
import sys
from pathlib import Path


def carregar(db_path: str) -> dict:
    c = sqlite3.connect(db_path)
    c.row_factory = sqlite3.Row
    nome = Path(db_path).stem
    evol = Path(db_path).with_suffix("") / "evolucao.jsonl"
    avaliacoes = []
    if evol.exists():
        avaliacoes = [json.loads(l) for l in evol.read_text().splitlines() if '"avaliacao"' in l]
    rodadas = c.execute("""SELECT rodada, COUNT(*) n, AVG(placar) m, SUM(placar>0) v, SUM(placar=0) e, SUM(placar<0) d
                           FROM jornadas WHERE status='concluida' AND rodada<900 GROUP BY rodada ORDER BY rodada""").fetchall()
    calls = c.execute("""SELECT c.estagio, c.resultado, c.metricas, j.rodada FROM calls c JOIN jornadas j ON j.id=c.jornada_id
                         WHERE j.status='concluida' AND j.rodada<900""").fetchall()
    tok = c.execute("SELECT COALESCE(SUM(contado),0) FROM uso_tokens").fetchone()[0]
    licoes = c.execute("""SELECT linhagem_id, COUNT(*) n, SUM(versao_aposentada IS NULL) ativas, SUM(aplicada) usos,
                          AVG(alpha/(alpha+beta)) q FROM licoes GROUP BY linhagem_id""").fetchall()
    final = Path(db_path).with_suffix("") / "avaliacao_final.json"
    return {"nome": nome, "rodadas": rodadas, "calls": calls, "tokens": tok, "avaliacoes": avaliacoes,
            "licoes": licoes, "final": json.loads(final.read_text()) if final.exists() else None}


def blocos(calls, tamanho=4):
    """Agrupa calls em janelas de rodadas para ver tendência."""
    por = {}
    for cl in calls:
        por.setdefault((cl["rodada"] - 1) // tamanho, []).append(cl)
    return sorted(por.items())


def md(ligas: list[dict]) -> str:
    L = ["# Comparativo das ligas", ""]
    L += ["| liga | tokens contados | jornadas válidas | placar médio geral |", "|---|---|---|---|"]
    for g in ligas:
        n = sum(r["n"] for r in g["rodadas"])
        m = sum(r["m"] * r["n"] for r in g["rodadas"]) / max(1, n)
        L.append(f"| {g['nome']} | {g['tokens']:,} | {n} | {m:+.2f} |")

    L += ["", "## Avaliação pareada contra o painel fixo v0 (a medida de aprendizado)", "",
          "Delta > 0 = a versão treinada foi melhor que a v0 nos MESMOS cenários, contra os MESMOS oponentes v0.", "",
          "| liga | após rodada | lado | média v0 | média treinada | delta pareado | melhor/igual/pior |", "|---|---|---|---|---|---|---|"]
    for g in ligas:
        for a in g["avaliacoes"]:
            t = a["tabela"]
            if "completo" in t and "v0" in t:
                L.append(f"| {g['nome']} | {a['rodada']} | {a['lado']} | {t['v0']['media']:+.2f} | {t['completo']['media']:+.2f} | "
                         f"{t['completo'].get('delta_pareado_vs_v0', 0):+.2f} | {t['completo'].get('melhor/igual/pior_que_v0')} |")

    for g in ligas:
        if g["final"]:
            L += ["", f"## Ablação final: {g['nome']}", "", "| lado | modo | n | média | delta vs v0 | melhor/igual/pior |", "|---|---|---|---|---|---|"]
            for lado, tab in g["final"].items():
                for modo, d in tab.items():
                    if isinstance(d, dict) and "media" in d:
                        L.append(f"| {lado} | {modo} | {d['n']} | {d['media']:+.2f} | {d.get('delta_pareado_vs_v0', 0):+.2f} | {d.get('melhor/igual/pior_que_v0', '')} |")

    L += ["", "## Tendência por janela de 4 rodadas (placar por estágio, honestidade e realismo)", ""]
    for g in ligas:
        L += [f"### {g['nome']}", "", "| rodadas | estágio | calls | placar médio | afirmações falsas/call | fala vendedor % | mediana palavras V |",
              "|---|---|---|---|---|---|---|"]
        for b, cs in blocos(g["calls"]):
            for est in ("cold_call", "discovery", "fechamento"):
                x = [c for c in cs if c["estagio"] == est]
                if not x:
                    continue
                ms = [json.loads(c["metricas"]) for c in x]
                L.append(f"| {4*b+1}-{4*b+4} | {est} | {len(x)} | {statistics.mean(c['resultado'] for c in x):+.2f} | "
                         f"{statistics.mean(m['afirmacoes_falsas'] for m in ms):.2f} | {statistics.mean(m['fala_vendedor_pct'] for m in ms):.0f} | "
                         f"{statistics.mean(m['mediana_palavras_vendedor'] for m in ms):.0f} |")
        L.append("")

    L += ["## Memória", "", "| liga | linhagem | lições criadas | ativas | usos creditados | qualidade média (α/(α+β)) |", "|---|---|---|---|---|---|"]
    for g in ligas:
        for l in g["licoes"]:
            L.append(f"| {g['nome']} | {l['linhagem_id']} | {l['n']} | {l['ativas']} | {l['usos'] or 0} | {l['q'] or 0:.2f} |")
    return "\n".join(L)


if __name__ == "__main__":
    print(md([carregar(p) for p in sys.argv[1:]]))
