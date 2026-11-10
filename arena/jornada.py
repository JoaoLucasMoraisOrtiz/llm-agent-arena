"""Executor de jornada: máquina de estados cold call → discovery → [PoC] → fechamento, com M2 e placar."""
import asyncio
import json
import random
import uuid

from .agentes import Agente, bloco_a, bloco_b
from .call import OBJETIVO, executar_call
from .config import CFG
from .juizes import mentiras_materiais, placar_estagio, regra_do_chefe, simular_poc
from .llm import OrcamentoEsgotado
from .memoria.aprendizado import criticar
from .congelamento import hash_regras
from .util import reais

ESTAGIOS = ["cold_call", "discovery", "fechamento"]


async def executar_jornada(llm, db, mem, cen: dict, produto: dict, vend: tuple[str, int], comp: tuple[str, int],
                           rodada: int, lados_aprendizes: set[str], rng: random.Random,
                           ablacao: dict | None = None, estagio_inicial: str = "cold_call") -> dict:
    """vend/comp = (linhagem_id, versão congelada).
    ablacao: {"vendedor"|"comprador": {"playbook": bool, "licoes": bool}} desliga partes da memória (avaliação)."""
    ab = {"vendedor": {"playbook": True, "licoes": True}, "comprador": {"playbook": True, "licoes": True}}
    for lado, d in (ablacao or {}).items():
        ab[lado].update(d)
    jid = uuid.uuid4().hex[:12]
    T = CFG["modelo"]["temperatura"]
    hist = historico_sintetico(cen, produto, estagio_inicial)
    detalhe = {"calls": [], "poc": None, "pos_venda": None, "chefe": [], "estagio_inicial": estagio_inicial,
               "versao_regras": hash_regras()}
    total = 0
    status = "concluida"
    mentiras_jornada = []
    db.inserir("jornadas", id=jid, rodada=rodada, cenario=cen, vendedor=f"{vend[0]}@{vend[1]}",
               comprador=f"{comp[0]}@{comp[1]}", status="em_andamento", placar=0, detalhe=detalhe)
    try:
        for estagio in ESTAGIOS[ESTAGIOS.index(estagio_inicial):]:
            perfil = {**cen["perfil"], "estagio": estagio}
            lic_v = mem.recuperar(vend[0], vend[1], {**perfil, "estilo_oponente": None}) if ab["vendedor"]["licoes"] else []
            lic_c = (mem.recuperar(comp[0], comp[1], {**perfil, "estilo_oponente": cen["vendedor"]["estilo"]})
                     if ab["comprador"]["licoes"] else [])
            pb_v = mem.playbook(*vend) if ab["vendedor"]["playbook"] else ""
            pb_c = mem.playbook(*comp) if ab["comprador"]["playbook"] else ""
            vendedor = Agente(llm, "vendedor", cen["vendedor"]["nome"], "vendedor",
                              bloco_a("vendedor", cen, produto, pb_v),
                              bloco_b("vendedor", estagio, cen, produto, hist["vendedor"], lic_v, rng),
                              T["vendedor"], jid)
            comprador = Agente(llm, "comprador", cen["comprador"]["nome"], "comprador",
                               bloco_a("comprador", cen, produto, pb_c),
                               bloco_b("comprador", estagio, cen, produto, hist["comprador"], lic_c, rng),
                               T["comprador"], jid, evasividade=cen["comprador"].get("evasividade", 0.0),
                               rng=random.Random(rng.random()))
            res = await executar_call(llm, db, estagio, vendedor, comprador, cen, produto, jid)
            pontos, explic = placar_estagio(estagio, cen, res["acordo"], res["motivo"])
            # Fase 0.2: a regra antiga (preço vs. orçamento) continua registrada como métrica secundária
            pontos_orc, _ = placar_estagio(estagio, cen, res["acordo"], res["motivo"], regra="orcamento")
            if res["motivo"] in ("erro_formato", "inversao_de_papel"):
                status = f"invalida_{res['motivo']}"

            # regra oculta do chefe (influenciador) para PoC e contrato
            chefe = None
            if (cen["papel"] == "influenciador" and res["acordo"] and res["acordo"]["item"] == OBJETIVO[estagio]
                    and estagio in ("discovery", "fechamento")):
                rel = _campo_yaml(res["notas_comprador"], "relatorio_para_chefe") or res["notas_comprador"]
                chefe = await regra_do_chefe(llm, rel, jid, res["call_id"])
                detalhe["chefe"].append({"estagio": estagio, **chefe})
                if not chefe["aprovado"]:
                    pontos, explic = -1, f"{explic}, mas o {cen['chefe']} reprovou ({chefe.get('justificativa', '')})"

            mentiras = mentiras_materiais(res["afirmacoes"])
            mentiras_jornada += mentiras
            total += pontos
            call_reg = {"call_id": res["call_id"], "estagio": estagio, "resultado": pontos, "explicacao": explic,
                        "motivo_fim": res["motivo"], "acordo": res["acordo"], "metricas": res["metricas"],
                        "resultado_regra_orcamento": pontos_orc,
                        "licoes_vendedor": [l["id"] for l in lic_v], "licoes_comprador": [l["id"] for l in lic_c],
                        "proposta_escrita": res.get("decisao_proposta")}
            detalhe["calls"].append(call_reg)
            db.inserir("calls", id=res["call_id"], jornada_id=jid, estagio=estagio, resultado=pontos,
                       motivo_fim=res["motivo"], minutos=res["metricas"]["minutos"], detalhe=call_reg,
                       metricas=res["metricas"])
            db.inserir("memoria_jornada", jornada_id=jid, agente="vendedor", apos_call=res["call_id"],
                       conteudo=res["notas_vendedor"])
            db.inserir("memoria_jornada", jornada_id=jid, agente="comprador", apos_call=res["call_id"],
                       conteudo=res["notas_comprador"])

            # crítico(s) do(s) lado(s) aprendiz(es)
            if status == "concluida":
                await _criticar(llm, db, mem, cen, res, estagio, pontos, explic, vend, comp, lic_v, lic_c,
                                rodada, lados_aprendizes, jid, produto)

            # M2: a memória de jornada que cada lado leva para a próxima call
            resumo = f"Resumo da última conversa ({estagio}): {res['resumo_final']}"
            hist["vendedor"] = f"Suas anotações de CRM:\n{res['notas_vendedor']}\n\n{resumo}"
            hist["comprador"] = f"Suas anotações internas:\n{res['notas_comprador']}\n\n{resumo}"

            avancou = res["acordo"] is not None and res["acordo"]["item"] == OBJETIVO[estagio] and status == "concluida"
            if chefe is not None and not chefe["aprovado"]:
                avancou = False
            if not avancou or estagio == "fechamento":
                break
            if estagio == "discovery":
                poc = simular_poc(rng, cen["fit"], mentiras_jornada)
                poc["criterio"] = res["acordo"].get("criterio", "")
                detalhe["poc"] = poc
                if not poc["sucesso"]:
                    # PoC é portão, não disputa: o fracasso por promessa falsa pune o vendedor;
                    # sem mentira, é desperdício compartilhado (métrica fora do placar soma-zero)
                    if mentiras_jornada:
                        total -= 1
                        poc["penalidade"] = "vendedor: promessas falsas materiais"
                    else:
                        poc["desperdicio"] = True
                    break
                txt_poc = (f"\n\nRESULTADO DA PoC: sucesso. O critério combinado ({poc['criterio']}) foi atingido "
                           f"e o time técnico aprovou a solução.")
                hist["vendedor"] += txt_poc
                hist["comprador"] += txt_poc

        graves = [m for m in mentiras_jornada if m.get("classe") in ("falsa", "roadmap_como_pronto")]
        ultimo = detalhe["calls"][-1] if detalhe["calls"] else None
        if (ultimo and ultimo["estagio"] == "fechamento" and ultimo["acordo"]
                and ultimo["acordo"].get("item") == "oferta" and graves):
            total -= 1
            detalhe["pos_venda"] = "penalidade: promessas falsas descobertas após a venda"
    except OrcamentoEsgotado as e:
        status = "abortada_orcamento"
        detalhe["erro"] = str(e)
    detalhe["tokens_contados"] = llm.gasto_jornada.get(jid, 0)
    db.ex("UPDATE jornadas SET status=?, placar=?, detalhe=? WHERE id=?",
          (status, total, json.dumps(detalhe, ensure_ascii=False, default=str), jid))
    return {"id": jid, "status": status, "placar": total, "detalhe": detalhe}


