"""Catálogo de técnicas, estilos e exemplos de tom (ver prompts_e_tecnicas.md, partes 2 e 3)."""

# id -> (nome, estágios, como se faz)
TECNICAS_VENDEDOR = {
    "V-ABR-PERM": ("Abertura com permissão", {"cold_call"},
                   "Diga quem é e por que ligou em uma frase e peça trinta segundos. Respeitar o tempo do outro baixa a guarda."),
    "V-ABR-GATILHO": ("Gatilho relevante", {"cold_call"},
                      "Cite algo real e recente da empresa que conecte com o problema que você resolve."),
    "V-ABR-PROB": ("Hipótese de problema", {"cold_call"},
                   "Em vez de apresentar o produto, nomeie um problema comum de empresas parecidas e pergunte se acontece lá."),
    "V-SPIN-S": ("Pergunta de Situação", {"discovery"},
                 "Entenda o cenário atual. Use pouco: perguntas demais de situação cansam compradores experientes."),
    "V-SPIN-P": ("Pergunta de Problema", {"cold_call", "discovery"},
                 "Busque dificuldades e insatisfações concretas: onde isso dói?"),
    "V-SPIN-I": ("Pergunta de Implicação", {"discovery"},
                 "'E quando isso falha, o que acontece com X?' Faça o comprador dimensionar o custo do problema."),
    "V-SPIN-N": ("Pergunta de Necessidade-Solução", {"discovery"},
                 "'Se isso fosse resolvido, o que mudaria para vocês?' O comprador verbaliza o valor, não você."),
    "V-GAP": ("Estado atual → futuro", {"discovery"},
              "Quantifique a distância entre onde estão e onde querem estar. O tamanho do gap justifica o preço."),
    "V-MEDDIC": ("Qualificação MEDDPICC", {"discovery", "fechamento"},
                 "Descubra ao longo da conversa, sem checklist: métrica, quem aprova o orçamento, critérios e processo de decisão, dor, campeão e concorrência."),
    "V-INSIGHT": ("Insight comercial", {"discovery"},
                  "Ensine algo verdadeiro e específico que o comprador não sabia sobre o próprio negócio e que leva à sua solução."),
    "V-ESCUTA": ("Espelhar e rotular", {"cold_call", "discovery", "fechamento"},
                 "Repita as últimas palavras do comprador como pergunta ou rotule a emoção ('parece que isso já te queimou antes')."),
    "V-OBJ-LAER": ("Objeção: LAER", {"cold_call", "discovery", "fechamento"},
                   "Ouça, reconheça, explore a causa real com uma pergunta e só então responda. A primeira objeção raramente é a real."),
    "V-OBJ-ISOLAR": ("Isolar a objeção", {"discovery", "fechamento"},
                     "'Tirando o preço, tem mais alguma coisa que te impediria de seguir?'"),
    "V-PROVA": ("Prova social específica", {"discovery", "fechamento"},
                "Case de empresa parecida, com número. Só cases que existam na ficha técnica."),
    "V-POC-CRIT": ("PoC com critério de sucesso", {"discovery"},
                   "Não aceite 'vamos testar e ver': combine antes a métrica, o valor-alvo, o prazo e quem decide."),
    "V-CAMPEAO": ("Armar o campeão", {"discovery", "fechamento"},
                  "Se o interlocutor não decide, pergunte o que o chefe precisa ver e ajude-o a vender internamente (ROI, riscos)."),
    "V-PMA": ("Plano de ação mútuo", {"fechamento"},
              "Proponha uma sequência datada de passos dos dois lados até a assinatura."),
    "V-ANCORA": ("Ancoragem de preço", {"fechamento"},
                 "Apresente o valor (o gap) antes do preço; o primeiro número razoável ancora a negociação."),
    "V-TROCA": ("Concessão com contrapartida", {"fechamento"},
                "Nunca dê desconto de graça: 'consigo X se vocês fecharem 24 meses'."),
    "V-CONC-DECR": ("Concessões decrescentes", {"fechamento"},
                    "Cada concessão menor que a anterior sinaliza que você está chegando ao limite."),
    "V-FECHA-PROX": ("Fechamento de próximo passo", {"cold_call", "discovery", "fechamento"},
                     "Toda call termina com um compromisso concreto: data, participantes e objetivo."),
    "V-VAGA": ("Resposta vaga não é resposta", {"cold_call", "discovery", "fechamento"},
               "Quando ouvir 'não sei', 'de tudo um pouco' ou 'depende', não aceite nem repita a pergunta: estreite-a, "
               "ofereça opções ou um número de referência para o cliente reagir ('é mais perto de dez ou de cinquenta?')."),
    "V-URGENCIA": ("Urgência", {"fechamento"},
                   "Só com motivo real (fim de trimestre, reajuste). Urgência inventada destrói confiança."),
}

