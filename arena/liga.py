"""Gerente da liga: linhagens, rodadas alternadas, matchmaking por Elo, hall of fame, consolidação."""
import asyncio
import random

from .cenarios import base_como_empresa, carregar_bases, carregar_produtos, empresas_sinteticas, montar_cenario
from .config import CFG
from .conhecimento import ESTILOS_COMPRADOR, ESTILOS_VENDEDOR
from .jornada import executar_jornada
from .llm import OrcamentoEsgotado
from .memoria.aprendizado import consolidar
from .memoria.estrategica import MemoriaEstrategica


def teto_rodadas() -> float:
    """Parte do teto global reservada para a liga; o restante fica para a avaliação final."""
    return CFG["orcamento"]["teto_global"] * (1 - CFG["orcamento"].get("reserva_avaliacao", 0.07))


def inicializar_linhagens(db):
    for lado, estilos in (("vendedor", ESTILOS_VENDEDOR), ("comprador", ESTILOS_COMPRADOR)):
        for e in estilos:
            lid = f"{lado}/{e}"
            db.ex("INSERT OR IGNORE INTO linhagens(id, lado, estilo) VALUES(?,?,?)", (lid, lado, e))
            db.ex("INSERT OR IGNORE INTO versoes(linhagem_id, numero, playbook, elo, partidas, criada_rodada) "
                  "VALUES(?,0,'',1500,0,0)", (lid,))


def versao_atual(db, linhagem: str) -> int:
    return db.um("SELECT MAX(numero) m FROM versoes WHERE linhagem_id=?", (linhagem,))["m"]


def atualizar_elo(db, vend: tuple[str, int], comp: tuple[str, int], placar: int):
    k = CFG["liga"]["elo_k"]
    rv = db.um("SELECT elo FROM versoes WHERE linhagem_id=? AND numero=?", vend)["elo"]
    rc = db.um("SELECT elo FROM versoes WHERE linhagem_id=? AND numero=?", comp)["elo"]
    esperado_v = 1 / (1 + 10 ** ((rc - rv) / 400))
    s = 1.0 if placar > 0 else (0.5 if placar == 0 else 0.0)
    db.ex("UPDATE versoes SET elo=elo+?, partidas=partidas+1 WHERE linhagem_id=? AND numero=?", (k * (s - esperado_v), *vend))
    db.ex("UPDATE versoes SET elo=elo-?, partidas=partidas+1 WHERE linhagem_id=? AND numero=?", (k * (s - esperado_v), *comp))


def escolher_oponente(db, rng, lado: str, rating_ref: float, congelado: bool) -> tuple[str, int]:
    """Oponente com Elo próximo (softmax sobre -|Δ|); com prob. hall_of_fame, uma versão antiga."""
    estilos = ESTILOS_VENDEDOR if lado == "vendedor" else ESTILOS_COMPRADOR
    cands = []
    for e in estilos:
        lid = f"{lado}/{e}"
        v = versao_atual(db, lid)
        if congelado and v > 0 and rng.random() < CFG["liga"]["hall_of_fame_prob"]:
            v = rng.randint(0, v - 1)
        elo = db.um("SELECT elo FROM versoes WHERE linhagem_id=? AND numero=?", (lid, v))["elo"]
        cands.append(((lid, v), elo))
    pesos = [2.718 ** (-abs(elo - rating_ref) / 100) for _, elo in cands]
    return rng.choices([c for c, _ in cands], weights=pesos)[0]


def sortear_cenario(db, rng, bases, produtos, estilo_v, estilo_c, sinteticas=True):
    base = bases[rng.choice(list(bases))]
    pool = [base_como_empresa(base)] + (empresas_sinteticas(db, base["id"]) if sinteticas else [])
    empresa = rng.choice(pool)
    # ponderado pelo fit: mistura realista (a maioria das prospecções é plausível, algumas não)
    ids = list(produtos)
    pesos = [produtos[i]["fit_base"].get(base["id"], 0.3) ** 2 + 0.05 for i in ids]
    produto = produtos[rng.choices(ids, weights=pesos)[0]]
    return montar_cenario(rng, empresa, produto, estilo_v, estilo_c), produto


