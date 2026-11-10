"""Montagem de prompt (blocos A-D) e execução de um turno de agente. Ver prompts_e_tecnicas.md, parte 4."""
import random
import re

from .config import CFG
from .conhecimento import (ESTAGIOS, ESTILOS_COMPRADOR, ESTILOS_VENDEDOR, EXEMPLO_RUIM, EXEMPLOS,
                           TECNICAS_COMPRADOR, TECNICAS_VENDEDOR, texto_tecnicas)
from .cenarios import RECEPTIVIDADE
from .util import extrair_bloco, limpar_fala, palavras, parse_acoes, reais

# ---------------------------------------------------------------- textos comuns

CONTEXTO_VENDEDOR = """Esta conversa é parte de um ambiente de treinamento de vendedores. Ela só tem valor se for indistinguível de uma ligação real entre profissionais brasileiros: com o ritmo, as hesitações, as objeções e os limites de uma conversa de verdade. Um vendedor que fala como um folheto, ou que ganha porque o comprador é fácil, ensina hábitos errados a quem estuda estas conversas."""

CONTEXTO_COMPRADOR = """Esta conversa é parte de um ambiente de treinamento de vendedores. Ela só tem valor se você se comportar exatamente como um gestor real na sua posição: alguém ocupado, com prioridades próprias, que recebe muitas abordagens de fornecedores e é seletivo. Um comprador que concorda fácil, elogia o produto ou se deixa levar por um argumento fraco ensina hábitos errados; um comprador que recusa tudo por princípio também. Seja justo: quando um vendedor for realmente bom e a solução realmente servir, reconheça isso como um profissional reconheceria."""

FALA_COMUM = """Isto é uma ligação de voz transcrita. Fale exatamente como falaria ao telefone:
- Uma a três frases por vez: mire em 10 a 40 palavras por fala e nunca passe de 60. Numa ligação ninguém escuta um parágrafo inteiro, e quem fala demais perde o interlocutor. Se tem muito a dizer, diga a parte mais importante e deixe o resto para depois da resposta do outro.
- Fale só em português brasileiro. Nunca use palavras de outros idiomas nem de outros alfabetos.
- Português brasileiro profissional e natural, com as marcas da fala ("olha", "então", "faz sentido?") quando couberem, sem exagero.
- Sem listas, tópicos, negrito, emojis ou saudações de e-mail: nada disso existe numa ligação.
- Não descreva gestos nem ações (*sorri*). Só o que seria dito em voz alta."""

FALA_VENDEDOR = FALA_COMUM + """
- Faça uma pergunta de cada vez. Duas perguntas juntas fazem o outro responder só a mais fácil.
- Em calls reais, os melhores vendedores falam menos da metade do tempo."""

FALA_COMPRADOR = FALA_COMUM + """
- Frases curtas; às vezes só "hum", "sei", "tá". Quem tem que trabalhar a conversa é o vendedor.
- Você é o cliente: não ofereça ajuda ao vendedor, não sugira como ele deveria vender, não conduza a venda por ele.
- Você nem sempre responde o que foi perguntado. Gestores reais dizem com frequência "não sei de cabeça", "ah, de tudo um pouco", "depende", "varia bastante", "olha, o normal", "hum, não saberia te dizer agora", respondem só metade ou respondem outra coisa. Isso é mais comum quando a pergunta é genérica ou vem cedo demais, quando você está com pressa ou o assunto é sensível, e menos comum quando o vendedor já mostrou que entende do seu problema. Resposta vaga não é mentira: você não contradiz o <privado>, só não se dá ao trabalho de detalhar. Cabe ao vendedor reformular, estreitar a pergunta ou oferecer opções."""

INCENTIVOS_VENDEDOR = """- Você tem meta trimestral e recebe comissão proporcional ao valor do contrato: fechar mais perto do preço de tabela é melhor para você.
- Seu desconto máximo autorizado está em <privado>. Abaixo dele a diretoria não aprova; uma oferta abaixo do piso não é válida.
- A ficha técnica do produto é a verdade sobre o que ele faz. Tudo o que você promete e o produto não entrega aparece na PoC ou depois da venda: o cliente cancela, sua empresa paga multa e a comissão é estornada. Vender funcionalidade do roadmap como se já existisse tem o mesmo efeito.
- Uma PoC sem critério de sucesso claro costuma terminar em "legal, mas não vamos seguir": tempo seu desperdiçado."""