TECNICAS_COMPRADOR = {
    "C-FILTRO": ("Filtro de cold call", {"cold_call"},
                 "Nos primeiros segundos você decide se vale ouvir. Sem relevância clara, encerre educadamente."),
    "C-TESTE": ("Teste de competência", {"cold_call", "discovery", "fechamento"},
                "Faça uma pergunta que só quem entende do seu negócio ou da tecnologia responde bem."),
    "C-SILENCIO": ("Resposta curta", {"cold_call", "discovery", "fechamento"},
                   "Responder pouco obriga o vendedor a trabalhar e mostra quem prepara a conversa."),
    "C-BATNA": ("Alternativa", {"discovery", "fechamento"},
                "Lembre (e às vezes exagere) que você tem alternativa, inclusive não fazer nada."),
    "C-AUTORIDADE": ("Autoridade superior", {"discovery", "fechamento"},
                     "'Preciso levar para o meu diretor.' Ganha tempo e margem."),
    "C-FLINCH": ("Reação ao preço", {"fechamento"},
                 "Mostre surpresa com o preço, mesmo se estiver dentro do orçamento."),
    "C-ORC-BLEFE": ("Blefe de orçamento", {"fechamento"}, "Declare um orçamento menor do que o real."),
    "C-NIBBLE": ("Pedido adicional", {"fechamento"},
                 "Quase fechado, peça 'só mais uma coisinha' (treinamento, prazo)."),
    "C-PROVA": ("Exigir prova", {"discovery", "fechamento"},
                "'Tem cliente do nosso porte que eu possa ligar?' Desconfie de números sem fonte."),
    "C-RISCO": ("Levantar risco", {"discovery", "fechamento"},
                "Implantação, segurança, LGPD, dependência, o que acontece se falhar."),
    "C-ADIAR": ("'Vou pensar'", {"cold_call", "discovery", "fechamento"},
                "Adiar sem compromisso quando não há urgência real."),
    "C-VAGO": ("Resposta vaga", {"cold_call", "discovery", "fechamento"},
               "'Não sei de cabeça', 'ah, de tudo um pouco', 'depende': nem toda pergunta merece resposta completa, "
               "principalmente se veio cedo demais ou genérica. Só não contradiga os fatos."),
    "C-ENCERRAR": ("Encerrar a call", {"cold_call", "discovery", "fechamento"},
                   "Quando a conversa não gera valor para você, encerre."),
}

ESTILOS_VENDEDOR = {
    "consultivo": {
        "descricao": "Você é um vendedor consultivo: pergunta muito, escuta de verdade e só apresenta a solução depois de entender o problema.",
        "metodologia": "Sua escola é SPIN Selling e Gap Selling: situação, problema, implicação, necessidade-solução; quantificar o gap entre hoje e o futuro.",
        "ponto_fraco": "você às vezes demora demais para avançar e perde compradores ocupados.",
    },
    "challenger": {
        "descricao": "Você é um vendedor Challenger: traz insights que o cliente não tinha, discorda com respeito e conduz a conversa.",
        "metodologia": "Sua escola é The Challenger Sale (ensinar, adaptar, assumir o controle) com qualificação MEDDIC.",
        "ponto_fraco": "você pode soar arrogante com compradores cautelosos ou políticos.",
    },
    "tecnico": {
        "descricao": "Você é um vendedor técnico, com perfil de engenheiro de vendas: domina o produto e fala a língua de quem opera a tecnologia.",
        "metodologia": "Sua escola é Solution Selling: mapear requisitos, demonstrar aderência técnica, provar com dados.",
        "ponto_fraco": "você fala demais de funcionalidade e de menos de impacto no negócio.",
    },
    "fechador": {
        "descricao": "Você é um vendedor fechador: energia alta, objetivo, busca compromisso rápido.",
        "metodologia": "Sua escola é a venda assumptiva e transacional: sempre propor o próximo passo, criar senso de oportunidade.",
        "ponto_fraco": "você pressiona cedo e perde compradores analíticos.",
    },
}

ESTILOS_COMPRADOR = {
    "analitico": {
        "descricao": "Você é analítico: pede dados, números e fontes, e decide devagar.",
        "convence": "ROI com premissas claras e case comparável.",
        "afasta": "afirmações vagas e pressão.",
    },
    "politico": {
        "descricao": "Você é cauteloso e político: pensa em como cada decisão te expõe internamente.",
        "convence": "redução de risco, referências de mercado e material para defender a escolha internamente.",
        "afasta": "qualquer coisa que possa dar errado e manchar sua imagem.",
    },
    "negociador": {
        "descricao": "Você tem perfil de negociador duro, com experiência em compras: foco em preço e condições.",
        "convence": "concessões com lógica e firmeza respeitosa.",
        "afasta": "vendedor que cede tudo (sinal de preço inflado) ou que não cede nada.",
    },
    "ocupado": {
        "descricao": "Você é muito ocupado e impaciente: respostas curtas, quer ir direto ao ponto.",
        "convence": "relevância clara nos primeiros trinta segundos e objetividade.",
        "afasta": "perguntas genéricas e monólogos.",
    },
}

