"""M3: memória estratégica por linhagem. Recuperação por atributos + amostragem de Thompson,
atribuição de crédito, staging e validação de lições. Ver arquitetura.md §5."""
import json
import random
import re
import uuid

from ..config import CFG

# Fase 0.4: lições universais ("sempre", "nunca", "com qualquer vendedor") e lições de bloqueio (encerrar/recusar/filtrar)
RE_UNIVERSAL = re.compile(r"\b(sempre|nunca|jamais|em qualquer (?:est[aá]gio|situa[cç][aã]o|caso)|com qualquer vendedor|"
                          r"todo(?:s os)? vendedor(?:es)?|qualquer vendedor|independentemente)\b", re.I)
RE_BLOQUEIO = re.compile(r"\b(encerr\w*|recus\w*|dispens\w*|deslig\w*|cort\w* a (?:liga[cç][aã]o|conversa)|"
                         r"n[aã]o (?:aceit|concedo|marc|revel|agend)\w*|filtr\w*)\b", re.I)


def condicao_vazia(licao: dict) -> bool:
    return not any(v for v in (licao.get("condicao") or {}).values())


def eh_universal(licao: dict) -> bool:
    return bool(RE_UNIVERSAL.search(f"{licao.get('acao', '')} {licao.get('porque', '')}")) and condicao_vazia(licao)


def eh_bloqueio(licao: dict) -> bool:
    return bool(RE_BLOQUEIO.search(licao.get("acao", "")))


PESOS = {"estagio": 3, "cargo": 2, "setor": 2, "papel": 1.5, "maturidade_digital": 1, "porte": 1, "estilo_oponente": 1}
TEMAS = ["abertura", "descoberta", "objecao", "preco", "fechamento", "relacionamento"]


def _casa(cond_val, perfil_val) -> float | None:
    """1 = casa, 0.5 = curinga, None = conflito."""
    if cond_val in (None, "", "null", "qualquer"):
        return 0.5
    if perfil_val is None:
        return 0.5
    vals = cond_val if isinstance(cond_val, list) else [cond_val]
    vals = [str(v).lower() for v in vals]
    pv = str(perfil_val).lower()
    if any(v.startswith(">=") for v in vals):          # ex.: maturidade ">=media"
        ordem = ["baixa", "media", "alta"]
        alvo = vals[0][2:]
        return 1.0 if alvo in ordem and pv in ordem and ordem.index(pv) >= ordem.index(alvo) else None
    return 1.0 if pv in vals else None