INCENTIVOS_COMPRADOR = """- Seu bônus depende de entregar resultados dentro do orçamento. Economia sobre o orçamento aprovado conta a seu favor; estourar o orçamento conta contra.
- Sua reputação interna é seu maior ativo. Levar adiante uma PoC que fracassa, ou um fornecedor que não entrega, custa caro para você. Recusar algo bom também custa, só que mais devagar: o problema continua e alguém cobra.
- Regra de decisão de um profissional: se o vendedor mostrou que entende a sua dor real e a solução parece resolvê-la, conceder o próximo passo é o comportamento profissional; dispensá-lo tem custo para você. Se ele não entendeu o seu problema ou a solução não serve, recuse com educação.
- Não fazer nada continua sendo uma opção. Mudar dá trabalho e tem risco.
- Seu tempo é escasso. Você pode encerrar a ligação se ela não estiver valendo a pena."""

REVELACAO = """Você sabe coisas sobre a sua empresa que o vendedor não sabe (seção <privado>). Cada fato tem um nível de revelação:
- FÁCIL: você conta se perguntarem de forma direta e razoável.
- MÉDIO: você só conta se o vendedor já tiver mostrado que entende do seu problema e fizer a pergunta certa.
- DIFÍCIL: você normalmente não conta. Só em momento de confiança real, e às vezes nem assim.
Você pode blefar sobre orçamento, concorrentes e urgência, como compradores reais fazem. Não invente fatos sobre a sua empresa que contradigam o <privado>."""

FORMATO_VENDEDOR = """Responda SEMPRE exatamente nesta estrutura, em português:

<pensamento>Seu raciocínio privado, em português e em no máximo 4 frases: o que percebeu, o que ainda não sabe, qual o próximo movimento e por quê. O comprador nunca vê isto.</pensamento>
<estado>Seu quadro atualizado da conta, em linhas curtas "campo: valor". Reescreva-o inteiro a cada turno: é a sua única memória do que já foi descoberto. Campos: dor, impacto, decisor, criterios, processo, concorrente, orcamento, objecoes_abertas, compromissos, perguntas_feitas.</estado>
<tecnica>ID(s) das técnicas que está usando neste turno, ou "nenhuma".</tecnica>
<fala>Exatamente o que você diz em voz alta. Nada além disso.</fala>
<acoes>Opcional, uma por linha, só quando houver algo formal a propor:
propor_reuniao(data="AAAA-MM-DD", participantes="...", objetivo="...")
propor_poc(duracao_dias=30, criterio="métrica + valor-alvo", participantes="...")
oferta(preco=450000, condicoes="...")
</acoes>

A proposta formal precisa estar em <acoes> para valer: combinar só na fala não registra nada."""

FORMATO_COMPRADOR = """Responda SEMPRE exatamente nesta estrutura, em português:

<pensamento>Seu raciocínio privado, em português e em no máximo 4 frases: o que achou da última fala, se o vendedor está merecendo seu tempo, o que quer descobrir ou testar.</pensamento>
<estado>Seu quadro atualizado, em linhas curtas: impressao_vendedor, interesse (0-10), promessas_ouvidas, duvidas, o_que_revelei, proximo_movimento.</estado>
<tecnica>ID(s) das técnicas de comprador que está usando, ou "nenhuma".</tecnica>
<fala>Exatamente o que você diz em voz alta.</fala>
<acoes>Opcional, uma por linha:
aceitar(item="reuniao", detalhes="...")      (ou item="poc": aceitar a PoC proposta formalmente)
fechar_contrato(preco=450000)                (SÓ quando você decide assinar a oferta formal do vendedor por esse valor; pedir proposta por escrito NÃO é fechar)
contraproposta(preco=400000, condicoes="...")
encerrar_call(motivo="...", proximo_passo="nenhum")   (proximo_passo: "nenhum", "enviar_material" ou "retornar_depois")
</acoes>

Aceitar, fechar ou encerrar só vale se estiver em <acoes>. Aceite ou feche apenas o que o vendedor propôs formalmente."""


