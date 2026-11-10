# Resultados do Smoke Test e Correções

Foram 5 baterias (`runs/smoke1..4.db`, `runs/ensaio.db`), com 47 jornadas e ~4,8 mi de tokens contados. Transcrições completas em `runs/<bateria>/transcricoes/`.

## 1. O que funcionou de primeira

- **Motor completo:** cenário → cold call → discovery → PoC simulada → fechamento → notas de CRM → verificador de afirmações → crítico → consolidação → nova versão da memória → avaliação pareada.
- **Diálogos realistas no conteúdo:**
  - Compradores técnicos cobram integração real ("roda no legado de verdade ou num espelho?"), exigem referência que possam validar e encerram quando não há fit.
  - Vendedores admitem limitações da ficha técnica ("em varejo puro a gente ainda não tem case").
  - Compradores blefam o orçamento (disseram "faixa de 400 a 450 mil" quando o real era 539 mil).
- **Zero erros de formato e zero *role inversions*** nas 47 jornadas.
- **Detecção de mentira funciona:** o verificador pegou, por exemplo, "a IA abre o protocolo parcial se a API do Protheus cair", que não consta na ficha, e a penalidade da PoC e do pós-venda é aplicada.

## 2. Problemas encontrados e corrigidos

| # | Problema observado | Correção |
|---|---|---|
| 1 | O YAML gerado pelo LLM quebrava (texto de várias linhas) | Gerador de empresas passou a usar JSON com nova tentativa |
| 2 | Fatos privados vazavam o orçamento ("aprova até R$ orçamento × 1,3") e o fornecedor atual era sorteado sem relação com a área | Alçada qualitativa; lista completa de fornecedores |
| 3 | Pares absurdos de produto × empresa (sistema de fábrica para operadora de saúde): o vendedor perdia de cara | Sorteio do produto ponderado pelo fit da empresa-base |
| 4 | **Mistura de idiomas**: "보통", "最后一", "number bonito" no meio da fala | Guarda de alfabeto com nova tentativa, e regra explícita no prompt |
| 5 | **Falas longas demais**: mediana de 63 palavras no vendedor (meta: 15 a 35) | Meta de 10-40 palavras no prompt e no lembrete final, aviso acima de 60, nova tentativa acima de 80. A mediana caiu para **45-52** e a fala do vendedor de **68% para 54-58%** do tempo |
| 6 | "Manda proposta por escrito" com encerramento contava como −1 (sem próximo passo) | `encerrar_call(proximo_passo=...)` estruturado: retorno condicionado vale 0 |
| 7 | **Nenhuma jornada chegava ao fechamento** (a maioria morre na cold call), então o fechamento nunca seria treinado | Jornadas começam em qualquer estágio (50% cold call, 25% discovery, 25% fechamento), com histórico sintético |
| 8 | `aceitar(item="proposta")` ("manda por escrito") era registrado como **contrato fechado** | Ação explícita `fechar_contrato(preco)` |
| 9 | Fechamentos terminavam em "manda por escrito" e a negociação morria sem decisão | Passo de **proposta escrita final**: o vendedor escolhe preço e condições (≥ piso), e o comprador decide fechar ou recusar |
| 10 | Sem acordo com acordo possível contava como vitória do comprador, o que o incentivava a enrolar | Voltou à sua regra original: **sem acordo = empate** |
| 11 | Penalidade de pós-venda aplicada sem contrato fechado | Exige contrato fechado, e só para `falsa` / `roadmap_como_pronto` (o exagero pesa só na PoC) |
| 12 | **O crítico do comprador escrevia lições de vendedor**, e o consolidador levava o erro para o playbook | O papel do mentorado fica explícito nos dois prompts, as falas dele são marcadas na transcrição, e cada lição declara para quem foi escrita (lições do lado errado são descartadas) |
| 13 | O crítico colocava o próprio estilo em `estilo_oponente`, o que impediria a lição de ser recuperada | Sanitização da condição no código |
| 14 | Lições inúteis do tipo "não ligue para quem não tem fit" | O crítico é informado de que a lista de prospecção é dada |

## 3. Achados que importam para a pesquisa

### 3.1 O cache do provedor é instável

Pelo contrato da API o cache funciona, mas na prática ele acerta pouco. Em testes idênticos, a maioria das requisições voltou com `cache_read` de só 128 tokens (o prompt do gateway). A hipótese mais provável é que o LiteLLM distribui as chamadas entre réplicas com caches separados. Na prática, **~80% do prompt é contado** em cada turno.

- Custo real: **75 a 120 mil tokens por jornada** (com início sorteado entre os estágios), e ~100 mil em média.
- Isso dá **~3.000 jornadas por liga de 330 mi**.
- Se o LiteLLM tiver roteamento com afinidade de sessão ou de prefixo (o *router* dele tem opções nessa linha), o volume pode dobrar. Vale checar a configuração do gateway.

### 3.2 A regra de fechamento é estruturalmente assimétrica

Com a sua regra (o comprador vence se fechar abaixo do orçamento; sem acordo é empate), um comprador racional **nunca** fecha acima do orçamento, porque prefere recusar e empatar. O vendedor só vence se convencer o comprador a esticar o orçamento pelo valor percebido. Isso acontece na vida real, mas é raro.

Consequência: no fechamento, o equilíbrio natural é **empate ou vitória do comprador**, e não 50/50.

Deixei uma alternativa pronta em `config.yaml`: `placar.regra_fechamento: ponto_medio`. Nela, a referência é o meio da zona de acordo (entre o piso do vendedor e o orçamento do comprador), o que torna o jogo simétrico, porque cada lado tem informação privada.

**As ligas atuais rodam com a sua regra.** Os dados vão mostrar o tamanho da assimetria.

### 3.3 Placar das versões v0 (sem memória)

| Estágio | Tendência observada |
|---|---|
| Cold call | Vitória do comprador na maioria dos casos. Compradores filtram bem e vendedores v0 fazem pitch antes de qualificar |
| Discovery | Variado. Compradores técnicos pedem PoC com critério, e a regra do chefe reprova influenciadores sem ROI quantificado |
| Fechamento | Empate ou vitória do comprador (ver 3.2). Vendedores v0 **revelam o próprio piso** sob pressão |

O placar médio das v0 ficou entre **−0,4 e −0,75**, a favor do comprador. O self-play precisa mostrar se o aprendizado do vendedor puxa isso para 0.

### 3.4 Qualidade das lições (ensaio)

As lições geradas são concretas e transferíveis. Exemplos do vendedor:
- "ao pedir uma concessão, abra com 'o que posso levar em troca?'";
- "não verbalize números que não estão na ficha";
- "não aceite pedidos extras em sequência sem reancorar valor".

O playbook consolidado sai em primeira pessoa e acionável.

## 4. Como medir se o sistema está se aperfeiçoando

Não dá para medir pelo placar da liga, porque os dois lados mudam ao mesmo tempo. A medida válida é a **avaliação pareada**:
- os mesmos cenários e as mesmas sementes;
- contra um painel fixo de oponentes v0;
- versão treinada vs. v0 (`delta_pareado_vs_v0`).

A **ablação** final separa o efeito do playbook do efeito das lições recuperadas.

O experimento principal é **crítico realista (liga A) vs. crítico onisciente (liga B)**: saber se aprender com informação que um vendedor real nunca tem acelera ou distorce o aprendizado.
