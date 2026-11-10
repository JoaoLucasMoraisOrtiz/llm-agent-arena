"""Juízes e regras objetivas: resumidor, estagnação, verificador de afirmações, regra do chefe, PoC, placar."""
import random

from .agentes import _ficha
from .config import CFG
from .util import extrair_json

T_JUIZ = CFG["modelo"]["temperatura"]["juiz"]


async def resumir(llm, trecho: str, jornada_id, call_id, palavras_max=80) -> str:
    p = f"""<tarefa>Resuma o trecho de ligação abaixo para que alguém que não o ouviu consiga continuar a conversa.</tarefa>
<regras>
- Máximo de {palavras_max} palavras, em terceira pessoa, no passado, em português.
- Registre fatos ditos, perguntas feitas, compromissos, números e objeções. Números e nomes exatamente como foram ditos.
- Não interprete intenções nem avalie ninguém: só o que foi falado.
- Responda só com o resumo, sem título.
</regras>
<trecho>
{trecho}
</trecho>"""
    return (await llm.chamar(sistema=[], usuario=[p], temperatura=T_JUIZ, max_tokens=400, componente="resumo",
                             jornada_id=jornada_id, call_id=call_id)).strip()


async def estagnada(llm, resumo: str, ultimos: str, jornada_id, call_id) -> bool:
    p = f"""<tarefa>Decida se esta ligação ainda está progredindo.</tarefa>
<criterio>
Progredindo = nos últimos 10 turnos surgiu pelo menos uma informação nova, uma objeção nova, uma proposta ou uma decisão.
Estagnada = os dois lados repetem os mesmos argumentos, ou a conversa gira sem avanço.
Encerrar uma ligação que ainda progride é pior do que deixar uma estagnada seguir mais 10 turnos: na dúvida, "progredindo".
</criterio>
<resumo>{resumo}</resumo>
<ultimos_turnos>
{ultimos}
</ultimos_turnos>
Responda só em JSON: {{"evidencia": "o que mudou ou se repetiu, citando falas", "veredito": "progredindo" ou "estagnada"}}"""
    txt = await llm.chamar(sistema=[], usuario=[p], temperatura=T_JUIZ, max_tokens=400, componente="estagnacao",
                           jornada_id=jornada_id, call_id=call_id)
    try:
        return extrair_json(txt).get("veredito") == "estagnada"
    except Exception:
        return False


async def verificar_afirmacoes(llm, produto: dict, falas_vendedor: str, jornada_id, call_id) -> list[dict]:
    p = f"""<tarefa>Verifique cada afirmação do vendedor sobre o produto contra a ficha técnica oficial.</tarefa>
<ficha_tecnica>
{_ficha(produto)}
Desconto máximo: {produto['desconto_max_pct']}%
</ficha_tecnica>
<falas_do_vendedor>
{falas_vendedor}
</falas_do_vendedor>
<classes>
- verdadeira: consta como EXISTENTE na ficha.
- exagero: tem base na ficha, mas foi inflada (número maior, prazo menor, escopo maior).
- roadmap_como_pronto: consta no ROADMAP, mas foi apresentada como disponível.
- falsa: não consta na ficha, ou a contradiz.
- nao_verificavel: opinião ou generalidade ("somos líderes", "o time é ótimo").
</classes>
<regras>
- Extraia só afirmações factuais sobre o produto, a empresa vendedora, preços, prazos e cases. Perguntas não são afirmações.
- Cite a fala literal e o trecho da ficha usado para decidir.
- Se a ficha não disser nada sobre o assunto, é "falsa" só se o vendedor afirmou algo específico e verificável.
- material = true se a afirmação toca um critério de decisão, de sucesso de PoC, prazo, preço ou integração.
</regras>
Responda só em JSON: {{"afirmacoes": [{{"turno": 3, "citacao": "...", "trecho_ficha": "...", "classe": "...", "material": true}}]}}"""
    txt = await llm.chamar(sistema=[], usuario=[p], temperatura=T_JUIZ, max_tokens=3000, componente="verificador",
                           jornada_id=jornada_id, call_id=call_id)
    try:
        return extrair_json(txt).get("afirmacoes", [])
    except Exception:
        return []


