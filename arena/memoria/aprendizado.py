"""Crítico (pós-call) e consolidador ("sono", fim de rodada). Ver prompts_e_tecnicas.md §5.4-5.5."""
import json

from ..config import CFG
from ..util import extrair_json

T = CFG["modelo"]["temperatura"]["juiz"]


def _transcricao_com_pensamentos(turnos: list[dict], lado: str, nomes: dict) -> str:
    linhas = []
    for i, t in enumerate(turnos):
        marca = " [MENTORADO]" if t["agente"] == lado else ""
        linhas.append(f"[{i}] {nomes[t['agente']]}{marca}: {t['fala']}")
        if t["agente"] == lado and t.get("pensamento"):
            linhas.append(f"     (pensamento do mentorado: {t['pensamento'][:400]})")
    return "\n".join(linhas)


async def criticar(llm, *, lado: str, nome: str, estilo: str, estagio: str, resultado: int, explicacao: str,
                   turnos: list[dict], nomes: dict, licoes: list[dict], ocultas: str | None,
                   afirmacoes_falsas: list[dict], jornada_id: str, call_id: str) -> dict:
    area = "vendas B2B" if lado == "vendedor" else "compras corporativas"
    placar = {1: "vitória do vendedor", 0: "empate", -1: "vitória do comprador"}[resultado]
    bom_para_mentorado = (resultado == 1) == (lado == "vendedor") and resultado != 0
    ocultas_txt = f"\nInformações do outro lado reveladas agora (o mentorado não sabia): {ocultas}" if ocultas else ""
    falsas = "; ".join(f"[{a.get('turno')}] {a.get('citacao')} ({a.get('classe')})" for a in afirmacoes_falsas) or "nenhuma"
    licoes_txt = "\n".join(f"- {l['id']}: {l['acao']}" for l in licoes) or "(nenhuma)"
    regra_lado = ("- Nunca escreva uma lição cujo sucesso dependa de uma afirmação falsa ou exagerada sobre o produto."
                  if lado == "vendedor" else
                  "- A lição precisa manter o comportamento realista: um comprador real, com os mesmos incentivos, faria isso. "
                  "Encerrar ligações de cara ou recusar tudo por princípio não é realista.\n"
                  "- O bom comprador DISCRIMINA: filtrar rápido quem não resolve uma dor real é acerto; dispensar um vendedor "
                  "competente cuja solução resolve uma dor real sua é ERRO (você perde a solução e o problema continua). "
                  "Condicione a lição a sinais observáveis de fit, e evite regras universais ('sempre', 'em qualquer estágio', "
                  "'com qualquer vendedor').")
    quem = ("o VENDEDOR da ligação. As lições são para ele vender melhor."
            if lado == "vendedor" else
            "o CLIENTE (gestor comprador) da ligação, NÃO o vendedor. As lições são para ele comprar melhor: "
            "filtrar fornecedores, testar competência, extrair informação, negociar preço e condições, proteger o "
            "orçamento e não levar adiante o que não serve. Nunca escreva lições sobre como vender.")
    p = f"""<papel>Você é um coach experiente de {area}, revisando a gravação de uma ligação com o seu mentorado, {nome} (estilo: {estilo}).
O seu mentorado é {quem}</papel>

<o_que_aconteceu>
Estágio: {estagio}. Resultado objetivo: {placar} ({explicacao}). Para o mentorado, isso foi {"um bom resultado" if bom_para_mentorado else ("neutro" if resultado == 0 else "um mau resultado")}.{ocultas_txt}
Afirmações falsas ou exageradas do vendedor identificadas: {falsas}
</o_que_aconteceu>

<transcricao_com_pensamentos>
{_transcricao_com_pensamentos(turnos, lado, nomes)}
</transcricao_com_pensamentos>

<licoes_que_ele_tinha>
{licoes_txt}
</licoes_que_ele_tinha>

<tarefa>
Parte 1. Para cada lição recebida, diga se ela foi aplicada (cite o turno) e se ajudou ou atrapalhou neste caso. "Não aplicada" é uma resposta válida.
Parte 2. Identifique de 1 a 3 momentos decisivos (turnos em que o resultado foi realmente definido).
Parte 3. Escreva de 0 a 3 lições NOVAS que um profissional levaria desta ligação para as próximas.
</tarefa>

<regras_para_licoes>
- Condicional e transferível: a condição descreve a situação por atributos; a ação é concreta; o porquê explica o mecanismo.
- Nunca cite nomes de empresas, pessoas ou valores em reais deste caso. Uma lição que só vale para esta empresa não é lição.
- Precisa ser uma ação executável numa ligação, não um conselho vago ("seja mais empático").
- Só escreva lições com evidência nesta ligação. Se não houve nada novo, devolva lista vazia.
- O vendedor não escolhe para quem liga nem o produto que vende: a lista de prospecção é dada. Lições do tipo "não ligue para empresas sem fit" não são acionáveis; escreva o que fazer DENTRO da ligação (ex.: como qualificar rápido e sair com elegância).
{regra_lado}
- Cada lição é escrita do ponto de vista do mentorado ({lado}); o campo "para" deve ser "{lado}". "estilo_oponente" é o estilo do OUTRO lado.
- Valores válidos na condição (use null para "qualquer"): setor ∈ {{varejo, industria, mobilidade, agro, saude}}; porte ∈ {{media, grande}}; maturidade_digital ∈ {{baixa, media, alta}}; cargo ∈ {{CTO, CFO, COO, Diretor de Compras, Diretor Comercial}}; papel ∈ {{decisor, influenciador}}; estagio ∈ {{cold_call, discovery, fechamento}}; estilo_oponente ∈ {{analitico, politico, negociador, ocupado, consultivo, challenger, tecnico, fechador}}.
</regras_para_licoes>

Responda só em JSON:
{{"creditos": [{{"licao_id": "...", "aplicada": true, "turno": 5, "efeito": "ajudou|atrapalhou|neutro", "evidencia": "..."}}],
 "momentos_decisivos": [{{"turno": 7, "porque": "..."}}],
 "licoes_novas": [{{"condicao": {{"setor": null, "porte": null, "maturidade_digital": null, "cargo": "CFO", "papel": null, "estagio": "discovery", "estilo_oponente": null}},
                   "tipo": "fazer|evitar", "tema": "abertura|descoberta|objecao|preco|fechamento|relacionamento",
                   "acao": "...", "porque": "...", "tecnicas": ["V-SPIN-I"], "para": "{lado}"}}]}}"""
    txt = await llm.chamar(sistema=[], usuario=[p], temperatura=T, max_tokens=3000, componente=f"critico_{lado}",
                           jornada_id=jornada_id, call_id=call_id)
    try:
        return extrair_json(txt)
    except Exception:
        return {"creditos": [], "momentos_decisivos": [], "licoes_novas": [], "erro": txt[:500]}