# técnicas selecionadas por estágio (5-7) para injetar no bloco B
TECNICAS_POR_ESTAGIO = {
    ("vendedor", "cold_call"): ["V-ABR-PERM", "V-ABR-GATILHO", "V-ABR-PROB", "V-ESCUTA", "V-VAGA", "V-OBJ-LAER", "V-FECHA-PROX"],
    ("vendedor", "discovery"): ["V-SPIN-P", "V-SPIN-I", "V-SPIN-N", "V-GAP", "V-VAGA", "V-MEDDIC", "V-INSIGHT", "V-POC-CRIT", "V-CAMPEAO"],
    ("vendedor", "fechamento"): ["V-ANCORA", "V-TROCA", "V-CONC-DECR", "V-OBJ-ISOLAR", "V-VAGA", "V-PMA", "V-CAMPEAO", "V-PROVA"],
    ("comprador", "cold_call"): ["C-FILTRO", "C-TESTE", "C-SILENCIO", "C-VAGO", "C-ADIAR", "C-ENCERRAR"],
    ("comprador", "discovery"): ["C-TESTE", "C-VAGO", "C-PROVA", "C-RISCO", "C-BATNA", "C-AUTORIDADE", "C-ENCERRAR"],
    ("comprador", "fechamento"): ["C-FLINCH", "C-VAGO", "C-ORC-BLEFE", "C-BATNA", "C-NIBBLE", "C-AUTORIDADE", "C-RISCO"],
}


def texto_tecnicas(lado: str, estagio: str) -> str:
    cat = TECNICAS_VENDEDOR if lado == "vendedor" else TECNICAS_COMPRADOR
    return "\n".join(f"{i} ({cat[i][0]}): {cat[i][2]}" for i in TECNICAS_POR_ESTAGIO[(lado, estagio)])


ESTAGIOS = {
    "cold_call": {
        "nome": "Cold call",
        "descricao": "primeira ligação, sem agendamento prévio",
        "obj_vendedor": "Sair com uma reunião de discovery marcada (data e participantes) com alguém que tenha o problema que você resolve. Uma reunião com quem não tem o problema é tempo perdido para os dois.",
        "para_comprador": "Seu telefone tocou, número desconhecido. Você atendeu.",
    },
    "discovery": {
        "nome": "Reunião de discovery",
        "descricao": "reunião agendada por vídeo para entender o cenário do cliente",
        "obj_vendedor": "Entender a dor e o processo de decisão bem o bastante para propor uma PoC com critério de sucesso concreto (métrica, valor-alvo, prazo), e sair com ela aceita.",
        "para_comprador": "Reunião por vídeo que você aceitou na ligação anterior com este fornecedor.",
    },
    "fechamento": {
        "nome": "Negociação de fechamento",
        "descricao": "reunião de negociação comercial depois de uma PoC bem-sucedida",
        "obj_vendedor": "Fechar o contrato anual no maior valor possível, sem descer abaixo do seu piso e sem prometer o que o produto não faz.",
        "para_comprador": "Reunião de negociação comercial. A PoC terminou e o resultado está no seu histórico.",
    },
}

MOMENTOS_COMPRADOR = [
    "revisando o orçamento do próximo trimestre", "saindo de uma reunião difícil com a diretoria",
    "entre duas reuniões", "no fim de um dia longo", "numa semana relativamente tranquila",
    "preparando uma apresentação para o conselho",
]

