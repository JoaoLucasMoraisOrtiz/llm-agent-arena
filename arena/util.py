import json
import re

TAGS_TURNO = ("pensamento", "estado", "tecnica", "fala", "acoes")


def extrair_bloco(txt: str, tag: str) -> str | None:
    m = re.search(rf"<{tag}>(.*?)(?:</{tag}>|$)", txt, re.S)
    if not m:
        return None
    conteudo = m.group(1)
    # se a tag não foi fechada, corta na próxima tag conhecida
    prox = re.search(r"<(?:" + "|".join(TAGS_TURNO) + r")>", conteudo)
    if prox and f"</{tag}>" not in txt:
        conteudo = conteudo[:prox.start()]
    return conteudo.strip()


def extrair_json(txt: str):
    m = re.search(r"```(?:json)?\s*(\{.*\}|\[.*\])\s*```", txt, re.S)
    bruto = m.group(1) if m else None
    if not bruto:
        ini = min([i for i in (txt.find("{"), txt.find("[")) if i >= 0], default=-1)
        fim = max(txt.rfind("}"), txt.rfind("]"))
        if ini < 0 or fim <= ini:
            raise ValueError("JSON não encontrado")
        bruto = txt[ini:fim + 1]
    return json.loads(bruto)


def palavras(txt: str) -> int:
    return len(re.findall(r"\w+", txt or ""))


RE_ACAO = re.compile(r"(\w+)\s*\((.*?)\)?\s*$")     # tolera parêntese final ausente (saída truncada)
RE_ARG = re.compile(r'(\w+)\s*=\s*("([^"]*)"?|[\d.,]+)')


def parse_acoes(txt: str | None) -> list[dict]:
    acoes = []
    for linha in (txt or "").splitlines():
        linha = linha.strip().strip("-").strip()
        m = RE_ACAO.match(linha)
        if not m:
            continue
        args = {}
        for a in RE_ARG.finditer(m.group(2)):
            chave, valor = a.group(1), a.group(3) if a.group(3) is not None else a.group(2)
            if a.group(3) is None:
                v = valor.replace(".", "").replace(",", ".") if valor.count(".") > 1 or "," in valor else valor
                try:
                    valor = float(v)
                except ValueError:
                    pass
            args[chave] = valor
        acoes.append({"acao": m.group(1), **args})
    return acoes


RE_FORMATACAO = re.compile(r"(\*\*|__|^\s*[-•]\s|^\s*\d+\)\s|^\s*\d+\.\s|#)", re.M)
RE_EMOJI = re.compile("[\U0001F300-\U0001FAFF☀-➿]")


def limpar_fala(fala: str) -> tuple[str, bool]:
    """Remove formatação que não existe numa ligação. Retorna (fala, tinha_formatacao)."""
    sujo = bool(RE_FORMATACAO.search(fala) or RE_EMOJI.search(fala))
    fala = RE_EMOJI.sub("", fala)
    fala = re.sub(r"\*\*|__|#+", "", fala)
    fala = re.sub(r"^\s*(?:[-•]|\d+[.)])\s*", "", fala, flags=re.M)
    fala = re.sub(r"\*[^*]{1,40}\*", "", fala)          # *sorri*
    fala = re.sub(r"\s*\n\s*", " ", fala).strip()
    return fala, sujo


def reais(v: float) -> str:
    return f"R$ {int(v):,}".replace(",", ".")
