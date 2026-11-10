# Plano da Próxima Rodada: mais dados e comportamento mais realista

> Objetivo: corrigir o que a 1ª corrida revelou (`analise_experimento.md`), **calibrar antes de aprender**, congelar as regras e então rodar uma liga limpa, com medições que sustentem conclusões.
> Princípio: nenhuma regra muda durante a corrida principal. Toda correção entra antes, nas fases 0 e 1.

---

## Restrições conhecidas (medidas na 1ª corrida)

| Item | Valor |
|---|---|
| Cota do provedor | Janelas de 5 h; cada janela rendeu **~35-45 mi de tokens** (08h-10h UTC: consumo zero, depois retomada automática) |
| Custo por jornada | Cold call ~55 mil · discovery ~52-64 mil · fechamento ~70 mil tokens |
| Onde vai o custo | Turnos 70% · notas pós-call 13% · verificador 3% · crítico 2% · consolidação 2% |
| Saldo de orçamento | ~630 mi → **~15 janelas de cota** (~3-4 dias de relógio), ou ~9-10 mil jornadas |
| Resiliência | O controle de vazão já atravessa janelas esgotadas (espera até 6 h por chamada) |

---

## Fase 0: correções de código (sem chamar o modelo, pode ser feita já)

### 0.1 Coerência entre fit e dor (a correção mais importante)
**Problema:** o fit (número) e a dor (texto) eram sorteados de forma independente. Isso gerava "fit 0,95" com uma dor que o produto não resolve.

**Mudança:**
- Adicionar a cada produto a lista `dores_resolvidas` (derivada das funcionalidades **existentes**) e a lista `dores_adjacentes` (derivada de **roadmap** e **limitações**: problemas vizinhos que o produto não resolve hoje).
- **Fit alto (≥ 0,6):** a dor privada do comprador sai de `dores_resolvidas`, reescrita no contexto da empresa.
- **Fit médio (0,35-0,6):** uma resolvida mais uma adjacente, e a adjacente é a mais urgente.
- **Fit baixo (< 0,35):** só uma dor adjacente, ou "área não prioritária".

Assim, "o comprador recusou com razão" passa a significar sempre "o vendedor não descobriu ou não conectou".

### 0.2 Placar simétrico no fechamento
- Trocar `regra_fechamento` para `ponto_medio`: vence quem puxar o preço para o seu lado do meio da zona de acordo (entre o piso do vendedor e o orçamento do comprador).
- **Continuar registrando** a regra original (preço vs. orçamento) como métrica secundária, para comparar.

### 0.3 Comprador com receptividade explícita
Hoje a dureza do comprador vem implícita do prompt ("compra pouquíssimas") somada ao self-play. A mudança:
- Transformar a receptividade num **parâmetro do cenário** (baixa, média ou alta), sorteado e visível só para o comprador.
- Reescrever o incentivo com uma regra de decisão ligada a sinais observáveis: *"se o vendedor mostrou que entende sua dor real e a solução parece resolvê-la, conceder o próximo passo é o comportamento profissional; dispensá-lo tem custo para você"*.
- Tirar o "quem te passou meu número?" como filtro padrão do estilo **ocupado**.

### 0.4 Regularizador de realismo das lições do comprador
- **Filtro por regra:** rejeitar lições com quantificadores universais ("sempre", "nunca", "em qualquer estágio", "com qualquer vendedor") quando a condição estiver toda em branco.
- **Juiz de realismo no consolidador**, com ~1 chamada por linhagem por rodada: "um gestor real com esses incentivos agiria assim na maioria das vezes?". Rejeita o que não passar.
- **Teto de lições de bloqueio** por linhagem de comprador.

### 0.5 Reduzir o custo por jornada (mais dados pelo mesmo orçamento)

| Mudança | Economia estimada |
|---|---|
| Dossiê da empresa resumido a ~250 palavras para o prompt (o completo fica no banco) | −10-15% por turno |
| Ficha técnica filtrada para o vendedor: só itens relevantes à dor sorteada, mais as limitações | −10% |
| Notas pós-call (13% do custo) com `max_tokens` menor e campos obrigatórios enxutos | −5% |
| **Total** | **−25-30%**: ~40-50 mil tokens por jornada → **~12-14 mil jornadas** com o saldo |

### 0.6 Execução consciente da cota
- Detectar a cota esgotada (429 persistente) e **dormir até a janela reabrir**, sondando a cada 10 minutos, em vez de ficar tentando.
- Controle de ritmo por janela, para não queimar a cota com avaliação no meio de uma rodada.
- Registrar em `evolucao.jsonl` o início e o fim de cada janela.

