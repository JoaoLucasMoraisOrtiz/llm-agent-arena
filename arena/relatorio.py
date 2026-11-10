"""Relatórios em Markdown: placar, Elo, métricas de realismo, honestidade, memória, custo."""
import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path


def transcricao_md(db, call_id: str) -> str:
    call = db.um("SELECT * FROM calls WHERE id=?", (call_id,))
    j = db.um("SELECT * FROM jornadas WHERE id=?", (call["jornada_id"],))
    cen = json.loads(j["cenario"])
    det = json.loads(call["detalhe"])
    linhas = [f"# {call_id}", "",
              f"- **Empresa:** {cen['empresa']['nome']} ({cen['empresa']['setor']}) · **Produto:** {cen['produto_id']}",
              f"- **Comprador:** {cen['comprador']['nome']}, {cen['cargo']} ({cen['papel']}, estilo {cen['comprador']['estilo']}, nível técnico {cen['nivel_tecnico']})",
              f"- **Vendedor:** {cen['vendedor']['nome']} (estilo {cen['vendedor']['estilo']}) · {j['vendedor']} vs {j['comprador']}",
              f"- **Oculto:** fit {cen['fit']} · orçamento R$ {cen['orcamento']:,} · piso R$ {cen['piso']:,} · tabela R$ {cen['preco_tabela']:,}",
              f"- **Resultado:** {call['resultado']:+d} ({det['explicacao']}) · fim: {call['motivo_fim']} · acordo: {det.get('acordo')}",
              f"- **Métricas:** {json.dumps(det['metricas'], ensure_ascii=False)}", "", "## Transcrição", ""]
    for t in db.todos("SELECT * FROM turnos WHERE call_id=? ORDER BY n", (call_id,)):
        quem = "🟦 V" if t["agente"] == "vendedor" else "🟧 C"
        linhas.append(f"**[{t['n']}] {quem}:** {t['fala']}")
        if t["pensamento"]:
            linhas.append(f"> _pensamento:_ {t['pensamento'][:300]}")
        acoes = json.loads(t["acoes"] or "[]")
        if acoes:
            linhas.append(f"> _ações:_ `{json.dumps(acoes, ensure_ascii=False)}`")
        linhas.append("")
    af = db.um("SELECT conteudo FROM afirmacoes WHERE call_id=?", (call_id,))
    if af:
        ruins = [a for a in json.loads(af["conteudo"]) if a.get("classe") not in ("verdadeira", "nao_verificavel")]
        if ruins:
            linhas += ["## Afirmações problemáticas", ""] + [
                f"- [{a.get('turno')}] {a.get('classe')} (material={a.get('material')}): {a.get('citacao')}" for a in ruins]
    return "\n".join(linhas)


def exportar_transcricoes(db, pasta: Path):
    pasta.mkdir(parents=True, exist_ok=True)
    for r in db.todos("SELECT id FROM calls"):
        (pasta / f"{r['id']}.md").write_text(transcricao_md(db, r["id"]), encoding="utf-8")