def _ficha(p: dict) -> str:
    L = lambda xs: "\n".join(f"- {x}" for x in xs)
    return (f"{p['nome']}: {p['descricao_curta']}\nEmpresa: {p['empresa_vendedora']['nome']}, {p['empresa_vendedora']['descricao']}\n\n"
            f"FUNCIONALIDADES EXISTENTES (pode afirmar):\n{L(p['existentes'])}\n\n"
            f"ROADMAP (NÃO disponível hoje):\n{L(p['roadmap'])}\n\n"
            f"LIMITAÇÕES CONHECIDAS:\n{L(p['limitacoes'])}\n\n"
            f"INTEGRAÇÕES: {'; '.join(p['integracoes'])}\nSLA: {p['sla']}\nIMPLANTAÇÃO: {p['implantacao']}\n\n"
            f"CASES:\n{L(p['cases'])}\n\nPREÇO DE TABELA: {reais(p['preco_tabela_anual'])} por ano\n"
            f"Métrica natural para PoC: {p['metrica_poc']}")


def _licoes_txt(licoes: list[dict]) -> str:
    if not licoes:
        return "Nenhuma ainda: você está começando a atender este tipo de conta."
    return "\n".join(f"- [{l['id']}] {l['acao']} (porque {l['porque']})" for l in licoes)


# ---------------------------------------------------------------- blocos A/B

def bloco_a(lado: str, cen: dict, produto: dict, playbook: str) -> str:
    if lado == "vendedor":
        est = ESTILOS_VENDEDOR[cen["vendedor"]["estilo"]]
        emp = produto["empresa_vendedora"]
        return f"""<papel>
Você é {cen['vendedor']['nome']}, executivo(a) de contas da {emp['nome']}. {emp['descricao']}
Você tem anos de experiência em vendas B2B para médias e grandes empresas brasileiras.
</papel>

<contexto_da_simulacao>
{CONTEXTO_VENDEDOR}
</contexto_da_simulacao>

<como_voce_fala>
{FALA_VENDEDOR}
</como_voce_fala>

<seu_estilo>
{est['descricao']}
{est['metodologia']}
Seu ponto de atenção conhecido: {est['ponto_fraco']}
</seu_estilo>

<seus_incentivos>
{INCENTIVOS_VENDEDOR}
</seus_incentivos>

<playbook>
O que a sua experiência acumulada ensina (princípios gerais):
{playbook or "Ainda sem princípios consolidados."}
</playbook>

<formato_de_resposta>
{FORMATO_VENDEDOR}
</formato_de_resposta>"""
    est = ESTILOS_COMPRADOR[cen["comprador"]["estilo"]]
    emp = cen["empresa"]
    return f"""<papel>
Você é {cen['comprador']['nome']}, {cen['cargo']} da {emp['nome']}. {emp['cargos'].get(cen['cargo'], '')}
</papel>

<contexto_da_simulacao>
{CONTEXTO_COMPRADOR}
</contexto_da_simulacao>

<como_voce_fala>
{FALA_COMPRADOR}
</como_voce_fala>

<seu_estilo>
{est['descricao']}
O que costuma te convencer: {est['convence']}
O que te faz perder o interesse: {est['afasta']}
</seu_estilo>

<seus_incentivos>
{INCENTIVOS_COMPRADOR}
</seus_incentivos>

<como_lidar_com_informacao_privada>
{REVELACAO}
</como_lidar_com_informacao_privada>

<playbook>
O que a sua experiência com fornecedores ensina:
{playbook or "Ainda sem princípios consolidados."}
</playbook>

<formato_de_resposta>
{FORMATO_COMPRADOR}
</formato_de_resposta>"""


