"""Geração de cenários: empresa (base ou sintética) × cargo × produto × verdades ocultas.

Princípio P6: números e verdades ocultas vêm do código; o LLM só escreve narrativa.
"""
import json
import random
import uuid

import yaml

from .config import DADOS
from .conhecimento import MOMENTOS_COMPRADOR
from .util import extrair_json

NOMES = ["Roberto", "Marina", "Carla", "Eduardo", "Fernanda", "Ricardo", "Patrícia", "André", "Luciana",
         "Marcelo", "Juliana", "Sérgio", "Renata", "Gustavo", "Camila", "Fábio", "Aline", "Rodrigo"]
SOBRENOMES = ["Almeida", "Souza", "Ferreira", "Lima", "Carvalho", "Ribeiro", "Martins", "Barbosa",
              "Rocha", "Teixeira", "Mendes", "Castro", "Nogueira", "Pires"]
NIVEL_TECNICO = {"CTO": (2, 3), "COO": (1, 2), "CFO": (0, 1), "Diretor de Compras": (1, 1), "Diretor Comercial": (0, 1)}
TIMINGS = [
    "O contrato com a solução atual vence em cerca de 4 meses e há insatisfação interna.",
    "Não há nenhum prazo forçando uma decisão este ano.",
    "A diretoria cobrou um plano para essa área até o fim do trimestre.",
    "O orçamento do ano que vem está sendo fechado agora; o que não entrar agora só entra daqui a um ano.",
]


def carregar_bases() -> dict:
    return {p.stem: yaml.safe_load(open(p, encoding="utf-8")) for p in sorted((DADOS / "empresas").glob("*.yaml"))}


def carregar_produtos() -> dict:
    return {p.stem: yaml.safe_load(open(p, encoding="utf-8")) for p in sorted((DADOS / "produtos").glob("*.yaml"))}


def nome_pessoa(rng) -> str:
    return f"{rng.choice(NOMES)} {rng.choice(SOBRENOMES)}"


PROMPT_SINTETICA = """<tarefa>Crie o dossiê de uma empresa brasileira FICTÍCIA com os atributos abaixo, inspirada no perfil da empresa de referência, mas claramente distinta dela.</tarefa>

<referencia>
Setor: {setor}
{publico}
Dores internas da referência (para inspiração): {dores}
</referencia>

<atributos_obrigatorios>
porte: {porte}
maturidade_digital: {maturidade}
saude_financeira: {saude}
cultura: {cultura}
</atributos_obrigatorios>

<regras>
- Nome fictício, que não exista no mercado brasileiro conhecido. Não cite a empresa de referência nem nomes de pessoas.
- Todos os números devem ser coerentes com os atributos (receita compatível com o porte etc.) e marcados como aproximados.
- O texto público (250-400 palavras) é o que estaria no site de RI ou na imprensa.
- As dores internas (8 a 10) são fatos internos plausíveis e específicos, cada uma com um tema de: seguranca, atendimento, frota, agro_campo, manufatura, contas_pagar, custo_nuvem, treinamento. Inclua pelo menos 5 temas diferentes, sempre incluindo seguranca, contas_pagar e treinamento.
- Não defina orçamento, preços nem fornecedores com nome de empresa real.
</regras>

Responda SOMENTE com um objeto JSON válido (sem comentários), com as chaves:
{{"nome": "...", "publico": "texto corrido", "cargos": {{"CTO": "...", "CFO": "...", "COO": "...", "Diretor de Compras": "...", "Diretor Comercial": "..."}}, "dores_internas": [{{"tema": "...", "texto": "..."}}], "fornecedores_plausiveis": ["..."]}}"""


async def gerar_sintetica(llm, db, base: dict, rng: random.Random) -> dict:
    atributos = {
        "porte": rng.choice(["media", "grande", "grande"]),
        "maturidade": rng.choice(["baixa", "media", "alta"]),
        "saude": rng.choice(["pressionada", "estavel", "forte"]),
        "cultura": rng.choice(["conservadora", "inovadora", "orientada a custo", "orientada a crescimento"]),
    }
    dores = "; ".join(d["texto"] for d in base.get("dores_internas", [])[:6])
    prompt = PROMPT_SINTETICA.format(setor=base["setor"], publico=base["publico"], dores=dores,
                                     porte=atributos["porte"], maturidade=atributos["maturidade"],
                                     saude=atributos["saude"], cultura=atributos["cultura"])
    for tentativa in range(3):
        txt = await llm.chamar(sistema=[], usuario=[prompt], temperatura=0.9, max_tokens=4000,
                               componente="gerador_empresa")
        try:
            dados = extrair_json(txt)
            if all(k in dados for k in ("nome", "publico", "cargos", "dores_internas")):
                break
        except ValueError:
            pass
    else:
        raise RuntimeError("gerador de empresa não produziu JSON válido")
    emp = {
        "id": f"sint-{base['id']}-{uuid.uuid4().hex[:6]}", "base_id": base["id"], "sintetica": True,
        "nome": dados["nome"], "setor": base["setor"], "porte": atributos["porte"],
        "maturidade_digital": atributos["maturidade"], "saude_financeira": atributos["saude"],
        "cultura": atributos["cultura"], "publico": dados["publico"], "cargos": dados["cargos"],
        "dores_internas": dados["dores_internas"], "fornecedores_plausiveis": dados.get("fornecedores_plausiveis", []),
    }
    db.inserir("empresas_sinteticas", id=emp["id"], base_id=base["id"], atributos=atributos, dossie=emp)
    return emp