def resumo(db) -> str:
    L = ["# Relatório da Arena", ""]
    jornadas = db.todos("SELECT * FROM jornadas")
    validas = [j for j in jornadas if j["status"] == "concluida"]
    L.append(f"**Jornadas:** {len(jornadas)} (válidas: {len(validas)}; status: {dict(Counter(j['status'] for j in jornadas))})")
    tok = db.um("SELECT SUM(contado) c, SUM(cache_read) r, SUM(input) i, SUM(output) o FROM uso_tokens")
    L.append(f"**Tokens contados:** {tok['c'] or 0:,} (entrada {tok['i'] or 0:,} + saída {tok['o'] or 0:,}); cache lido (não conta): {tok['r'] or 0:,}")
    if validas:
        por_j = [json.loads(j["detalhe"]).get("tokens_contados", 0) for j in validas]
        L.append(f"**Tokens por jornada:** média {statistics.mean(por_j):,.0f} · máx {max(por_j):,}")
    comp = db.todos("SELECT componente, SUM(contado) c, COUNT(*) n FROM uso_tokens GROUP BY componente ORDER BY c DESC")
    L += ["", "| componente | chamadas | tokens contados |", "|---|---|---|"] + [f"| {r['componente']} | {r['n']} | {r['c']:,} |" for r in comp]

    L += ["", "## Placar por rodada", "", "| rodada | jornadas | placar médio | V vence | empate | C vence |", "|---|---|---|---|---|---|"]
    por_rodada = defaultdict(list)
    for j in validas:
        por_rodada[j["rodada"]].append(j["placar"])
    for r, ps in sorted(por_rodada.items()):
        L.append(f"| {r} | {len(ps)} | {statistics.mean(ps):+.2f} | {sum(p > 0 for p in ps)} | {sum(p == 0 for p in ps)} | {sum(p < 0 for p in ps)} |")

    L += ["", "## Placar por estágio", "", "| estágio | calls | média | +1 | 0 | −1 | motivos de fim |", "|---|---|---|---|---|---|---|"]
    calls = db.todos("SELECT c.* FROM calls c JOIN jornadas j ON j.id=c.jornada_id WHERE j.status='concluida'")
    for est in ("cold_call", "discovery", "fechamento"):
        cs = [c for c in calls if c["estagio"] == est]
        if cs:
            rs = [c["resultado"] for c in cs]
            L.append(f"| {est} | {len(cs)} | {statistics.mean(rs):+.2f} | {rs.count(1)} | {rs.count(0)} | {rs.count(-1)} | "
                     f"{dict(Counter(c['motivo_fim'] for c in cs))} |")

    L += ["", "## Realismo (âncoras: fala do vendedor ~43%, 11-14 perguntas na discovery, falas curtas)", "",
          "| estágio | fala vendedor % | perguntas vendedor | mediana palavras V | mediana palavras C | falas >70 palavras | erros formato | inversões | afirmações falsas | exageros |",
          "|---|---|---|---|---|---|---|---|---|---|"]
    for est in ("cold_call", "discovery", "fechamento"):
        ms = [json.loads(c["metricas"]) for c in calls if c["estagio"] == est]
        if ms:
            f = lambda k: statistics.mean(m[k] for m in ms)
            L.append(f"| {est} | {f('fala_vendedor_pct'):.0f} | {f('perguntas_vendedor'):.1f} | {f('mediana_palavras_vendedor'):.0f} | "
                     f"{f('mediana_palavras_comprador'):.0f} | {f('falas_longas'):.1f} | {f('erros_formato'):.2f} | "
                     f"{statistics.mean(sum(m['inversoes'].values()) for m in ms):.2f} | {f('afirmacoes_falsas'):.2f} | {f('exageros'):.2f} |")

    L += ["", "## Elo por linhagem e versão", "", "| linhagem | versão | Elo | partidas | lições ativas |", "|---|---|---|---|---|"]
    for v in db.todos("SELECT * FROM versoes ORDER BY linhagem_id, numero"):
        n = db.um("""SELECT COUNT(*) n FROM licoes WHERE linhagem_id=? AND versao_criada<=?
                     AND (versao_aposentada IS NULL OR versao_aposentada>?)""", (v["linhagem_id"], v["numero"], v["numero"]))["n"]
        L.append(f"| {v['linhagem_id']} | v{v['numero']} | {v['elo']:.0f} | {v['partidas']} | {n} |")

    L += ["", "## Lições mais usadas", ""]
    for l in db.todos("SELECT * FROM licoes ORDER BY aplicada DESC, alpha DESC LIMIT 12"):
        L.append(f"- **{l['linhagem_id']}** [{l['id']}] α={l['alpha']:.0f} β={l['beta']:.0f} usos={l['aplicada']}/{l['recuperada']}: {l['acao']}")
    for v in db.todos("SELECT linhagem_id, numero, playbook FROM versoes WHERE playbook != '' ORDER BY numero DESC LIMIT 2"):
        L += ["", f"### Playbook {v['linhagem_id']} v{v['numero']}", "", v["playbook"]]
    return "\n".join(L)