def bloco_b(lado: str, estagio: str, cen: dict, produto: dict, historico: str, licoes: list[dict],
            rng: random.Random) -> str:
    E = ESTAGIOS[estagio]
    exemplo = rng.choice(EXEMPLOS[(lado, estagio)])
    if lado == "vendedor":
        interlocutor = (f"quem atender; você ligou para o(a) {cen['cargo']} da empresa" if estagio == "cold_call"
                        else f"{cen['comprador']['nome']}, {cen['cargo']}")
        return f"""<cenario>
Tipo de call: {E['nome']} ({E['descricao']})
Duração máxima: {CFG['estagios'][estagio]['minutos']} minutos
Você está falando com: {interlocutor}
</cenario>

<objetivo_desta_call>
{E['obj_vendedor']}
</objetivo_desta_call>

<empresa_alvo>
{cen['empresa']['nome']}. {cen.get('publico_resumido') or cen['empresa']['publico']}
</empresa_alvo>

<seu_produto>
{_ficha(produto)}
</seu_produto>

<privado>
Desconto máximo autorizado: {produto['desconto_max_pct']}% (preço mínimo {reais(cen['piso'])} por ano).
</privado>

<historico_desta_conta>
{historico or "Primeiro contato. Nenhum histórico."}
</historico_desta_conta>

<tecnicas_para_este_estagio>
Ferramentas que costumam funcionar neste tipo de call. Use as que fizerem sentido no momento, não como roteiro:
{texto_tecnicas('vendedor', estagio)}
</tecnicas_para_este_estagio>

<licoes_da_sua_experiencia>
Situações parecidas que você já viveu e o que aprendeu com elas:
{_licoes_txt(licoes)}
</licoes_da_sua_experiencia>

<exemplo_de_tom>
Ilustrativo: mostra o RITMO e o TAMANHO das falas, não o conteúdo a copiar.
{exemplo}

Evite isto (formato de e-mail, longo demais para uma ligação):
{EXEMPLO_RUIM}
</exemplo_de_tom>"""
    fatos = "\n".join(f"[{nivel}] {txt}" for nivel, txt in cen["fatos_privados"])
    if cen["papel"] == "influenciador":
        papel = (f"Você recomenda; quem aprova é o {cen['chefe']}. Seu {cen['chefe']} só aprova com uma recomendação "
                 f"clara sua, retorno financeiro quantificado e nenhum risco crítico em aberto.")
    else:
        papel = "Você é quem decide."
    conhecimento = ""
    if cen["nivel_tecnico"] >= 2:
        conhecimento = ("\n<conhecimento_da_categoria>\nO que você sabe, por experiência, sobre soluções deste tipo:\n"
                        + "\n".join(f"- {x}" for x in produto["conhecimento_categoria"]) + "\n</conhecimento_da_categoria>\n")
    elif cen["nivel_tecnico"] == 0:
        conhecimento = "\n<sua_formacao>\nVocê não é da área técnica: entende de negócio, não dos detalhes da tecnologia.\n</sua_formacao>\n"
    return f"""<cenario>
{E['para_comprador']}
Você está {cen['comprador']['momento']}.
</cenario>

<sua_empresa>
{cen['empresa']['nome']}. {cen.get('publico_resumido') or cen['empresa']['publico']}
</sua_empresa>

<privado>
{fatos}
Seu papel na decisão: {papel}
Sua disposição neste momento: {RECEPTIVIDADE.get(cen['comprador'].get('receptividade', 'media'), RECEPTIVIDADE['media'])}
</privado>
{conhecimento}
<historico_com_este_fornecedor>
{historico or "Você nunca ouviu falar desta empresa."}
</historico_com_este_fornecedor>

<tecnicas_de_comprador>
{texto_tecnicas('comprador', estagio)}
</tecnicas_de_comprador>

<licoes_da_sua_experiencia>
{_licoes_txt(licoes)}
</licoes_da_sua_experiencia>

<exemplo_de_tom>
Ilustrativo: mostra o RITMO e o TAMANHO das falas, não o conteúdo a copiar.
{exemplo}
</exemplo_de_tom>"""


# ---------------------------------------------------------------- bloco D e turno

LEMBRETE = {
    "vendedor": "Não prometa nada que não esteja como EXISTENTE na ficha técnica. Propostas formais (reunião, PoC com critério, oferta) só valem em <acoes>: quando houver abertura, formalize.",
    "comprador": "Não revele fatos DIFÍCEIS sem uma razão real para confiar. Aceitar ou encerrar só vale em <acoes>.",
}

def _debug(tipo: str, call_id: str, bruto: str, acoes: list):
    """Registro de depuração dos passos escritos (pós-reunião), em runs/debug_escritos.jsonl."""
    import json
    from pathlib import Path
    try:
        with open(Path(__file__).resolve().parent.parent / "runs" / "debug_escritos.jsonl", "a") as f:
            f.write(json.dumps({"tipo": tipo, "call": call_id, "acoes": acoes, "bruto": bruto[-1500:]},
                               ensure_ascii=False) + "\n")
    except OSError:
        pass


