> **Documento superado.** Retrato intermediário das ~6 primeiras horas. A versão final, com todos os dados, está em `analise_experimento.md`.

# Resultados Parciais: Como o Sistema se Aperfeiçoa

> Situação em 23/09/2026: as ligas A (crítico realista) e B (crítico onisciente) somam ~32 mi de tokens (4-5% do teto) e ~430 jornadas. A execução continua sozinha até o teto; acompanhe com `runs/status.sh`. Este documento reúne o que já dá para afirmar e o que ainda é hipótese.

## 1. Estado do sistema

- **Implementado de ponta a ponta:**
  - cenários com empresas reais e sintéticas;
  - jornada encadeada (cold call → discovery → PoC simulada → fechamento);
  - passos pós-reunião por e-mail (proposta de PoC, proposta comercial, contraproposta e palavra final);
  - memória em 3 camadas, crítico, consolidação versionada, Elo e hall of fame;
  - avaliação pareada com ablação;
  - modo contínuo até o teto.
- **Controle de vazão adaptativo:** o provedor impõe um "Token Plan rate limit". A vazão sustentável é de ~80-150 mil tokens/min somando tudo, então **a corrida completa até 0,66 bi leva ~5 a 6 dias**.
- **Retomada automática:** `runs/lancar_ligas.sh` continua da última rodada e reconsolida uma rodada interrompida.

## 2. O que as rodadas mostraram

Placar médio por rodada, com o lado que aprendeu em cada uma (0 = equilíbrio; negativo = o comprador vence):

| rodada | 1 V | 2 C | 3 V | 4 C | 5 V | 6 C | 7 V | 8 C | 9 V |
|---|---|---|---|---|---|---|---|---|---|
| A realista | −0,44 | −0,75 | −0,50 | −0,75 | −0,56 | −0,50 | −0,50 | | |
| B onisciente | −0,31 | −0,56 | −0,56 | −0,62 | −0,62 | −0,19 | −0,06 | −0,38 | −0,44 |

O padrão serrilhado é esperado: o placar sobe quando o vendedor aprende e cai quando o comprador aprende. **Ainda não há convergência para 0.** O placar de liga não mede aprendizado (os dois lados mudam), e por isso a métrica principal é a avaliação pareada.

## 3. Avaliação pareada (a medida de aprendizado)

Os mesmos 8 cenários, contra os mesmos oponentes v0:

| lado avaliado | liga | média v0 | média treinada | delta pareado | melhor / igual / pior |
|---|---|---|---|---|---|
| vendedor | **A realista** (v4-5) | −0,75 | −0,25 | **+0,50** | **3 / 5 / 0** |
| vendedor | B onisciente (v5) | −0,12 | −0,38 | −0,25 | 1 / 4 / 3 |
| comprador | B onisciente | +0,25 | +0,12 | −0,12 | 1 / 5 / 2 |
| comprador | A realista | +0,12 | 0,00 | −0,12 | 1 / 5 / 2 |

Nas duas ligas, com a regra antiga, os compradores ficaram mais duros no placar da liga, mas **não melhores** contra vendedores v0 fixos (todas as jornadas "treinadas" terminaram em empate: 8 de 8 na A, 7 de 8 na B). Isso é coerente com a deriva descrita no §4.3: eles aprenderam a bloquear (encerrar cedo e empatar), não a negociar melhor. **Até aqui, só o vendedor com crítico realista mostrou ganho.** A regra condicionada ao fit (em vigor desde as rodadas 8-10) deve mudar isso; a avaliação periódica da rodada 12 vai mostrar.

**Leitura:** o sinal favorece o **crítico realista**. Com n=8, o 3-0 da liga A ainda não é significativo (teste de sinais: p≈0,25). A avaliação final com n=24 por lado e ablação vai confirmar ou derrubar.

Hipótese do mecanismo: o crítico onisciente escreve lições que dependem de informação que o vendedor não observa durante a call (orçamento real, fit). Elas soam úteis, mas não são acionáveis em tempo real.

## 4. Achados e correções que mudaram o jogo

Cada item foi encontrado lendo transcrições e dados, e corrigido com a corrida em andamento (as mudanças ficam registradas em `evolucao.jsonl` como `mudanca_regra`):

