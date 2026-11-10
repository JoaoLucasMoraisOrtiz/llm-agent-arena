# Análise do Experimento: Arena de Vendas B2B

> Experimento interrompido em 23/09/2026, às 12:26 UTC, quando a cota de 5 horas da conta do provedor acabou. As duas ligas estavam em execução havia ~9h40.
> Dados completos em `runs/liga_A_realista.db` e `runs/liga_B_onisciente.db` (SQLite), com relatórios e transcrições em `runs/liga_*/`.

---

## 1. Volume do que foi feito

| | Liga A: crítico realista | Liga B: crítico onisciente | Total |
|---|---|---|---|
| Rodadas completas | 14 (15ª interrompida) | 22 (23ª interrompida) | 36 |
| Jornadas concluídas (liga) | 273 | 423 | 696 |
| Jornadas de avaliação pareada | 93 | 129 | 222 |
| Jornadas interrompidas | 34 | 31 | 65 |
| Calls (conversas) | 382 | 574 | **956** |
| Turnos de fala | 4.347 | 6.402 | **10.749** |
| Palavras faladas | 189 mil | 278 mil | **467 mil** (~52 horas de ligação a 150 palavras/min) |
| Empresas sintéticas geradas | 25 | 35 | 60 (+5 reais) |
| Versões da memória por estilo | v7-v8 | v11 | |
| Lições criadas / ativas no fim | 407 / 204 | 652 / 259 | |
| Tokens contados | 25,2 mi | 38,2 mi | **70,4 mi com os testes (10% do orçamento de 0,7 bi)** |

**Distribuição de calls por estágio:** cold call 434, discovery 247, fechamento 275.

---

## 2. A abordagem, em resumo

1. **Cenário.**
   - Empresa real (Magalu, WEG, Localiza, SLC, Hapvida) ou sintética derivada delas.
   - Cargo do comprador (CTO, CFO, COO, Compras ou Comercial), decisor ou influenciador.
   - Um de 8 produtos fictícios, com ficha técnica verdadeira.
   - **Verdades ocultas** sorteadas por código: fit real, orçamento (±15% da tabela), piso do vendedor e fatos privados com nível de revelação.
2. **Jornada encadeada:** cold call → discovery → PoC simulada (sucesso sorteado pelo fit e penalizado por promessas falsas) → fechamento.
   - Começa em qualquer estágio, com histórico sintético.
   - Depois de cada reunião há passos por e-mail: proposta de PoC, proposta comercial, contraproposta e palavra final.
3. **Os dois agentes (MiniMax-M3) conversam por turnos curtos**, com pensamento privado, estado de crenças, fala e ações formais separados.
4. **Placar objetivo soma-zero** (+1 vendedor / 0 / −1 comprador), calculado por código a partir das ações. Um juiz só verifica afirmações contra a ficha técnica e extrai o relatório para o chefe.
5. **Aprendizado em contexto:**
   - um crítico escreve lições condicionais depois de cada call;
   - no fim da rodada, um consolidador ("sono") gera uma nova versão da memória de cada estilo (4 vendedores × 4 compradores);
   - antes de cada call, as lições são recuperadas por semelhança de atributos (setor, cargo, estágio…) com amostragem de Thompson;
   - rodadas alternadas: numa, os vendedores aprendem; na seguinte, os compradores.
6. **Medida de aprendizado:** avaliação pareada. Nos mesmos cenários, contra os mesmos oponentes da versão inicial (v0), comparam-se a versão treinada e a v0.

---

## 3. O que aprendemos

### 3.1 O vendedor com crítico realista aprendeu, e é o único resultado estatisticamente significativo

Soma das avaliações pareadas (avulsa + periódicas), versão treinada vs. v0:

| Lado | Liga | Melhor | Igual | Pior | Teste de sinais (bicaudal) |
|---|---|---|---|---|---|
| **Vendedor** | **A realista** | **8** | 11 | **1** | **p = 0,04** |
| Vendedor | B onisciente | 6 | 21 | 5 | p = 1,0 |
| Comprador | A realista | 5 | 12 | 3 | p = 0,73 |
| Comprador | B onisciente | 3 | 24 | 5 | p = 0,73 |

**Leitura:**
- **Só o vendedor da liga A melhorou de forma detectável** (delta médio +0,33 a +0,50 por jornada).
- **O crítico onisciente não ajudou.** A hipótese é que ele escreve lições apoiadas em informação que o vendedor não vê durante a call (orçamento real, fit): elas parecem boas, mas não são acionáveis.
- **Os compradores não melhoraram contra vendedores fixos.** Eles ficaram mais duros, mas isso aparece como mais empates, não como mais vitórias.

Ressalvas:
- n pequeno (20-32 pares por linha);
- as avaliações misturam versões diferentes (v4 a v11);
- as regras mudaram durante a corrida (§5).

### 3.2 O que os vendedores aprenderam (conteúdo do playbook)

As lições que sobreviveram à consolidação e à estatística de crédito batem com a literatura de vendas:
- **Honestidade estratégica:** "declaro o gap em uma frase e condiciono a entrega completa a uma troca de contexto".
- **Uma pergunta por turno**, e responder antes de perguntar.
- **Não revelar preço, piso nem referência sem uma troca explícita**, e pedir contrapartida em cada concessão.
- **Transformar "manda material" em compromisso verificável.**
- **Na cold call:** "permissão verbal não é dor", perguntar onde dói em R$ ou horas.

A taxa de **afirmações falsas por call caiu** na liga A (fechamento: 0,47 → 0,19), mas **subiu** na liga B (0,28 → 0,48). É mais um ponto contra o crítico onisciente.