def empresas_sinteticas(db, base_id: str | None = None) -> list[dict]:
    sql = "SELECT dossie FROM empresas_sinteticas" + (" WHERE base_id=?" if base_id else "")
    return [json.loads(r["dossie"]) for r in db.todos(sql, (base_id,) if base_id else ())]


def base_como_empresa(base: dict) -> dict:
    return {**base, "base_id": base["id"], "sintetica": False}


def montar_cenario(rng: random.Random, empresa: dict, produto: dict, estilo_vendedor: str,
                   estilo_comprador: str, cargo: str | None = None, papel: str | None = None,
                   fit: float | None = None) -> dict:
    cargos_possiveis = [c for c in produto["cargos_alvo"] if c in empresa["cargos"]] or list(empresa["cargos"])
    cargo = cargo or rng.choice(cargos_possiveis)
    papel = papel or rng.choice(["decisor", "influenciador"])
    preco = produto["preco_tabela_anual"]
    if fit is None:
        fit = produto["fit_base"].get(empresa["base_id"], 0.4) + rng.gauss(0, 0.12)
        if not any(d["tema"] == produto["tema"] for d in empresa["dores_internas"]):
            fit -= 0.2
    fit = round(min(0.95, max(0.05, fit)), 2)
    orcamento = int(round(preco * rng.uniform(0.85, 1.15), -3))
    piso = int(round(preco * (1 - produto["desconto_max_pct"] / 100), -3))
    lo, hi = NIVEL_TECNICO.get(cargo, (0, 2))
    nivel_tecnico = rng.randint(lo, hi)
    chefe = "CEO" if cargo == "CFO" else "CFO"

    # camada interna com níveis de revelação (P7)
    dores_tema = [d["texto"] for d in empresa["dores_internas"] if d["tema"] == produto["tema"]]
    outras = [d["texto"] for d in empresa["dores_internas"] if d["tema"] != produto["tema"]]
    fatos = []
    if empresa.get("fornecedores_plausiveis"):
        fatos.append(("FÁCIL", "Sistemas e fornecedores que vocês já usam: " + "; ".join(empresa["fornecedores_plausiveis"]) + "."))
    if dores_tema and fit >= 0.35:
        fatos.append(("MÉDIO", dores_tema[0]))
        if fit >= 0.65:
            fatos.append(("MÉDIO", "Esse problema já foi discutido na diretoria e existe pressão real por uma solução."))
    else:
        fatos.append(("FÁCIL", "Honestamente, essa área não está entre as suas cinco maiores prioridades este ano; o processo atual funciona razoavelmente."))
    if outras:
        fatos.append(("MÉDIO", f"Prioridade concorrente que disputa orçamento e atenção: {rng.choice(outras)}"))
    if papel == "decisor":
        fatos.append(("MÉDIO", "Você tem alçada para aprovar sozinho uma contratação deste porte."))
    else:
        fatos.append(("MÉDIO", f"Você recomenda, mas quem aprova é o {chefe}."))
    fatos.append(("DIFÍCIL", f"Orçamento disponível para essa frente: R$ {orcamento:,} por ano.".replace(",", ".")))
    fatos.append(("DIFÍCIL", rng.choice(TIMINGS)))

    return {
        "id": uuid.uuid4().hex[:10],
        "empresa": empresa, "produto_id": produto["id"],
        "cargo": cargo, "papel": papel, "chefe": chefe,
        "nivel_tecnico": nivel_tecnico, "fit": fit, "orcamento": orcamento,
        "preco_tabela": preco, "piso": piso,
        "fatos_privados": fatos,
        "comprador": {"nome": nome_pessoa(rng), "estilo": estilo_comprador,
                      "momento": rng.choice(MOMENTOS_COMPRADOR)},
        "vendedor": {"nome": nome_pessoa(rng), "estilo": estilo_vendedor},
        "perfil": {  # vetor de atributos para recuperação de lições
            "setor": empresa["setor"], "porte": empresa.get("porte", "grande"),
            "maturidade_digital": empresa.get("maturidade_digital", "media"),
            "cargo": cargo, "papel": papel,
        },
    }