async def rodada(llm, db, rodada_n: int, lado_aprendiz: str, n_jornadas: int, rng: random.Random,
                 concorrencia: int = 4, consolidar_fim: bool = True, log=print, inicio_fixo: str | None = None) -> dict:
    inicializar_linhagens(db)
    mem = MemoriaEstrategica(db, rng)
    bases, produtos = carregar_bases(), carregar_produtos()
    vendedores = [f"vendedor/{e}" for e in ESTILOS_VENDEDOR]
    agenda = []
    for i in range(n_jornadas):
        lv = vendedores[i % len(vendedores)]
        vv = versao_atual(db, lv)
        elo_v = db.um("SELECT elo FROM versoes WHERE linhagem_id=? AND numero=?", (lv, vv))["elo"]
        comp = escolher_oponente(db, rng, "comprador", elo_v, congelado=(lado_aprendiz == "vendedor"))
        vend = (lv, vv)
        if lado_aprendiz == "comprador" and vv > 0 and rng.random() < CFG["liga"]["hall_of_fame_prob"]:
            vend = (lv, rng.randint(0, vv - 1))
        cen, prod = sortear_cenario(db, rng, bases, produtos, lv.split("/")[1], comp[0].split("/")[1])
        inicio = inicio_fixo or rng.choices(["cold_call", "discovery", "fechamento"], weights=[2, 1, 1])[0]
        agenda.append((cen, prod, vend, comp, inicio))

    sem = asyncio.Semaphore(concorrencia)
    resultados = []

    async def uma(cen, prod, vend, comp, inicio):
        async with sem:
            if llm.gasto_global >= teto_rodadas():
                return
            try:
                r = await executar_jornada(llm, db, mem, cen, prod, vend, comp, rodada_n, {lado_aprendiz},
                                           random.Random(rng.random()), estagio_inicial=inicio)
            except Exception as e:  # noqa: BLE001 — uma jornada com erro não pode derrubar a liga
                log(f"  ERRO jornada ({type(e).__name__}): {str(e)[:200]}")
                return
            if r["status"] == "concluida":
                atualizar_elo(db, vend, comp, r["placar"])
            estagios = "→".join(f"{c['estagio']}:{c['resultado']:+d}" for c in r["detalhe"]["calls"])
            log(f"  jornada {r['id']} {vend[0]}@{vend[1]} vs {comp[0]}@{comp[1]} | {cen['empresa']['nome'][:28]} × "
                f"{prod['nome']} (fit {cen['fit']}) | {estagios} | placar {r['placar']:+d} | {r['status']} | "
                f"{r['detalhe'].get('tokens_contados', 0):,} tok")
            resultados.append(r)

    try:
        await asyncio.gather(*(uma(*a) for a in agenda))
    except OrcamentoEsgotado as e:
        log(f"  orçamento: {e}")
    consolidacoes = []
    if consolidar_fim:
        lados = vendedores if lado_aprendiz == "vendedor" else [f"comprador/{e}" for e in ESTILOS_COMPRADOR]
        for lid in lados:
            rel = await consolidar(llm, db, mem, lid, versao_atual(db, lid), rodada_n)
            consolidacoes.append(rel)
            log(f"  consolidação {lid}: v{rel['de']}→v{rel['para']} candidatas={rel['candidatas']} "
                f"novas={rel['novas']} fundidas={rel['fundidas']} generalizadas={rel['generalizadas']} "
                f"aposentadas={rel['aposentadas']} ativas={rel['ativas']}")
    validas = [r for r in resultados if r["status"] == "concluida"]
    media = sum(r["placar"] for r in validas) / max(1, len(validas))
    return {"rodada": rodada_n, "lado_aprendiz": lado_aprendiz, "jornadas": len(resultados),
            "validas": len(validas), "placar_medio": media, "consolidacoes": consolidacoes}


MODOS = {
    "v0": None,                                            # versão inicial, sem memória
    "completo": {"playbook": True, "licoes": True},
    "so_playbook": {"playbook": True, "licoes": False},
    "so_licoes": {"playbook": False, "licoes": True},
}