### 3.3 O que os compradores aprenderam, e por que isso é um problema

Os compradores viraram **porteiros muito eficientes**:
- "filtro de relevância em 30 segundos";
- "antes de revelar volume, orçamento ou sistemas, devolvo pergunta de competência";
- encerrar "listando os três sinais de má prospecção".

Algumas lições são realistas para um executivo sênior, mas o conjunto é mais duro do que o mercado real:

| Métrica | Antes | Depois |
|---|---|---|
| Cold calls com fit ≥ 0,5 que viraram reunião, liga A | 2 de 61 (3%) | 0 de 57 |
| Cold calls com fit ≥ 0,5 que viraram reunião, liga B | 5 de 86 (6%) | 0 de 94 |
| Discovery que virou PoC (as duas ligas) | 2-3% | 0-3% |
| Turnos médios por cold call | ~11,5 | ~7,5-9 |

### 3.4 O fechamento é onde o comprador ganha

- **130 contratos fechados em 198 fechamentos** (66%).
- Preço médio de **88% do orçamento do comprador e 87-88% da tabela**. Só 8 de 130 fecharam acima do orçamento.
- O vendedor cede ~12%, e o comprador sempre sai com economia. Pela regra do placar (vence quem fechar abaixo do orçamento), quase todo contrato conta como vitória do comprador.

---

## 4. Por que não chegamos a 50/50

| Fator | Evidência | Efeito |
|---|---|---|
| **1. Regra de fechamento assimétrica** | 122 de 130 contratos abaixo do orçamento | O comprador conhece o orçamento e só fecha abaixo dele. O vendedor só vence se o comprador estourar a verba, o que um comprador racional não faz |
| **2. Dor do cenário desalinhada com o produto** | Fit 0,95 com dor "vistoria por imagem" para um produto de telemetria (FrotaSense); o comprador rejeitou, corretamente | A dor privada é sorteada do tema do produto, mas não é conferida contra as funcionalidades existentes. Um fit "alto" pode ser uma dor que o produto não resolve |
| **3. Comprador-LLM sem calibração** | Reunião em ~0% mesmo com fit alto; comprador "ocupado" desliga no 2º turno por "quem te passou meu número?" | O prompt ("compra pouquíssimas") somado ao self-play empurra para a rejeição. Sem uma âncora humana, não há como saber o ponto certo |
| **4. Brecha de incentivo (corrigida na rodada 8/10)** | Antes da correção, parar sempre dava vitória ao comprador | Gerou a deriva descrita no §3.3; a correção melhorou o placar médio (A: −0,53 → −0,26; B: −0,41 → −0,31) |

---

## 5. Mudanças feitas durante a corrida (os dados antes e depois não são 100% comparáveis)

| Rodada | Mudança |
|---|---|
| 2 | Contraproposta por escrito no fechamento (antes, o comprador só podia fechar ou recusar) |
| 6 | Proposta de PoC por escrito depois da discovery; "retorno condicionado" na discovery passou a valer 0 |
| 8 (A) / 10 (B) | **Placar de cold call e discovery condicionado ao fit** (parar com fit = empate; parar sem fit = vitória do comprador) |
| — | Correções de parser, prompts dos passos por e-mail, consolidador e perspectiva do crítico do comprador (ver `resultados_smoke_test.md`) |

---

## 6. Recomendações para a próxima corrida (quando a cota voltar)

Em ordem de impacto esperado:

1. **Alinhar a dor com o produto no gerador de cenários.** Com fit alto, sortear uma dor que o produto de fato resolve (funcionalidade existente). Com fit baixo, uma dor adjacente que ele não resolve. Hoje o "fit" e a dor são independentes.
2. **Trocar a regra de fechamento para `ponto_medio`**, que já está implementada: vence quem puxar o preço para o seu lado do meio da zona de acordo. O jogo fica simétrico e o 50/50 passa a ser alcançável por construção.
3. **Calibrar o comprador com cenários de controle antes do self-play.** Com fit 0,9 e um vendedor competente, a reunião deve sair em algo como 20-40% dos casos. Com fit 0,1, deve sair em ~0%. Ajustar o prompt do comprador até bater, e só então ligar o aprendizado.
4. **Manter o crítico realista** (é o único com ganho significativo) e **cortar a liga B**, economizando metade do orçamento.
5. **Regularizador de realismo das lições do comprador:** rejeitar lições universais de bloqueio e acompanhar a taxa de reunião por faixa de fit a cada rodada, como alarme de deriva.
6. **Avaliação final com ablação** (playbook vs. lições) na liga A, que não chegou a rodar: `avaliar --lado vendedor --n 24`.
7. **Âncora humana:** 5 a 10 vendedores jogando contra o comprador treinado, para validar se ele é difícil de um jeito realista.

**Custo real observado:** ~90 mil tokens por jornada. O limite do provedor ficou em ~80-150 mil tokens/min, com a cota esgotada depois de ~64 mi em ~9h40. Com o saldo de ~630 mi, dá para rodar mais ~7.000 jornadas, respeitando as janelas de cota.

---

## 7. Onde está cada coisa

| O quê | Onde |
|---|---|
| Relatório de cada liga | `runs/liga_A_realista/relatorio.md`, `runs/liga_B_onisciente/relatorio.md` |
| Comparativo A × B por janela de rodadas | `runs/comparativo.md` |
| 956 transcrições (com pensamentos, ações e afirmações problemáticas) | `runs/liga_*/transcricoes/*.md` |
| Evolução e avaliações periódicas | `runs/liga_*/evolucao.jsonl` |
| Avaliações avulsas | `runs/aval_*.log` |
| Retomar | `runs/lancar_ligas.sh` (continua da última rodada) |