async def juiz_realismo(llm, lessons: list[dict], estilo: str) -> set[int]:
    """Fase 0.4: uma chamada por linhagem de comprador por rodada. Devolve os índices das lições reprovadas."""
    if not lessons:
        return set()
    txt = "\n".join(f"[{i}] cond={json.dumps({k: v for k, v in (l.get('condicao') or {}).items() if v}, ensure_ascii=False)} | "
                    f"{l.get('tipo')}: {l.get('acao')} | porque {l.get('porque')}" for i, l in enumerate(lessons))
    p = f"""<tarefa>Você avalia o REALISMO de regras de comportamento de um gestor comprador corporativo brasileiro (estilo {estilo}), que atende ligações e reuniões de fornecedores B2B.</tarefa>
<pergunta>Para cada regra: um gestor real, com incentivos normais (entregar resultado, proteger o orçamento, não perder uma solução que resolve um problema dele), agiria assim NA MAIORIA DAS VEZES, na situação descrita pela condição?</pergunta>
<reprove>
- regras que recusam, encerram ou bloqueiam por princípio, sem depender de sinais observáveis de falta de fit ou de competência;
- regras que tornam o comprador mais duro do que o mercado real (ex.: nunca revelar nada, encerrar em segundos qualquer abordagem);
- regras que só fazem sentido para vencer o jogo, e não para comprar bem.
</reprove>
<regras>
{txt}
</regras>
Responda só em JSON: {{"reprovadas": [{{"indice": 0, "motivo": "..."}}]}}"""
    try:
        d = extrair_json(await llm.chamar(sistema=[], usuario=[p], temperatura=T, max_tokens=1500, componente="juiz_realismo"))
        return {int(r["indice"]) for r in d.get("reprovadas", []) if str(r.get("indice", "")).isdigit() or isinstance(r.get("indice"), int)}
    except Exception:
        return set()


