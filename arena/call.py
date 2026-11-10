"""Orquestrador de uma call: loop de turnos, relógio, ações, árbitro, guarda de papel, memória de trabalho (M1)."""
import asyncio
import re
import statistics
import uuid

from .config import CFG
from .juizes import estagnada, resumir, verificar_afirmacoes

OBJETIVO = {"cold_call": "reuniao", "discovery": "poc", "fechamento": "oferta"}
RANK = {"reuniao": 1, "poc": 2, "oferta": 3}
PROPOSTAS = {"propor_reuniao": "reuniao", "propor_poc": "poc", "oferta": "oferta"}
RE_MATERIAL = re.compile(r"material|e-?mail|apresenta[cç][aã]o|proposta|por escrito|me manda|retorno", re.I)
RE_VAGA = re.compile(r"\b(n[aã]o sei|n[aã]o saberia|n[aã]o tenho (?:esse|esses|esse tipo de) n[uú]mero|de cabe[cç]a|de tudo um pouco|"
                     r"depende|varia(?: bastante| muito)?|sei l[aá]|mais ou menos|o normal|o de sempre|a gente vai vendo|"
                     r"n[aã]o lembro|dif[ií]cil dizer)\b", re.I)
RE_INVERSAO = {
    "comprador": re.compile(r"\b(nossa solução|nosso produto|nossa plataforma|posso te apresentar|nossos clientes)\b", re.I),
    "vendedor": re.compile(r"\b(nosso orçamento (?:é|está)|vou levar (?:pro|para o) meu (?:chefe|diretor)|estamos avaliando fornecedores)\b", re.I),
}


class ResultadoCall(dict):
    pass


def _fmt(t: dict, nomes: dict) -> str:
    return f"{nomes[t['agente']]}: {t['fala']}"