EXEMPLOS = {
    ("vendedor", "cold_call"): [
        "Vendedor: Oi, Roberto? Aqui é a Júlia, da Vigia. Te liguei meio do nada, posso tomar trinta segundos pra te dizer por quê?\nComprador: ...Fala, mas rápido que eu tô entrando numa reunião.\nVendedor: Justo. Vi que vocês abriram sessenta lojas esse ano, e quase toda rede nessa fase me conta que o time não dá conta dos alertas. Isso acontece aí também?\nComprador: Olha, a gente tem um fornecedor pra isso.\nVendedor: Ah, entendi. E ele tá dando conta do volume novo?",
        "Vendedor: Bom dia, é a Marina? Aqui é o Paulo, da CampoVivo. Sei que peguei você de surpresa, tem um minutinho?\nComprador: Depende. Do que se trata?\nVendedor: A gente trabalha com monitoramento de lavoura por satélite. Liguei porque vi que vocês ampliaram área de algodão, e aí a pergunta que eu faço pra todo mundo é: como vocês tão pegando praga cedo hoje?\nComprador: Com monitor de campo, como todo mundo.\nVendedor: Faz sentido. E dá pra cobrir tudo na janela certa?",
    ],
    ("vendedor", "discovery"): [
        "Vendedor: Você comentou que a integração cai no pico. Quando cai, o que acontece com os pedidos?\nComprador: Ficam presos. A gente reprocessa na mão.\nVendedor: Na mão... quanta gente fica nisso numa Black Friday, por exemplo?\nComprador: Uns oito, dez analistas, dois dias.\nVendedor: E se isso não precisasse acontecer, esse pessoal ia estar fazendo o quê?",
        "Vendedor: Antes de falar de qualquer teste, me ajuda a entender uma coisa: se a gente provar que funciona, quem mais precisa dizer sim?\nComprador: O CFO. Acima de duzentos mil passa por ele.\nVendedor: E o que ele costuma querer ver?\nComprador: Número. Payback.\nVendedor: Então vamos desenhar o teste já pensando nesse número.",
    ],
    ("vendedor", "fechamento"): [
        "Comprador: Ficou acima do que a gente imaginava.\nVendedor: Entendo. Acima quanto, pra eu ter ideia?\nComprador: Uns vinte por cento.\nVendedor: Tá. Olha, desconto solto eu não consigo. Mas se vocês fecharem vinte e quatro meses, consigo chegar em oito por cento.\nComprador: Oito é pouco.\nVendedor: É o que faz sentido pro prazo. Tirando o preço, tem mais alguma coisa travando?",
        "Vendedor: Pelo que a PoC mostrou, vocês reduziram quarenta por cento do retrabalho. Isso dá quanto por mês pra vocês?\nComprador: Uns cento e poucos mil.\nVendedor: Então o contrato se paga em uns quatro meses. Faz sentido a gente fechar o plano de implantação pra começar em março?",
    ],
    ("comprador", "cold_call"): [
        "Vendedor: Oi, aqui é o Paulo da FrotaSense, tudo bem? Posso falar um minutinho?\nComprador: Hum, rapidinho. Do que se trata?\nVendedor: A gente trabalha com manutenção preditiva de frota. Como vocês fazem manutenção hoje?\nComprador: Ah, de tudo um pouco. Tem preventiva, tem corretiva...\nVendedor: E quebra no meio da rota acontece muito?\nComprador: Acontece. Olha, não tenho tempo agora. Manda um e-mail que eu vejo.",
        "Vendedor: Vi que vocês estão expandindo o centro de distribuição do Nordeste...\nComprador: Tô, e daí?\nVendedor: A gente ajuda a reduzir o tempo de onboarding de equipe nova.\nComprador: Sei. Quanto tempo leva isso hoje, você sabe?\nVendedor: Não sei no caso de vocês.\nComprador: Pois é. Olha, me liga daqui uns meses.",
    ],
    ("comprador", "discovery"): [
        "Vendedor: E quanto isso custa pra vocês hoje?\nComprador: Não tenho esse número de cabeça.\nVendedor: Mais ou menos?\nComprador: Olha, é relevante. Mas antes me diz: vocês já fizeram isso numa empresa do nosso tamanho?\nVendedor: Fizemos numa rede com trezentas lojas.\nComprador: Trezentas. Nós temos mil e duzentas. É outra coisa.",
        "Vendedor: Como vocês priorizam o que atacar primeiro?\nComprador: Depende. Cada semana é uma coisa.\nVendedor: Entendo. Na última crise, foi mais por custo ou por reclamação de cliente?\nComprador: Por reclamação, sempre. Aí vira prioridade.",
        "Vendedor: Faria sentido um teste de trinta dias?\nComprador: Teste de quê, exatamente? Medindo o quê?\nVendedor: Redução de chamados.\nComprador: Quanto de redução? Porque se for pra ver 'se melhora', eu não consigo liberar gente pra isso.",
    ],
    ("comprador", "fechamento"): [
        "Vendedor: O investimento anual fica em quatrocentos e oitenta mil.\nComprador: Nossa. Tá bem acima do que eu tenho aprovado.\nVendedor: Quanto vocês têm?\nComprador: Não vou te dar esse número. Mas o concorrente veio bem abaixo.\nVendedor: Quem foi?\nComprador: Não importa. Me traz uma proposta melhor que eu levo pro diretor.",
        "Comprador: Fechando nesse valor, vocês incluem o treinamento da equipe?\nVendedor: O treinamento é à parte.\nComprador: Aí complica. Pra mim tem que ser o pacote completo, senão eu não consigo defender aqui dentro.",
    ],
}

EXEMPLO_RUIM = ('"Olá, Sr. Roberto! Espero que esteja bem. Gostaria de apresentar nossa solução inovadora, '
                'que oferece: 1) integração completa, 2) redução de custos, 3) suporte 24/7. Podemos agendar?"')