class MemoriaEstrategica:
    def __init__(self, db, rng: random.Random):
        self.db, self.rng = db, rng

    # ------------------------------------------------------------ leitura
    def playbook(self, linhagem: str, versao: int) -> str:
        r = self.db.um("SELECT playbook FROM versoes WHERE linhagem_id=? AND numero=?", (linhagem, versao))
        return (r["playbook"] or "") if r else ""

    def ativas(self, linhagem: str, versao: int) -> list[dict]:
        rows = self.db.todos(
            """SELECT * FROM licoes WHERE linhagem_id=? AND versao_criada<=?
               AND (versao_aposentada IS NULL OR versao_aposentada>?)""", (linhagem, versao, versao))
        out = []
        for r in rows:
            d = dict(r)
            d["condicao"] = json.loads(d["condicao"])
            d["tecnicas"] = json.loads(d["tecnicas"] or "[]")
            out.append(d)
        return out

    def recuperar(self, linhagem: str, versao: int, perfil: dict, k: int | None = None) -> list[dict]:
        k = k or CFG["memoria"]["licoes_por_call"]
        cand = []
        for l in self.ativas(linhagem, versao):
            s, conflito = 0.0, False
            for attr, peso in PESOS.items():
                c = _casa(l["condicao"].get(attr), perfil.get(attr))
                if c is None:
                    conflito = True
                    break
                s += peso * c
            if conflito:
                continue
            s /= sum(PESOS.values())
            u = (self.rng.betavariate(l["alpha"], l["beta"]) if CFG["memoria"]["thompson"]
                 else l["alpha"] / (l["alpha"] + l["beta"]))
            cand.append((s * u, l))
        cand.sort(key=lambda x: -x[0])
        escolhidas, por_tema = [], {}
        for _, l in cand:
            if por_tema.get(l["tema"], 0) >= CFG["memoria"]["max_por_tema"]:
                continue
            escolhidas.append(l)
            por_tema[l["tema"]] = por_tema.get(l["tema"], 0) + 1
            if len(escolhidas) >= k:
                break
        for l in escolhidas:
            self.db.ex("UPDATE licoes SET recuperada=recuperada+1 WHERE id=?", (l["id"],))
        return escolhidas

    # ------------------------------------------------------------ escrita
    def creditar(self, call_id: str, linhagem: str, creditos: list[dict], ids_validos: set[str]):
        for c in creditos:
            lid = c.get("licao_id")
            if lid not in ids_validos:
                continue
            aplicada = bool(c.get("aplicada"))
            efeito = c.get("efeito")
            self.db.inserir("licoes_uso", call_id=call_id, licao_id=lid, linhagem_id=linhagem,
                            aplicada=int(aplicada), turno=c.get("turno"), efeito=efeito)
            if not aplicada:
                continue
            campos = "aplicada=aplicada+1"
            if efeito == "ajudou":
                campos += ", ajudou=ajudou+1, alpha=alpha+1"
            elif efeito == "atrapalhou":
                campos += ", atrapalhou=atrapalhou+1, beta=beta+1"
            self.db.ex(f"UPDATE licoes SET {campos} WHERE id=?", (lid,))

    def validar(self, licao: dict, nomes_proibidos: list[str], linhagem: str | None = None) -> str | None:
        """Guarda contra vazamento de caso (arquitetura.md §5.5) e, para o comprador, contra lições universais sem
        condição (Fase 0.4). Retorna motivo de rejeição ou None."""
        texto = f"{licao.get('acao', '')} {licao.get('porque', '')}"
        if len(licao.get("acao", "")) < 15:
            return "ação vaga"
        if linhagem and linhagem.startswith("comprador") and eh_universal(licao):
            return "lição universal sem condição (irrealista para um comprador)"
        for nome in nomes_proibidos:
            partes = [p for p in re.split(r"\W+", nome) if len(p) >= 4]
            if any(re.search(rf"\b{re.escape(p)}\b", texto, re.I) for p in partes):
                return f"cita nome do caso ({nome})"
        if re.search(r"R\$\s?\d|\d{3}\.\d{3}|\d+\s?mil reais", texto):
            return "cita valor absoluto"
        return None

    def encenar(self, rodada: int, linhagem: str, licao: dict, call_id: str):
        self.db.inserir("staging", rodada=rodada, linhagem_id=linhagem, conteudo=licao, call_id=call_id)

    @staticmethod
    def sanitizar_condicao(linhagem: str, cond: dict) -> dict:
        """Mantém só atributos/valores válidos; estilo_oponente precisa ser um estilo do OUTRO lado."""
        from ..conhecimento import ESTILOS_COMPRADOR, ESTILOS_VENDEDOR
        validos = {
            "setor": {"varejo", "industria", "mobilidade", "agro", "saude"}, "porte": {"media", "grande"},
            "maturidade_digital": {"baixa", "media", "alta"},
            "cargo": {"CTO", "CFO", "COO", "Diretor de Compras", "Diretor Comercial"},
            "papel": {"decisor", "influenciador"}, "estagio": {"cold_call", "discovery", "fechamento"},
            "estilo_oponente": set(ESTILOS_COMPRADOR if linhagem.startswith("vendedor") else ESTILOS_VENDEDOR),
        }
        out = {}
        for k, vs in validos.items():
            v = (cond or {}).get(k)
            if isinstance(v, list):
                v = [x for x in v if x in vs] or None
            elif isinstance(v, str) and v.startswith(">=") and k == "maturidade_digital":
                v = v if v[2:] in vs else None
            elif v not in vs:
                v = None
            out[k] = v
        return out

    def inserir_licao(self, linhagem: str, versao: int, licao: dict, alpha=1.0, beta=1.0,
                      evidencias=None, lid: str | None = None) -> str:
        lid = lid or f"L-{linhagem.replace('/', '-')}-{uuid.uuid4().hex[:5]}"
        licao = {**licao, "condicao": self.sanitizar_condicao(linhagem, licao.get("condicao", {}))}
        tema = licao.get("tema") if licao.get("tema") in TEMAS else "relacionamento"
        self.db.inserir("licoes", id=lid, linhagem_id=linhagem, condicao=licao.get("condicao", {}),
                        tipo=licao.get("tipo", "fazer"), tema=tema, acao=licao["acao"], porque=licao.get("porque", ""),
                        tecnicas=licao.get("tecnicas", []), alpha=alpha, beta=beta, status="ativa",
                        versao_criada=versao, versao_aposentada=None, evidencias=evidencias or [])
        return lid