async def executar_call(llm, db, estagio: str, vendedor, comprador, cen: dict, produto: dict,
                        jornada_id: str) -> ResultadoCall:
    cfg_e, cfg_c = CFG["estagios"][estagio], CFG["call"]
    call_id = f"{jornada_id}-{estagio}"
    nomes = {"vendedor": f"{vendedor.nome} ({produto['empresa_vendedora']['nome']})",
             "comprador": f"{comprador.nome} ({cen['empresa']['nome']})"}
    turnos: list[dict] = []
    blocos_resumo: list[str] = []
    resumidos_ate = 0
    pendentes: dict[str, dict] = {}
    acordo = None
    motivo = None
    avisos = {"vendedor": [], "comprador": []}
    inversoes = {"vendedor": 0, "comprador": 0}
    erros_formato = 0
    retentativas = 0
    turnos_finais = None          # contagem regressiva após acordo ou fim do tempo
    palavras_total = 0

    if estagio == "cold_call":    # o comprador atende o telefone
        turnos.append({"agente": "comprador", "fala": f"Alô, {comprador.nome.split()[0]} falando.", "palavras": 3,
                       "pensamento": "", "estado": "", "tecnica": "", "acoes": [], "formatacao": False})
    vez = "vendedor"

    for n in range(cfg_e["max_turnos"]):
        minutos = palavras_total / cfg_c["palavras_por_minuto"]
        ag = vendedor if vez == "vendedor" else comprador
        resumo = ""
        if blocos_resumo:
            resumo = "<resumo_da_conversa_ate_aqui>\n" + "\n".join(blocos_resumo) + "\n</resumo_da_conversa_ate_aqui>"
        recentes = "\n".join(_fmt(t, nomes) for t in turnos[resumidos_ate:])
        ultima_outro = turnos[-1]["fala"] if turnos and turnos[-1]["agente"] != vez else ""
        t = await ag.turno(resumo, recentes, minutos, cfg_e["minutos"], avisos[vez], call_id, ultima_fala_outro=ultima_outro)
        avisos[vez] = []
        if "erro" in t:
            erros_formato += 1
            if erros_formato >= 3:
                motivo = "erro_formato"
                break
            vez = "comprador" if vez == "vendedor" else "vendedor"
            continue
        retentativas += t["tentativas"] - 1
        turnos.append(t)
        palavras_total += t["palavras"]
        if t["palavras"] > 60 or t["formatacao"]:
            avisos[vez].append(f"Atenção: sua última fala teve {t['palavras']} palavras; numa ligação, fale curto (10 a 40 palavras).")
        if RE_INVERSAO[vez].search(t["fala"]):
            inversoes[vez] += 1

        # --- ações
        for a in t["acoes"]:
            nome = a["acao"]
            if vez == "vendedor" and nome in PROPOSTAS:
                item = PROPOSTAS[nome]
                if item == "oferta":
                    try:
                        preco = float(a.get("preco", 0))
                    except (TypeError, ValueError):
                        preco = 0
                    if preco < cen["piso"]:
                        avisos["vendedor"].append(f"Sua oferta de R$ {preco:,.0f} está abaixo do que a diretoria autoriza e não foi registrada.")
                        continue
                    a["preco"] = preco
                pendentes[item] = {"item": item, **a, "turno": len(turnos) - 1}
            elif vez == "comprador" and nome == "aceitar":
                item = str(a.get("item", "")).lower()
                item = {"reunião": "reuniao"}.get(item, item)
                if item in ("oferta", "proposta", "contrato"):
                    avisos["comprador"].append("Para assinar uma oferta use fechar_contrato(preco=...); pedir proposta por escrito não fecha nada.")
                    continue
                if item in pendentes:
                    novo = {**pendentes[item], "aceito_turno": len(turnos) - 1}
                elif item == "reuniao":
                    novo = {"item": "reuniao", "detalhes": a.get("detalhes", ""), "aceito_turno": len(turnos) - 1}
                else:
                    if item in RANK:
                        avisos["comprador"].append(f"Não há proposta formal de {item} do vendedor para aceitar.")
                    else:
                        motivo = motivo or ("material" if RE_MATERIAL.search(str(a)) else None)
                    continue
                if acordo is None or RANK[novo["item"]] >= RANK[acordo["item"]]:
                    acordo = novo
            elif vez == "comprador" and nome == "fechar_contrato":
                of = pendentes.get("oferta")
                if not of:
                    avisos["comprador"].append("Não há oferta formal do vendedor para fechar.")
                    continue
                acordo = {**of, "aceito_turno": len(turnos) - 1}
            elif vez == "comprador" and nome == "encerrar_call":
                pp = str(a.get("proximo_passo", "")).lower()
                condicional = pp in ("enviar_material", "retornar_depois") or (
                    not pp and RE_MATERIAL.search(str(a.get("motivo", ""))))
                motivo = "material" if condicional else "comprador_encerrou"

        if motivo in ("comprador_encerrou",) or (motivo == "material" and vez == "comprador" and
                                                 any(a["acao"] == "encerrar_call" for a in t["acoes"])):
            break
        if acordo and acordo["item"] == OBJETIVO[estagio] and turnos_finais is None:
            turnos_finais = 2
            motivo = "objetivo_acordado"
        if minutos >= cfg_e["minutos"] and turnos_finais is None:
            turnos_finais = 2
            motivo = motivo or "tempo"
        if turnos_finais is not None:
            turnos_finais -= 1
            if turnos_finais < 0:
                break

        # --- M1: resumo append-only
        if len(turnos) - resumidos_ate >= cfg_c["janela_literal"] + cfg_c["resumo_a_cada"]:
            trecho = "\n".join(_fmt(x, nomes) for x in turnos[resumidos_ate:resumidos_ate + cfg_c["resumo_a_cada"]])
            m0 = sum(x["palavras"] for x in turnos[:resumidos_ate]) / cfg_c["palavras_por_minuto"]
            m1 = sum(x["palavras"] for x in turnos[:resumidos_ate + cfg_c["resumo_a_cada"]]) / cfg_c["palavras_por_minuto"]
            texto = await resumir(llm, trecho, jornada_id, call_id)
            blocos_resumo.append(f"[Minutos {m0:.0f}–{m1:.0f}] {texto}")
            db.inserir("resumos", call_id=call_id, bloco=len(blocos_resumo), texto=texto)
            resumidos_ate += cfg_c["resumo_a_cada"]

        # --- árbitro de estagnação
        if (turnos_finais is None and len(turnos) >= cfg_c["estagnacao_depois_de"]
                and len(turnos) % cfg_c["estagnacao_a_cada"] == 0):
            ult = "\n".join(_fmt(x, nomes) for x in turnos[-10:])
            if await estagnada(llm, "\n".join(blocos_resumo), ult, jornada_id, call_id):
                motivo = "estagnacao"
                break
        if max(inversoes.values()) >= 3:
            motivo = "inversao_de_papel"
            break
        vez = "comprador" if vez == "vendedor" else "vendedor"
    else:
        motivo = motivo or "max_turnos"

    if motivo == "objetivo_acordado" and not acordo:
        motivo = "tempo"
    resumo_txt = "\n".join(blocos_resumo)
    recentes = "\n".join(_fmt(x, nomes) for x in turnos[resumidos_ate:])
    transcricao = "\n".join(f"[{i}] " + _fmt(x, nomes) for i, x in enumerate(turnos))
    falas_v = "\n".join(f"[{i}] {x['fala']}" for i, x in enumerate(turnos) if x["agente"] == "vendedor")
    resumo_bloco = ("<resumo_da_conversa_ate_aqui>\n" + resumo_txt + "\n</resumo_da_conversa_ate_aqui>") if resumo_txt else ""
    influenciador = cen["papel"] == "influenciador"

    decisao = None
    invalida = motivo in ("erro_formato", "inversao_de_papel")
    resumo_fim = ("<resumo_da_conversa_ate_aqui>\n" + "\n".join(blocos_resumo) + "\n</resumo_da_conversa_ate_aqui>") if blocos_resumo else ""
    if (estagio == "discovery" and not invalida and motivo != "comprador_encerrou"
            and not (acordo and acordo["item"] == "poc")):
        rec = "\n".join(_fmt(x, nomes) for x in turnos[resumidos_ate:])
        poc = pendentes.get("poc") or await vendedor.escrever_poc(resumo_fim, rec, call_id)
        if poc:
            decisao = await comprador.decidir_poc(resumo_fim, rec, poc, call_id)
            decisao["tipo"] = "poc_escrita"
            if decisao["aceitou"]:
                acordo = {**poc, "item": "poc", "aceito_turno": "poc_escrita"}
                motivo = "poc_por_escrito"
    if estagio == "fechamento" and not acordo and "oferta" not in pendentes and not invalida and motivo != "comprador_encerrou":
        of = await vendedor.escrever_proposta(resumo_fim, "\n".join(_fmt(x, nomes) for x in turnos[resumidos_ate:]), call_id)
        if of and of["preco"] >= cen["piso"]:
            pendentes["oferta"] = of
    if estagio == "fechamento" and not acordo and "oferta" in pendentes and not invalida:
        rec = "\n".join(_fmt(x, nomes) for x in turnos[resumidos_ate:])
        of = pendentes["oferta"]
        decisao = await comprador.decidir_proposta(resumo_fim, rec, of, call_id)
        if decisao["fechou"]:
            acordo = {**of, "aceito_turno": "proposta_escrita"}
            motivo = "fechou_por_escrito"
        elif decisao.get("contraproposta"):
            contra = decisao["contraproposta"]
            resp = await vendedor.responder_contraproposta(resumo_fim, rec, of, contra, call_id)
            decisao["resposta_vendedor"] = {k: v for k, v in resp.items() if k != "oferta"}
            if resp["aceitou"] and contra["preco"] >= cen["piso"]:
                acordo = {"item": "oferta", "preco": contra["preco"], "condicoes": contra.get("condicoes", ""),
                          "aceito_turno": "contraproposta_aceita"}
                motivo = "fechou_por_escrito"
            else:
                final = resp.get("oferta") or of
                if final["preco"] < cen["piso"]:
                    final = of
                decisao["oferta_final"] = final["preco"]
                d2 = await comprador.decidir_proposta(resumo_fim, rec, final, call_id, final=True)
                decisao["decisao_final"] = {k: d2[k] for k in ("fechou", "motivo_recusa", "pensamento")}
                if d2["fechou"]:
                    acordo = {**final, "aceito_turno": "oferta_final"}
                    motivo = "fechou_por_escrito"
    notas_v, notas_c, afirmacoes, resumo_final = await asyncio.gather(
        vendedor.notas_pos_call(resumo_bloco, recentes, motivo, call_id, False, cen["chefe"]),
        comprador.notas_pos_call(resumo_bloco, recentes, motivo, call_id, influenciador, cen["chefe"]),
        verificar_afirmacoes(llm, produto, falas_v, jornada_id, call_id),
        resumir(llm, transcricao[-12000:], jornada_id, call_id, palavras_max=130),
    )

    # --- métricas de realismo (código, custo zero)
    pv = sum(x["palavras"] for x in turnos if x["agente"] == "vendedor")
    pc = sum(x["palavras"] for x in turnos if x["agente"] == "comprador")
    falas_vend = [x for x in turnos if x["agente"] == "vendedor"]
    # respostas do comprador a perguntas do vendedor: quantas foram vagas (sorteadas pelo código ou espontâneas)
    resp_a_perg = [x for i, x in enumerate(turnos) if x["agente"] == "comprador" and i > 0
                   and turnos[i - 1]["agente"] == "vendedor" and "?" in turnos[i - 1]["fala"]]
    metricas = {
        "turnos": len(turnos), "minutos": round(palavras_total / cfg_c["palavras_por_minuto"], 1),
        "fala_vendedor_pct": round(100 * pv / max(1, pv + pc), 1),
        "perguntas_vendedor": sum(x["fala"].count("?") for x in falas_vend),
        "mediana_palavras_vendedor": statistics.median([x["palavras"] for x in falas_vend]) if falas_vend else 0,
        "mediana_palavras_comprador": statistics.median([x["palavras"] for x in turnos if x["agente"] == "comprador"] or [0]),
        "falas_longas": sum(1 for x in turnos if x["palavras"] > cfg_c["max_palavras_fala"]),
        "erros_formato": erros_formato, "retentativas": retentativas, "inversoes": inversoes,
        "afirmacoes_falsas": sum(1 for a in afirmacoes if a.get("classe") in ("falsa", "roadmap_como_pronto")),
        "exageros": sum(1 for a in afirmacoes if a.get("classe") == "exagero"),
        "respostas_a_perguntas": len(resp_a_perg),
        "respostas_vagas_sorteadas": sum(1 for x in resp_a_perg if x.get("vaga_sorteada")),
        "respostas_vagas_detectadas": sum(1 for x in resp_a_perg if RE_VAGA.search(x["fala"])),
    }
    for i, x in enumerate(turnos):
        db.inserir("turnos", call_id=call_id, n=i, agente=x["agente"], pensamento=x.get("pensamento"),
                   estado=x.get("estado"), tecnica=x.get("tecnica"), fala=x["fala"], acoes=x.get("acoes", []),
                   palavras=x["palavras"], bruto=x.get("bruto"))
    db.inserir("afirmacoes", call_id=call_id, conteudo=afirmacoes)
    return ResultadoCall(call_id=call_id, estagio=estagio, turnos=turnos, acordo=acordo, motivo=motivo,
                         notas_vendedor=notas_v, notas_comprador=notas_c, afirmacoes=afirmacoes,
                         resumo_final=resumo_final, metricas=metricas, transcricao=transcricao,
                         decisao_proposta=decisao)