def historico_sintetico(cen: dict, produto: dict, estagio_inicial: str) -> dict:
    """Contexto anterior para jornadas que começam no meio do funil (sem gastar tokens simulando o início)."""
    if estagio_inicial == "cold_call":
        return {"vendedor": "", "comprador": ""}
    v, c = cen["vendedor"]["nome"], cen["comprador"]["nome"]
    base = (f"Numa ligação anterior, {v} apresentou rapidamente a {produto['empresa_vendedora']['nome']} "
            f"({produto['descricao_curta']}) e {c} aceitou uma reunião de discovery. Pouco foi aprofundado.")
    if estagio_inicial == "discovery":
        return {"vendedor": f"Suas anotações de CRM:\ninterlocutor: {c}, {cen['cargo']}\n{base}",
                "comprador": f"Suas anotações internas:\n{base} Você aceitou para ouvir mais, sem compromisso."}
    poc = (f"{base} Na discovery, as partes combinaram uma PoC com critério de sucesso em torno de "
           f"'{produto['metrica_poc']}'.\n\nRESULTADO DA PoC: sucesso. O critério combinado foi atingido e o time "
           f"técnico aprovou a solução. Falta a negociação comercial.")
    return {"vendedor": f"Suas anotações de CRM:\ninterlocutor: {c}, {cen['cargo']}\n{poc}",
            "comprador": f"Suas anotações internas:\n{poc}"}