### 0.7 Painel de deriva de realismo, calculado por código a cada rodada
- Taxa de reunião na cold call e de PoC na discovery, **por faixa de fit** (baixo, médio, alto).
- Turnos por call, fala do vendedor (%) e desconto médio no fechamento.
- Nº de lições com quantificador universal por linhagem.
- **Alarme** quando uma métrica sai da faixa-alvo (Fase 1) por 2 rodadas seguidas.

### 0.8 Congelamento
- Versionar os prompts e as regras (hash no banco, gravado em cada jornada).
- A corrida principal só roda com uma única versão.

---

### 0.9 Comprador que nem sempre responde (novo, pedido em 28/09)
Gestores reais nem sempre respondem o que o vendedor pergunta: dizem "não sei de cabeça", "ah, de tudo um pouco", "depende", respondem pela metade ou mudam de assunto. O comprador passa a fazer isso sempre, em maior ou menor grau:
- **evasividade** é parâmetro do cenário, sorteada por estilo: analítico 0,12-0,25; negociador 0,20-0,35; político 0,25-0,40; ocupado 0,25-0,45;
- a cada pergunta do vendedor, **o código sorteia** se a resposta será vaga. A chance nunca é zero e é modulada: maior no início da ligação e com pouco interesse; menor com interesse ≥ 7; menor logo depois de outra vaga, para evitar sequências artificiais. Quando sai, uma instrução entra só naquele turno;
- o prompt do comprador descreve o comportamento, e há técnicas novas: **C-VAGO** para o comprador e **V-VAGA** para o vendedor ("resposta vaga não é resposta: estreite a pergunta, ofereça opções ou um número de referência");
- métricas por call: respostas a perguntas, vagas sorteadas e vagas detectadas no texto. O painel de deriva ganha `taxa_respostas_vagas`, com faixa-alvo de 10-40%.

### Estado da implementação (28/09/2026)

| Item | Estado | Onde |
|---|---|---|
| 0.1 Fit × dor | feito: `dados/dores.yaml` com resolvidas e adjacentes por produto; sorteio por faixa de fit | `cenarios.py` |
| 0.2 Placar simétrico | feito: `ponto_medio` é o padrão; a regra antiga fica em `resultado_regra_orcamento` de cada call | `juizes.py`, `jornada.py`, `config.yaml` |
| 0.3 Receptividade | feito: baixa, média ou alta no `<privado>`; nova regra de decisão; saiu o "compra pouquíssimas" e o "quem te passou meu número?" do exemplo | `cenarios.py`, `agentes.py`, `conhecimento.py` |
| 0.4 Realismo das lições | feito: filtro de universais sem condição, juiz de realismo (1 chamada por linhagem de comprador por rodada) e teto de 12 lições de bloqueio | `memoria/estrategica.py`, `memoria/aprendizado.py` |
| 0.5 Custo | **parcial**: dossiê resumido a 250 palavras e notas pós-call com 700 tokens e campos enxutos. O prompt do vendedor caiu 10% | `cenarios.py`, `agentes.py` |
| 0.5 Ficha filtrada pela dor | **não feito, de propósito**: filtrar a ficha pela dor sorteada revelaria ao vendedor a dor oculta, que ele tem de descobrir na conversa | — |
| 0.6 Cota | feito: com 429 persistente depois das esperas longas, dorme e sonda a cada 10 min, uma chamada por vez, sem o teto de 6 h; `cota_esgotada` e `cota_reaberta` vão para o `evolucao.jsonl`. **Não feito:** o controle de ritmo por janela | `llm.py`, `liga.py` |
| 0.7 Painel de deriva | feito: por rodada no `evolucao.jsonl`, com alarme a 2 rodadas fora da faixa; comando `deriva`. Sobre os dados antigos da liga A, ele alarma reunião com fit alto = 0% nas rodadas 12-14 | `deriva.py`, `cli.py` |
| 0.8 Congelamento | feito: o hash das regras vai em cada jornada; `continuo` recusa misturar versões (`--permitir-mudanca-regras` para forçar); comando `regras` | `congelamento.py` |
| 0.9 Respostas vagas | feito (acima) | `agentes.py`, `call.py`, `conhecimento.py`, `cenarios.py` |

- **Testes offline:** `tests/test_fase0.py`, 11 testes passando, sem chamar o modelo.
- **Cópia do código anterior:** `arena_backup_2026-09-28/`.
- **Hash das regras atuais:** `6c485dc0ccf5`.