async def consolidar(llm, db, mem, linhagem: str, versao_atual: int, rodada: int) -> dict:
    """Gera a versão v+1 da memória da linhagem a partir do staging da rodada."""
    nova = versao_atual + 1
    ativas = mem.ativas(linhagem, versao_atual)
    staging = [json.loads(r["conteudo"]) | {"_call": r["call_id"]}
               for r in db.todos("SELECT * FROM staging WHERE rodada=? AND linhagem_id=?", (rodada, linhagem))]
    playbook = mem.playbook(linhagem, versao_atual)
    cfgm = CFG["memoria"]

    relatorio = {"linhagem": linhagem, "de": versao_atual, "para": nova, "candidatas": len(staging),
                 "novas": 0, "fundidas": 0, "generalizadas": 0, "aposentadas": 0}

    if staging:
        ativas_txt = "\n".join(
            f"- {l['id']} | cond={json.dumps({k: v for k, v in l['condicao'].items() if v}, ensure_ascii=False)} | "
            f"{l['tipo']}: {l['acao']} | porque {l['porque']} | α={l['alpha']:.0f} β={l['beta']:.0f} usos={l['aplicada']}"
            for l in ativas) or "(nenhuma)"
        cand_txt = "\n".join(
            f"- C{i} | cond={json.dumps({k: v for k, v in c.get('condicao', {}).items() if v}, ensure_ascii=False)} | "
            f"{c.get('tipo')}: {c.get('acao')} | porque {c.get('porque')} | call={c['_call']}"
            for i, c in enumerate(staging))
        lado, estilo = linhagem.split("/")
        quem = (f"um(a) VENDEDOR(A) B2B de estilo {estilo}" if lado == "vendedor" else
                f"um(a) GESTOR(A) COMPRADOR(A) corporativo(a) de estilo {estilo}, que é o CLIENTE nas ligações de venda "
                f"(o caderno ensina a comprar e negociar melhor, nunca a vender)")
        p = f"""<papel>Você mantém o caderno de experiência profissional de {quem}. É o que ele(a) consulta antes de cada ligação.</papel>

<licoes_ativas>
{ativas_txt}
</licoes_ativas>

<candidatas_desta_rodada>
{cand_txt}
</candidatas_desta_rodada>

<playbook_atual>
{playbook or "(vazio)"}
</playbook_atual>

<tarefa>
1. FUNDIR: candidata que diz o mesmo que uma lição ativa vira evidência dela (não duplique).
2. AGRUPAR: candidatas que dizem o mesmo entre si viram UMA lição nova, com a união das evidências.
3. GENERALIZAR: se 2 ou mais lições (ativas ou novas) dizem o mesmo para setores/cargos diferentes, proponha uma versão com condição mais ampla (use null) e indique quais ela substitui.
4. As demais candidatas válidas viram lições novas (reescreva para ficarem claras e acionáveis).
5. PLAYBOOK: reescreva o playbook (máximo 600 tokens, 6 a 10 princípios, primeira pessoa: "Com CFOs, eu abro por...") a partir das lições com mais evidência e das novas. Princípios gerais, não casos.
</tarefa>
<regras>
- Nunca cite nomes de empresas, pessoas ou valores em reais.
- Descarte candidatas vagas, que contradizem o realismo do papel, ou que foram escritas para o OUTRO lado da mesa.
- Mantenha os valores de condição do vocabulário original (setor, porte, maturidade_digital, cargo, papel, estagio, estilo_oponente).
</regras>

Responda só em JSON:
{{"fusoes": [{{"candidata": "C0", "licao_id": "L-..."}}],
 "novas": [{{"de_candidatas": ["C1", "C3"], "condicao": {{...}}, "tipo": "fazer|evitar", "tema": "...", "acao": "...", "porque": "...", "tecnicas": []}}],
 "generalizacoes": [{{"substitui": ["L-...", "L-..."], "condicao": {{...}}, "tipo": "...", "tema": "...", "acao": "...", "porque": "...", "tecnicas": []}}],
 "playbook": "..."}}"""
        d = None
        for _ in range(2):
            txt = await llm.chamar(sistema=[], usuario=[p], temperatura=T, max_tokens=12000,
                                   componente="consolidador", jornada_id=None)
            try:
                d = extrair_json(txt)
                break
            except Exception:
                continue
        if d is None:   # fallback: candidatas validadas entram como lições novas, sem fusão
            relatorio["fallback"] = True
            d = {"fusoes": [], "generalizacoes": [], "playbook": playbook,
                 "novas": [{**c, "de_candidatas": [f"C{i}"]} for i, c in enumerate(staging)]}
        idx = {f"C{i}": c for i, c in enumerate(staging)}
        # Fase 0.4: filtro por regra + juiz de realismo (1 chamada) antes de qualquer lição nova do comprador entrar
        relatorio["reprovadas_realismo"] = 0
        if lado == "comprador" and CFG["memoria"].get("juiz_realismo", True):
            a_inserir = [("n", n) for n in d.get("novas", [])] + [("g", g) for g in d.get("generalizacoes", [])]
            reprov = await juiz_realismo(llm, [x for _, x in a_inserir], estilo)
            for i in sorted(reprov, reverse=True):
                if i < len(a_inserir):
                    tipo, x = a_inserir[i]
                    (d["novas"] if tipo == "n" else d["generalizacoes"]).remove(x)
                    relatorio["reprovadas_realismo"] += 1
        ids_ativos = {l["id"] for l in ativas}
        for f in d.get("fusoes", []):
            c = idx.get(f.get("candidata"))
            if c and f.get("licao_id") in ids_ativos:
                r = db.um("SELECT evidencias FROM licoes WHERE id=?", (f["licao_id"],))
                ev = json.loads(r["evidencias"] or "[]") + [c["_call"]]
                db.ex("UPDATE licoes SET evidencias=?, alpha=alpha+0.5 WHERE id=?", (json.dumps(ev), f["licao_id"]))
                relatorio["fundidas"] += 1
        for n in d.get("novas", []):
            evid = [idx[c]["_call"] for c in n.get("de_candidatas", []) if c in idx]
            if not n.get("acao") or mem.validar(n, [], linhagem):
                continue
            alpha = 2.0 if len(set(e.split("-")[0] for e in evid)) >= 2 else 1.0   # evidência em ≥2 jornadas
            mem.inserir_licao(linhagem, nova, n, alpha=alpha, beta=1.0, evidencias=evid)
            relatorio["novas"] += 1
        for g in d.get("generalizacoes", []):
            subs = [s for s in g.get("substitui", []) if s in ids_ativos]
            if len(subs) < 2 or not g.get("acao") or mem.validar(g, [], linhagem):
                continue
            rows = [db.um("SELECT alpha,beta,evidencias FROM licoes WHERE id=?", (s,)) for s in subs]
            alpha = 1 + sum(r["alpha"] - 1 for r in rows)
            beta = 1 + sum(r["beta"] - 1 for r in rows)
            evid = sum((json.loads(r["evidencias"] or "[]") for r in rows), [])
            mem.inserir_licao(linhagem, nova, g, alpha=alpha, beta=beta, evidencias=evid)
            for s in subs:
                db.ex("UPDATE licoes SET versao_aposentada=?, status='generalizada' WHERE id=?", (nova, s))
            relatorio["generalizadas"] += 1
        playbook = d.get("playbook") or playbook

    # aposentadoria por estatística (código, não LLM)
    for l in mem.ativas(linhagem, nova):
        n = l["alpha"] + l["beta"] - 2
        if n >= cfgm["aposentar_n_min"] and l["alpha"] / (l["alpha"] + l["beta"]) < cfgm["aposentar_media_abaixo"]:
            db.ex("UPDATE licoes SET versao_aposentada=?, status='aposentada' WHERE id=?", (nova, l["id"]))
            relatorio["aposentadas"] += 1
    # Fase 0.4: teto de lições de bloqueio (encerrar/recusar/filtrar) por linhagem de comprador
    if linhagem.startswith("comprador"):
        from .estrategica import eh_bloqueio
        bloq = [l for l in mem.ativas(linhagem, nova) if eh_bloqueio(l)]
        teto = cfgm.get("max_licoes_bloqueio", 12)
        if len(bloq) > teto:
            bloq.sort(key=lambda l: l["alpha"] / (l["alpha"] + l["beta"]))
            for l in bloq[:len(bloq) - teto]:
                db.ex("UPDATE licoes SET versao_aposentada=?, status='aposentada_bloqueio' WHERE id=?", (nova, l["id"]))
                relatorio["aposentadas"] += 1
    ativas_novas = mem.ativas(linhagem, nova)
    if len(ativas_novas) > cfgm["max_licoes_ativas"]:
        ativas_novas.sort(key=lambda l: l["alpha"] / (l["alpha"] + l["beta"]))
        for l in ativas_novas[:len(ativas_novas) - cfgm["max_licoes_ativas"]]:
            db.ex("UPDATE licoes SET versao_aposentada=?, status='aposentada' WHERE id=?", (nova, l["id"]))
            relatorio["aposentadas"] += 1

    elo = db.um("SELECT elo FROM versoes WHERE linhagem_id=? AND numero=?", (linhagem, versao_atual))["elo"]
    db.inserir("versoes", linhagem_id=linhagem, numero=nova, playbook=playbook, elo=elo, partidas=0,
               criada_rodada=rodada)
    relatorio["ativas"] = len(mem.ativas(linhagem, nova))
    return relatorio