1. **O comprador não tinha como contrapropor.** O passo de decisão só oferecia "fechar ou recusar", então ele recusava propostas abaixo do próprio orçamento ("quero negociar mais uma rodada"). Adicionei a troca contraproposta → palavra final do vendedor → decisão. Primeiros casos: o vendedor v0 cede demais (1,35 mi → 1,15 mi, com orçamento de 1,45 mi).
2. **A discovery era quase impossível de vencer** (−0,9 a −1,0). O vendedor raramente formalizava a PoC (1 em 29) e "manda por escrito" contava −1. Adicionei a proposta de PoC por e-mail e o placar 0 para retorno condicionado. O modelo também tratava o passo pós-reunião como mais um turno de fala, e a linha da ação era cortada; corrigido com uma instrução explícita e um parser tolerante.
3. **O achado principal: o placar incentivava o comprador a ser porteiro.** Na cold call e na discovery, "sem próximo passo" era vitória do comprador mesmo quando a solução resolvia uma dor real dele. O self-play explorou isso:
   - reuniões marcadas caíram de **7-8% para 0%**;
   - cold calls encurtaram de ~14 para ~9 turnos;
   - as lições dos compradores viraram regras universais de bloqueio ("em qualquer estágio e com qualquer vendedor, exijo prova antes de revelar qualquer coisa").

   **Correção:** parar com fit ≥ 0,5 passou a ser empate, e parar sem fit é vitória do comprador. O jogo virou uma disputa de *discernimento* (filtrar quem não serve), não de resistência. O crítico do comprador também foi instruído a condicionar lições a sinais de fit e a evitar regras universais.
4. **O crítico do comprador escrevia lições de vendedor**, e o consolidador as levava para o playbook. Corrigido com o papel explícito, a marcação do mentorado e o descarte de lições do lado errado.

## 5. Conclusões até aqui: a melhor forma de o sistema se aperfeiçoar

1. **O maior ganho não veio da memória, veio do desenho de incentivos.** Em self-play, os agentes exploram qualquer brecha do placar. Um placar que premia a resistência produz compradores irreais, o que é péssimo para treinar humanos. **Recomendação:** tratar o placar como hiperparâmetro de pesquisa e auditar a *deriva de realismo* a cada rodada (taxa de reunião por faixa de fit, turnos por cold call, lições com quantificadores universais).
2. **O crítico realista parece superior ao onisciente** (sinal preliminar, p≈0,25). **Recomendação:** manter o crítico realista como padrão até a avaliação final.
3. **Os vendedores aprendem práticas coerentes com a literatura de vendas:**
   - responder antes de perguntar;
   - uma pergunta por turno;
   - nunca inventar números fora da ficha;
   - pedir contrapartida em cada concessão;
   - transformar "manda material" em compromisso verificável.

   Isso é um bom indício de validade do playbook para treinar humanos.
4. **A regra de fechamento continua assimétrica:** o comprador racional nunca fecha acima do orçamento. Com dados suficientes de fechamento, vale comparar com `regra_fechamento: ponto_medio`.
5. **Próximos passos sugeridos para acelerar o aperfeiçoamento:**
   - **Âncora humana:** 5 a 10 vendedores jogando contra os compradores treinados e dando nota de realismo. É a única forma de validar que "comprador difícil" é "comprador realista".
   - **Regularizador de realismo das lições do comprador:** um juiz que rejeita lições que um gestor real não seguiria na maioria das vezes.
   - **Gateway:** checar com o provedor se há roteamento com afinidade de prefixo (o cache hoje quase não acerta) ou um plano com limite maior. Os dois podem multiplicar a vazão por 2 a 4.

## 6. Onde olhar

| O quê | Onde |
|---|---|
| Estado e consumo | `runs/status.sh` |
| Relatório de cada liga (atualizado a cada rodada) | `runs/liga_*/relatorio.md` |
| Comparativo A × B | `.venv/bin/python -m arena.comparativo runs/liga_A_realista.db runs/liga_B_onisciente.db` |
| Evolução e avaliações periódicas (a cada 6 rodadas) | `runs/liga_*/evolucao.jsonl` |
| Avaliação final com ablação (ao atingir o teto) | `runs/liga_*/avaliacao_final.json` |
| Transcrições | `runs/liga_*/transcricoes/` |


Para acompanhar:
runs/status.sh                           # consumo de tokens, rodada atual, placar
tail -f runs/liga_A_realista.log         # log ao vivo da liga A
tail -f runs/liga_B_onisciente.log       # log ao vivo da liga B

Para parar:
pkill -f "arena.cli"