async def avaliar(llm, db, lado: str, versao: int | None, n: int, modos: list[str], rng: random.Random,
                  concorrencia: int = 8, log=print) -> dict:
    """Avaliação pareada: os MESMOS cenários, contra o painel fixo de oponentes v0, para cada modo de memória.
    Mede melhora atribuível à memória (e não ao oponente) e faz ablação playbook × lições."""
    import copy
    inicializar_linhagens(db)
    mem = MemoriaEstrategica(db, rng)
    bases, produtos = carregar_bases(), carregar_produtos()
    estilos_lado = ESTILOS_VENDEDOR if lado == "vendedor" else ESTILOS_COMPRADOR
    estilos_op = ESTILOS_COMPRADOR if lado == "vendedor" else ESTILOS_VENDEDOR
    agenda = []
    for i in range(n):
        e_lado = list(estilos_lado)[i % len(estilos_lado)]
        e_op = rng.choice(list(estilos_op))
        ev, ec = (e_lado, e_op) if lado == "vendedor" else (e_op, e_lado)
        cen, prod = sortear_cenario(db, rng, bases, produtos, ev, ec)
        inicio = rng.choices(["cold_call", "discovery", "fechamento"], weights=[2, 1, 1])[0]
        agenda.append((cen, prod, e_lado, e_op, rng.random(), inicio))
    sem = asyncio.Semaphore(concorrencia)
    res: dict[str, list] = {m: [None] * n for m in modos}

    async def uma(i, modo):
        cen, prod, e_lado, e_op, semente, inicio = agenda[i]
        lid = f"{lado}/{e_lado}"
        v = 0 if modo == "v0" else (versao if versao is not None else versao_atual(db, lid))
        oponente = (f"{'comprador' if lado == 'vendedor' else 'vendedor'}/{e_op}", 0)
        vend, comp = ((lid, v), oponente) if lado == "vendedor" else (oponente, (lid, v))
        abl = {lado: MODOS[modo]} if MODOS[modo] else None
        async with sem:
            try:
                r = await executar_jornada(llm, db, mem, copy.deepcopy(cen), prod, vend, comp, 900, set(),
                                           random.Random(semente), ablacao=abl, estagio_inicial=inicio)
            except Exception as e:  # noqa: BLE001
                log(f"  ERRO avaliação ({type(e).__name__}): {str(e)[:200]}")
                return
        res[modo][i] = r
        etapas = "→".join(f"{c['estagio']}:{c['resultado']:+d}" for c in r["detalhe"]["calls"])
        log(f"  [{modo}] #{i} {lid}@{v} vs {oponente[0]} | {cen['empresa']['nome'][:24]} × {prod['nome']} "
            f"(fit {cen['fit']}) | {etapas} | placar {r['placar']:+d} | {r['status']}")

    await asyncio.gather(*(uma(i, m) for i in range(n) for m in modos))
    sinal = 1 if lado == "vendedor" else -1        # placar positivo = bom para o lado avaliado
    tabela = {}
    for m in modos:
        validos = [r for r in res[m] if r and r["status"] == "concluida"]
        pts = [sinal * r["placar"] for r in validos]
        avancos = [len(r["detalhe"]["calls"]) for r in validos]
        tabela[m] = {"n": len(pts), "media": sum(pts) / max(1, len(pts)),
                     "vitorias": sum(p > 0 for p in pts), "empates": sum(p == 0 for p in pts),
                     "derrotas": sum(p < 0 for p in pts), "calls_por_jornada": sum(avancos) / max(1, len(avancos))}
    if "v0" in modos:
        for m in modos:
            if m == "v0":
                continue
            difs = [sinal * (res[m][i]["placar"] - res["v0"][i]["placar"]) for i in range(n)
                    if res[m][i] and res["v0"][i] and res[m][i]["status"] == res["v0"][i]["status"] == "concluida"]
            tabela[m]["delta_pareado_vs_v0"] = sum(difs) / max(1, len(difs))
            tabela[m]["melhor/igual/pior_que_v0"] = (sum(d > 0 for d in difs), sum(d == 0 for d in difs), sum(d < 0 for d in difs))
    return tabela