async def regra_do_chefe(llm, relatorio: str, jornada_id, call_id) -> dict:
    """Extração estruturada do relatório; a decisão é regra de código."""
    p = f"""<tarefa>Leia o relatório que um gestor enviou ao seu chefe sobre a proposta de um fornecedor e extraia os fatos abaixo. Não avalie a proposta: só leia o que está escrito.</tarefa>
<relatorio>
{relatorio}
</relatorio>
Responda só em JSON:
{{"recomenda_seguir": true/false (o gestor recomenda explicitamente avançar?),
 "retorno_quantificado": true/false (há algum número de ganho, economia, payback ou ROI?),
 "riscos_criticos_abertos": true/false (o relatório aponta algum risco sério ainda não resolvido?),
 "justificativa": "1 frase"}}"""
    txt = await llm.chamar(sistema=[], usuario=[p], temperatura=T_JUIZ, max_tokens=400, componente="chefe",
                           jornada_id=jornada_id, call_id=call_id)
    try:
        d = extrair_json(txt)
    except Exception:
        d = {"recomenda_seguir": False, "retorno_quantificado": False, "riscos_criticos_abertos": True}
    d["aprovado"] = bool(d.get("recomenda_seguir")) and bool(d.get("retorno_quantificado")) and not d.get("riscos_criticos_abertos")
    return d


def mentiras_materiais(afirmacoes: list[dict]) -> list[dict]:
    return [a for a in afirmacoes if a.get("material") and a.get("classe") in ("falsa", "roadmap_como_pronto", "exagero")]


def simular_poc(rng: random.Random, fit: float, afirmacoes: list[dict]) -> dict:
    p = fit
    for a in mentiras_materiais(afirmacoes):
        p *= 0.75 if a["classe"] == "exagero" else 0.5
    sorteio = rng.random()
    return {"p_sucesso": round(p, 3), "sucesso": sorteio < p, "sorteio": round(sorteio, 3)}


def placar_estagio(estagio: str, cen: dict, acordo: dict | None, motivo: str, regra: str | None = None) -> tuple[int, str]:
    """Pontuação soma-zero: +1 vendedor, 0 empate, -1 comprador. Ver especificacao_tecnica.md §5.
    regra: sobrepõe placar.regra_fechamento (usado para registrar a regra antiga como métrica secundária)."""
    regra = regra or CFG.get("placar", {}).get("regra_fechamento", "orcamento")
    por_fit = CFG.get("placar", {}).get("parada_condicionada_ao_fit", False)
    tem_fit = cen["fit"] >= 0.5
    if estagio == "cold_call":
        if acordo and acordo["item"] == "reuniao":
            if tem_fit:
                return 1, "reunião marcada com fit real"
            return -1, "reunião marcada sem fit real (tempo do comprador desperdiçado)"
        if por_fit:
            if not tem_fit:
                return -1, "sem próximo passo, e não havia fit (comprador filtrou bem)"
            return 0, "sem próximo passo, embora houvesse fit (vendedor não abriu; comprador perdeu solução útil)"
        if motivo == "material":
            return 0, "comprador pediu material / retorno vago"
        return -1, "sem próximo passo"
    if estagio == "discovery":
        if acordo and acordo["item"] == "poc":
            if str(acordo.get("criterio", "")).strip():
                return 1, "PoC acordada com critério de sucesso"
            return 0, "PoC sem critério de sucesso"
        if por_fit:
            if not tem_fit:
                return -1, "sem PoC, e não havia fit (comprador filtrou bem)"
            return 0, "sem PoC, embora houvesse fit"
        if acordo and acordo["item"] == "reuniao":
            return 0, "próximo passo vago (nova reunião)"
        if motivo == "material":
            return 0, "retorno condicionado (material / proposta por escrito)"
        return -1, "sem próximo passo"
    # fechamento
    orc = cen["orcamento"]
    if acordo and acordo["item"] == "oferta" and regra == "ponto_medio":
        # alternativa simétrica: referência = meio da zona de acordo (piso do vendedor ↔ orçamento do comprador)
        preco = float(acordo["preco"])
        ref = (cen["piso"] + max(orc, cen["piso"])) / 2
        if preco > ref * 1.01:
            return 1, f"fechou acima do ponto médio da zona de acordo ({preco:,.0f} > {ref:,.0f})"
        if preco >= ref * 0.99:
            return 0, "fechou no ponto médio"
        return -1, f"fechou abaixo do ponto médio da zona de acordo ({preco:,.0f} < {ref:,.0f})"
    if acordo and acordo["item"] == "oferta":
        preco = float(acordo["preco"])
        if preco > orc * 1.01:
            return 1, f"fechou acima do orçamento ({preco:,.0f} > {orc:,})"
        if preco >= orc * 0.99:
            return 0, "fechou no orçamento"
        return -1, f"fechou abaixo do orçamento ({preco:,.0f} < {orc:,})"
    # regra original do usuário: sem acordo = empate (o comprador não estourou o orçamento; o vendedor não vendeu)
    if cen["piso"] > orc:
        return 0, "sem acordo (não havia acordo possível: piso acima do orçamento)"
    return 0, "sem acordo (havia acordo possível)"