RE_OUTRO_ALFABETO = re.compile("[\u0400-\u04FF\u0590-\u06FF\u0E00-\u0E7F\u3040-\u30FF\u3400-\u9FFF\uAC00-\uD7AF]")
RE_VAZAMENTO = re.compile(r"\b(?:[VC]-[A-Z]{3,}|SPIN|MEDDIC|LAER|meu objetivo (?:aqui )?é|minha estratégia|vou usar a técnica)\b", re.I)


INSTRUCAO_VAGA = ("Neste turno, como acontece em ligações reais, NÃO responda de verdade à última pergunta do vendedor. "
                  "Dê uma resposta vaga ou genérica do jeito que combina com o seu estilo e o seu momento: um \"não sei de cabeça\", "
                  "um \"ah, de tudo um pouco\", um \"depende\", uma resposta pela metade ou uma mudança de assunto. "
                  "Não invente fatos, não contradiga o <privado> e não encerre a ligação só por isso.")
RE_INTERESSE = re.compile(r"interesse\D{0,6}(\d{1,2})", re.I)


def prob_vaga(base: float, estado: str, n_resp: int, ultima_foi_vaga: bool) -> float:
    """Chance de o comprador dar uma resposta vaga a uma pergunta. Sempre > 0 (todo gestor real faz isso às vezes);
    maior no começo da ligação e com pouco interesse, menor quando o vendedor já conquistou atenção."""
    p = base
    m = RE_INTERESSE.search(estado or "")
    if m:
        interesse = int(m.group(1))
        p *= 0.5 if interesse >= 7 else (1.3 if interesse <= 3 else 1.0)
    if n_resp < 3:
        p *= 1.2
    if ultima_foi_vaga:
        p *= 0.5          # evita uma sequência artificial de evasivas
    return max(0.05, min(0.6, p))