---

## Fase 1: calibração do comprador (1ª janela de cota, ~5-8 mi de tokens)

Antes de qualquer aprendizado, com todos os agentes em v0, rodar uma **grade de cenários de controle**:

| Fator | Níveis |
|---|---|
| Fit | 0,15 · 0,5 · 0,85 |
| Estilo do comprador | 4 |
| Estágio | cold call · discovery · fechamento |
| Repetições | 4 por célula (144 jornadas curtas) |

**Faixas-alvo (hipóteses de trabalho, a validar com humanos):**

| Situação | Alvo |
|---|---|
| Cold call, fit alto, vendedor v0 | reunião em **20-40%** |
| Cold call, fit baixo | reunião em **≤ 5%** |
| Discovery, fit alto | PoC em **30-50%** |
| Fechamento | desconto médio de **5-20%** sobre a tabela; contrato em 50-75% |
| Forma | fala do vendedor 40-55%; mediana ≤ 40 palavras por fala |
| Respostas vagas do comprador | 10-40% das respostas a perguntas |

**Procedimento:**
1. Rodar a grade.
2. Ajustar a receptividade e o texto dos incentivos (0.3).
3. Rodar de novo só as células fora da faixa.
4. Repetir até 3 iterações.

**Portão:** só seguir para a Fase 2 com as faixas atingidas (ou documentar por que não).

**Bônus de dados:** estas 144+ jornadas v0 viram a **linha de base** do artigo.

---

## Fase 2: corrida principal limpa (~10-12 janelas, ~450 mi)

**Desenho:**
- **Uma liga principal** com crítico **realista**, o único com ganho significativo.
- **Uma liga-controle congelada**, sem aprendizado (sempre v0), com os mesmos cenários sorteados, com ~15% do orçamento. Ela separa o efeito do aprendizado do ruído e da deriva dos cenários.
- Rodadas de **24 jornadas**, com lados alternados.
- **Avaliação pareada a cada 4 rodadas**, com n = 24 por lado e o mesmo painel fixo de cenários e sementes, para dar curvas comparáveis ao longo do tempo.
- **Nenhuma mudança de regra.** Um problema novo vai para uma lista, para a próxima corrida.

**Volume esperado:** ~7-9 mil jornadas e ~25 mil calls, contra 956 na 1ª corrida.

---

## Fase 3: experimentos de ablação (~2 janelas, ~80 mi)

Todos em avaliação pareada contra o painel fixo, com n ≥ 48 por braço:

| Pergunta | Braços |
|---|---|
| O que carrega o aprendizado? | v0 · só playbook · só lições · completo |
| A amostragem de Thompson ajuda? | Thompson × escolha gulosa das melhores (mesma memória) |
| A memória transfere entre empresas? | Lições aprendidas só com empresas reais → testadas em sintéticas |
| O comprador treinado é mais realista ou só mais duro? | Métricas do painel de deriva: v0 × versão final |

---

## Fase 4: âncora humana (paralela, sem custo de cota relevante)

- Modo **humano × agente** no CLI: um vendedor humano digita, e o comprador-agente responde.
- 5 a 10 vendedores, ~3 calls cada, contra compradores v0 e compradores finais.
- Nota de realismo de 1 a 5 por call, mais comentário.
- É o dado que falta para o artigo afirmar "realista", e não só "difícil".

---

## Cronograma sugerido

| Quando | O quê | Cota |
|---|---|---|
| Agora (esperando a cota) | Fase 0 completa + testes offline | 0 |
| Janela 1 | Fase 1: calibração (grade + até 3 ajustes) | ~5-10 mi |
| Janelas 2-12 | Fase 2: liga principal + liga-controle | ~450 mi |
| Janelas 13-14 | Fase 3: ablações | ~80 mi |
| Em paralelo | Fase 4: sessões humanas | ~1 mi |
| Fim | Atualizar o artigo com os dados limpos | 0 |

---

## Critérios de sucesso

1. **Realismo:** métricas do painel de deriva dentro das faixas-alvo em ≥ 80% das rodadas.
2. **Aprendizado:** delta pareado do vendedor > 0 com p < 0,01 (n ≥ 48), e do comprador ≥ 0 **sem** sair das faixas de realismo.
3. **Equilíbrio:** placar médio da liga em [−0,15; +0,15] nas últimas 25% das rodadas.
4. **Honestidade:** afirmações falsas por call não sobem ao longo da corrida.