def _campo_yaml(txt: str, campo: str) -> str | None:
    import yaml
    try:
        d = yaml.safe_load(txt)
        if isinstance(d, dict) and d.get(campo):
            return str(d[campo])
    except Exception:
        pass
    return None


async def _criticar(llm, db, mem, cen, res, estagio, pontos, explic, vend, comp, lic_v, lic_c, rodada,
                    lados_aprendizes, jid, produto):
    nomes = {"vendedor": cen["vendedor"]["nome"] + " (vendedor)", "comprador": cen["comprador"]["nome"] + " (cliente)"}
    falsas = mentiras_materiais(res["afirmacoes"])
    tarefas = []
    for lado in sorted(lados_aprendizes):
        linhagem, lic = (vend[0], lic_v) if lado == "vendedor" else (comp[0], lic_c)
        ocultas = None
        if CFG["memoria"]["critico_onisciente"]:
            ocultas = (f"orçamento real {reais(cen['orcamento'])}, fit real {cen['fit']}, papel {cen['papel']}"
                       if lado == "vendedor" else f"piso do vendedor {reais(cen['piso'])}")
        tarefas.append((lado, linhagem, lic, criticar(
            llm, lado=lado, nome=cen[lado]["nome"], estilo=cen[lado]["estilo"], estagio=estagio, resultado=pontos,
            explicacao=explic, turnos=res["turnos"], nomes=nomes, licoes=lic, ocultas=ocultas,
            afirmacoes_falsas=falsas, jornada_id=jid, call_id=res["call_id"])))
    saidas = await asyncio.gather(*(t[3] for t in tarefas))
    proibidos = [cen["empresa"]["nome"], cen["vendedor"]["nome"], cen["comprador"]["nome"], produto["nome"],
                 produto["empresa_vendedora"]["nome"]]
    for (lado, linhagem, lic, _), out in zip(tarefas, saidas):
        db.inserir("criticas", call_id=res["call_id"], linhagem_id=linhagem, conteudo=out)
        mem.creditar(res["call_id"], linhagem, out.get("creditos", []), {l["id"] for l in lic})
        for nova in out.get("licoes_novas", [])[:3]:
            if nova.get("para") and nova["para"] != lado:
                continue      # lição escrita para o outro lado da mesa
            motivo = mem.validar(nova, proibidos, linhagem)
            if motivo is None:
                mem.encenar(rodada, linhagem, nova, res["call_id"])