async def continuo(llm, db, rng, jornadas_por_rodada: int, concorrencia: int, avaliar_a_cada: int,
                   n_avaliacao: int, pasta, log=print):
    """Liga completa até o teto: rodadas alternadas + avaliação pareada periódica + avaliação final com ablação."""
    import json
    from .cenarios import gerar_sintetica
    from .relatorio import resumo
    from .deriva import com_alarme
    pasta.mkdir(parents=True, exist_ok=True)
    evol = pasta / "evolucao.jsonl"

    def registrar_evento(ev):                      # Fase 0.6: início e fim das janelas de cota no evolucao.jsonl
        log(f"  [cota] {ev}")
        with open(evol, "a") as f:
            f.write(json.dumps(ev, ensure_ascii=False) + "\n")
    llm.ao_evento = registrar_evento
    ultima = db.um("SELECT MAX(rodada) m FROM jornadas WHERE rodada < 900")["m"] or 0
    consolidada = db.um("SELECT COUNT(*) n FROM versoes WHERE criada_rodada=? AND numero>0", (ultima,))["n"]
    r = ultima if (ultima and not consolidada) else ultima + 1   # retoma rodada interrompida antes do "sono"
    bases = carregar_bases()
    while llm.gasto_global < teto_rodadas():
        if (r - 1) % 4 == 0:        # renova a diversidade de empresas a cada 4 rodadas
            try:
                novas = await asyncio.gather(*(gerar_sintetica(llm, db, b, random.Random(rng.random()))
                                               for b in bases.values()))
                log(f"  +{len(novas)} empresas sintéticas: " + ", ".join(e["nome"] for e in novas))
            except Exception as e:  # noqa: BLE001
                log(f"  ERRO gerando sintéticas: {e}")
        lado = "vendedor" if r % 2 == 1 else "comprador"
        log(f"== rodada {r} (aprende: {lado}) | tokens {llm.gasto_global:,} / {int(teto_rodadas()):,} ==")
        res = await rodada(llm, db, r, lado, jornadas_por_rodada, rng, concorrencia=concorrencia, log=log)
        log(f"   rodada {r}: placar médio {res['placar_medio']:+.2f} em {res['validas']} jornadas válidas")
        with open(evol, "a") as f:
            f.write(json.dumps({"tipo": "rodada", "rodada": r, "lado": lado, "placar_medio": res["placar_medio"],
                                "validas": res["validas"], "tokens": llm.gasto_global}, ensure_ascii=False) + "\n")
        pd = com_alarme(db, r)                     # Fase 0.7: painel de deriva de realismo
        with open(evol, "a") as f:
            f.write(json.dumps({"tipo": "deriva", **{k: v for k, v in pd.items() if k != "faixas"}}, ensure_ascii=False) + "\n")
        if pd["alarmes"]:
            log(f"   ALARME de deriva (2 rodadas fora da faixa): {', '.join(pd['alarmes'])}")
        if r % avaliar_a_cada == 0 and llm.gasto_global < teto_rodadas():
            for lado_av in ("vendedor", "comprador"):
                tab = await avaliar(llm, db, lado_av, None, n_avaliacao, ["v0", "completo"],
                                    random.Random(1000 + r), concorrencia=concorrencia, log=log)
                log(f"   avaliação {lado_av} após rodada {r}: {json.dumps(tab, ensure_ascii=False)}")
                with open(evol, "a") as f:
                    f.write(json.dumps({"tipo": "avaliacao", "rodada": r, "lado": lado_av, "tabela": tab,
                                        "tokens": llm.gasto_global}, ensure_ascii=False) + "\n")
        (pasta / "relatorio.md").write_text(resumo(db), encoding="utf-8")
        r += 1
    log(f"== teto da liga atingido ({llm.gasto_global:,}); avaliação final com ablação ==")
    final = {}
    for lado_av in ("vendedor", "comprador"):
        try:
            final[lado_av] = await avaliar(llm, db, lado_av, None, 2 * n_avaliacao, list(MODOS),
                                           random.Random(4242), concorrencia=concorrencia, log=log)
        except Exception as e:  # noqa: BLE001
            final[lado_av] = {"erro": str(e)}
        log(f"   final {lado_av}: {json.dumps(final[lado_av], ensure_ascii=False)}")
    (pasta / "avaliacao_final.json").write_text(json.dumps(final, ensure_ascii=False, indent=1))
    (pasta / "relatorio.md").write_text(resumo(db), encoding="utf-8")
    log(f"== fim. tokens contados: {llm.gasto_global:,} ==")