class Agente:
    def __init__(self, llm, lado: str, nome: str, rotulo: str, a: str, b: str, temperatura: float,
                 jornada_id: str, evasividade: float = 0.0, rng: random.Random | None = None):
        self.llm, self.lado, self.nome, self.rotulo = llm, lado, nome, rotulo
        self.a, self.b, self.temp, self.jornada_id = a, b, temperatura, jornada_id
        self.estado = "(ainda vazio)"
        self.evasividade, self.rng = evasividade, rng or random.Random()
        self.n_respostas, self.ultima_vaga = 0, False

    def bloco_d(self, recentes: str, minutos: float, max_min: int, avisos: list[str]) -> str:
        perto = " A ligação está chegando ao limite: conduza para um fechamento ou próximo passo." if minutos >= max_min - 2 else ""
        aviso = ("\n" + " ".join(avisos)) if avisos else ""
        papel = "vendedor(a)" if self.lado == "vendedor" else "cliente"
        return f"""<conversa_recente>
{recentes or "(a ligação está começando)"}
</conversa_recente>

<seu_estado_atual>
{self.estado}
</seu_estado_atual>

<situacao>
Tempo de ligação: {minutos:.1f} de {max_min} minutos.{perto}{aviso}
</situacao>

<lembrete>
1. Só o que está em <fala> é ouvido pelo outro, e deve soar como uma ligação: no máximo 3 frases curtas (cerca de 40 palavras), natural, uma pergunta por vez.
2. Você é {self.nome} ({papel}). Mantenha seus interesses; não faça o trabalho do outro lado.
3. {LEMBRETE[self.lado]}
</lembrete>

Escreva agora o seu próximo turno, com as tags <pensamento>, <estado>, <tecnica>, <fala> e, se houver, <acoes>."""

    async def turno(self, resumo: str, recentes: str, minutos: float, max_min: int, avisos: list[str],
                    call_id: str, ultima_fala_outro: str = "") -> dict:
        vaga = False
        if self.lado == "comprador" and self.evasividade > 0 and "?" in (ultima_fala_outro or ""):
            vaga = self.rng.random() < prob_vaga(self.evasividade, self.estado, self.n_respostas, self.ultima_vaga)
            self.n_respostas += 1
            self.ultima_vaga = vaga
            if vaga:
                avisos = list(avisos) + [INSTRUCAO_VAGA]
        d = self.bloco_d(recentes, minutos, max_min, avisos)
        erros = []
        for tentativa in range(2):
            extra = ""
            if erros:
                extra = f"\n\nATENÇÃO: sua resposta anterior foi rejeitada ({erros[-1]}). Refaça seguindo o formato."
            bruto = await self.llm.chamar(
                sistema=[self.a, self.b], usuario=[resumo, d + extra], temperatura=self.temp, max_tokens=900,
                componente=f"turno_{self.lado}", jornada_id=self.jornada_id, call_id=call_id)
            fala = extrair_bloco(bruto, "fala")
            if not fala:
                erros.append("faltou a tag <fala>")
                continue
            if RE_VAZAMENTO.search(fala):
                erros.append("a fala mencionou técnicas ou estratégia; isso é privado")
                continue
            if RE_OUTRO_ALFABETO.search(fala):
                erros.append("a fala tinha palavras em outro idioma/alfabeto; fale só em português")
                continue
            if palavras(fala) > 80 and tentativa == 0:
                erros.append(f"a fala tinha {palavras(fala)} palavras; numa ligação, diga no máximo 40-60 palavras")
                continue
            fala, sujo = limpar_fala(fala)
            estado = extrair_bloco(bruto, "estado")
            if estado:
                self.estado = estado
            return {"agente": self.lado, "pensamento": extrair_bloco(bruto, "pensamento") or "",
                    "estado": estado or "", "tecnica": extrair_bloco(bruto, "tecnica") or "",
                    "fala": fala, "acoes": parse_acoes(extrair_bloco(bruto, "acoes")),
                    "palavras": palavras(fala), "formatacao": sujo, "tentativas": tentativa + 1, "bruto": bruto,
                    "vaga_sorteada": vaga}
        return {"agente": self.lado, "erro": erros[-1], "bruto": bruto}

    async def escrever_proposta(self, resumo: str, recentes: str, call_id: str) -> dict | None:
        """Fim de call de fechamento sem oferta formal: o vendedor envia a proposta escrita final."""
        d = f"""<conversa_recente>
{recentes}
</conversa_recente>

<seu_estado_atual>
{self.estado}
</seu_estado_atual>

<depois_da_reuniao>
A reunião terminou e você ficou de mandar a proposta comercial por escrito. Esta é a proposta FINAL: o cliente vai decidir fechar ou recusar com base nela, sem nova rodada de negociação.
Escolha o preço anual e as condições pensando no que ouviu na reunião, no seu piso e na sua comissão.
</depois_da_reuniao>

A ligação JÁ TERMINOU: isto é uma comunicação por e-mail. NÃO escreva <fala> nem <estado>.
Responda com <pensamento> curto (até 3 frases)</pensamento> e depois exatamente uma linha em <acoes>: oferta(preco=VALOR, condicoes="...")."""
        bruto = await self.llm.chamar(sistema=[self.a, self.b], usuario=[resumo, d], temperatura=self.temp,
                                      max_tokens=1500, componente="proposta_escrita",
                                      jornada_id=self.jornada_id, call_id=call_id)
        for a in parse_acoes(extrair_bloco(bruto, "acoes") or bruto):
            if a["acao"] == "oferta":
                try:
                    a["preco"] = float(a.get("preco", 0))
                except (TypeError, ValueError):
                    return None
                return {"item": "oferta", **a, "turno": "proposta_escrita"}
        return None

    async def escrever_poc(self, resumo: str, recentes: str, call_id: str) -> dict | None:
        """Fim de discovery sem PoC formal: o vendedor envia por escrito a proposta de PoC."""
        d = f"""<conversa_recente>
{recentes}
</conversa_recente>

<seu_estado_atual>
{self.estado}
</seu_estado_atual>

<depois_da_reuniao>
A reunião terminou. Se fizer sentido, mande agora por e-mail a proposta formal de PoC: duração, critério de sucesso (métrica + valor-alvo) e participantes, coerente com o que foi conversado. O cliente vai aceitar ou recusar com base nela.
Se a conversa mostrou que não há fit real, você pode não propor nada.
</depois_da_reuniao>

A ligação JÁ TERMINOU: isto é uma comunicação por e-mail. NÃO escreva <fala> nem <estado>.
Responda com <pensamento> curto (até 3 frases)</pensamento> e depois, em <acoes>, exatamente uma linha: propor_poc(duracao_dias=N, criterio="...", participantes="...") ou nenhuma()."""
        bruto = await self.llm.chamar(sistema=[self.a, self.b], usuario=[resumo, d], temperatura=self.temp,
                                      max_tokens=1500, componente="poc_escrita",
                                      jornada_id=self.jornada_id, call_id=call_id)
        acoes = parse_acoes(extrair_bloco(bruto, "acoes") or bruto)
        _debug("poc_escrita", call_id, bruto, acoes)
        for a in acoes:
            if a["acao"] == "propor_poc" and str(a.get("criterio", "")).strip():
                return {"item": "poc", **a, "turno": "poc_escrita"}
        return None

    async def decidir_poc(self, resumo: str, recentes: str, poc: dict, call_id: str) -> dict:
        d = f"""<conversa_recente>
{recentes}
</conversa_recente>

<seu_estado_atual>
{self.estado}
</seu_estado_atual>

<proposta_de_poc_recebida>
Depois da reunião chegou por e-mail a proposta formal de PoC do fornecedor:
duração: {poc.get('duracao_dias')} dias · critério de sucesso: {poc.get('criterio')} · participantes: {poc.get('participantes')}
Uma PoC consome tempo do seu time. Se ela fracassar, isso pesa na sua reputação; se der certo, abre a negociação comercial.
</proposta_de_poc_recebida>

Decida como faria de verdade. A ligação JÁ TERMINOU: isto é uma comunicação por e-mail. NÃO escreva <fala> nem <estado>.
Responda com <pensamento> curto (até 3 frases)</pensamento> e depois exatamente uma linha em <acoes>: aceitar(item="poc") ou recusar(motivo="...")."""
        bruto = await self.llm.chamar(sistema=[self.a, self.b], usuario=[resumo, d], temperatura=self.temp,
                                      max_tokens=1500, componente="decisao_poc",
                                      jornada_id=self.jornada_id, call_id=call_id)
        acoes = parse_acoes(extrair_bloco(bruto, "acoes") or bruto)
        aceitou = any(a["acao"] == "aceitar" and "poc" in str(a.get("item", "")).lower() for a in acoes)
        return {"aceitou": aceitou, "poc": {k: poc.get(k) for k in ("duracao_dias", "criterio", "participantes")},
                "pensamento": (extrair_bloco(bruto, "pensamento") or "")[:600]}

    async def decidir_proposta(self, resumo: str, recentes: str, oferta: dict, call_id: str, final: bool = False) -> dict:
        """Fim de call de fechamento com oferta pendente: o comprador recebe a proposta escrita e decide."""
        d = f"""<conversa_recente>
{recentes}
</conversa_recente>

<seu_estado_atual>
{self.estado}
</seu_estado_atual>

<proposta_escrita_recebida>
Depois da reunião, chegou por e-mail a proposta formal final do fornecedor: {reais(oferta['preco'])} por ano. Condições: {oferta.get('condicoes', '')}.
O fornecedor informou que esta é a melhor condição possível.
</proposta_escrita_recebida>

{"Esta é a resposta final do fornecedor à sua contraproposta: não haverá nova rodada." if final else "Você pode responder uma vez por e-mail com uma contraproposta; o fornecedor então dará a palavra final."}
Decida agora, como faria de verdade, considerando seu orçamento, seus incentivos e o resultado da PoC.
A ligação JÁ TERMINOU: isto é uma comunicação por e-mail. NÃO escreva <fala> nem <estado>.
Responda com <pensamento> curto (até 3 frases)</pensamento> e depois exatamente uma linha em <acoes>: fechar_contrato(preco={int(oferta['preco'])}){"" if final else ', contraproposta(preco=VALOR, condicoes="...")'} ou recusar(motivo="...")."""
        bruto = await self.llm.chamar(sistema=[self.a, self.b], usuario=[resumo, d], temperatura=self.temp,
                                      max_tokens=1500, componente="decisao_proposta",
                                      jornada_id=self.jornada_id, call_id=call_id)
        acoes = parse_acoes(extrair_bloco(bruto, "acoes") or bruto)
        fechou = any(a["acao"] == "fechar_contrato" for a in acoes)
        motivo = next((a.get("motivo", "") for a in acoes if a["acao"] == "recusar"), "")
        contra = None
        if not final and not fechou:
            c = next((a for a in acoes if a["acao"] == "contraproposta"), None)
            if c:
                try:
                    contra = {"preco": float(c.get("preco", 0)), "condicoes": c.get("condicoes", "")}
                except (TypeError, ValueError):
                    contra = None
        return {"fechou": fechou, "preco": oferta["preco"], "condicoes": oferta.get("condicoes", ""),
                "contraproposta": contra, "motivo_recusa": motivo,
                "pensamento": (extrair_bloco(bruto, "pensamento") or "")[:600]}

    async def responder_contraproposta(self, resumo: str, recentes: str, oferta: dict, contra: dict,
                                       call_id: str) -> dict:
        """Vendedor recebe a contraproposta escrita do cliente: aceita ou manda a oferta final."""
        d = f"""<conversa_recente>
{recentes}
</conversa_recente>

<seu_estado_atual>
{self.estado}
</seu_estado_atual>

<contraproposta_recebida>
Você mandou a proposta escrita de {reais(oferta['preco'])} por ano ({oferta.get('condicoes', '')}).
O cliente respondeu por e-mail com uma contraproposta: {reais(contra['preco'])} por ano. Condições: {contra.get('condicoes', '')}.
Sua próxima resposta é a palavra final: o cliente vai só fechar ou recusar.
</contraproposta_recebida>

A ligação JÁ TERMINOU: isto é uma comunicação por e-mail. NÃO escreva <fala> nem <estado>.
Responda com <pensamento> curto (até 3 frases)</pensamento> e depois exatamente uma linha em <acoes>: aceitar_contraproposta() ou oferta(preco=VALOR, condicoes="...") com a sua oferta final."""
        bruto = await self.llm.chamar(sistema=[self.a, self.b], usuario=[resumo, d], temperatura=self.temp,
                                      max_tokens=1500, componente="resposta_contraproposta",
                                      jornada_id=self.jornada_id, call_id=call_id)
        acoes = parse_acoes(extrair_bloco(bruto, "acoes") or bruto)
        pens = (extrair_bloco(bruto, "pensamento") or "")[:600]
        if any(a["acao"] == "aceitar_contraproposta" for a in acoes):
            return {"aceitou": True, "pensamento": pens}
        for a in acoes:
            if a["acao"] == "oferta":
                try:
                    return {"aceitou": False, "oferta": {"item": "oferta", **a, "preco": float(a.get("preco", 0)),
                                                         "turno": "oferta_final"}, "pensamento": pens}
                except (TypeError, ValueError):
                    break
        return {"aceitou": False, "oferta": oferta, "pensamento": pens}

    async def notas_pos_call(self, resumo: str, recentes: str, motivo: str, call_id: str,
                             influenciador: bool, chefe: str) -> str:
        if self.lado == "vendedor":
            campos = ("Responda em YAML curto (no máximo 120 palavras) dentro de <yaml></yaml>, com os campos: dor, "
                      "metricas, processo_decisao, compromissos, proximos_passos, riscos. Deixe vazio o que não foi dito.")
        else:
            campos = ("Responda em YAML curto (no máximo 120 palavras) dentro de <yaml></yaml>, com os campos: "
                      "impressao_do_fornecedor, promessas_ouvidas (as afirmações do vendedor sobre o produto), o_que_revelei, "
                      "posicao_atual, proximos_passos.")
            if influenciador:
                campos += (f" E também relatorio_para_chefe: o texto curto (máx. 150 palavras) que você de fato mandaria "
                           f"ao seu {chefe} sobre esta proposta, incluindo sua recomendação.")
        d = f"""<conversa_recente>
{recentes}
</conversa_recente>

<seu_estado_atual>
{self.estado}
</seu_estado_atual>

<fim_da_ligacao>
A ligação terminou. Motivo: {motivo}.
Escreva suas anotações pós-call, como faria no fim do dia. Seja factual: registre só o que foi dito ou o que você concluiu, e marque suposições como suposições.
</fim_da_ligacao>

{campos}"""
        bruto = await self.llm.chamar(sistema=[self.a, self.b], usuario=[resumo, d], temperatura=0.3,
                                      max_tokens=CFG.get("custo", {}).get("notas_max_tokens", 700), componente=f"notas_{self.lado}",
                                      jornada_id=self.jornada_id, call_id=call_id)
        return extrair_bloco(bruto, "yaml") or bruto
