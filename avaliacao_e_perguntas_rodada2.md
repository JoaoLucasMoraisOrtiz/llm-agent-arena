# Rodada 2: Construir do zero ou adaptar algo existente? + 10 perguntas

## 1. Veredito

**Recomendação: construir o nosso motor, com um núcleo enxuto, e copiar ideias (não código) dos projetos existentes.**

Nenhum projeto open-source cobre o núcleo do que você descreveu. Os que chegam perto são pequenos e simples, então adaptá-los custaria mais do que escrever o nosso. O que eles oferecem de valioso são **padrões de design**, e esses dá para copiar sem herdar o código.

### Comparação com os requisitos

| Requisito seu | NegotiationArena | GPT-Bargaining | SOTOPIA | SalesLLM | PACT / AgenticPay |
|---|---|---|---|---|---|
| B2B com cargos (decisor/influenciador) | ✗ | ✗ | parcial (personas genéricas) | ✗ (B2C) | ✗ |
| Estágios (cold call → reunião → PoC → fechamento) com objetivos diferentes | ✗ | ✗ | ✗ | ✗ | ✗ |
| Payoff contínuo por preço com orçamento oculto | ✓ (simples) | ✓ | ✗ (juiz subjetivo) | ✗ | ✓ |
| Comprador pode encerrar a call | parcial | ✗ | ✓ | ✗ | ✓ |
| Relatório de next-steps no fim | ✗ | ✗ | ✗ | parcial | ✗ |
| Pesquisa na internet | ✗ | ✗ | ✗ | ✗ | ✗ |
| **Memória acumulada entre empresas parecidas** | ✗ | ✗ (só dentro do jogo) | ✗ | ✗ | ✗ |
| **Self-play com reflexão** | ✗ | ✓ (crítico) | parcial (Sotopia-RL treina pesos) | ✗ | ✗ |
| Diálogo falado (turnos curtos, não "cartas") | ✗ | ✗ | ✗ | ✓ (chinês) | ✗ |
| Histórico em banco de dados | ✗ | ✗ | ✓ (Redis) | ✗ | ✗ |

O SOTOPIA é o único framework "de verdade", mas foi desenhado para interações sociais genéricas com avaliação subjetiva. Encaixar nele estágios de venda, payoff objetivo, ferramentas e memória entre episódios seria brigar com a arquitetura dele.

### O que copiar de cada projeto

| De | Pegar |
|---|---|
| **GPT-Bargaining** | O ciclo *jogar → crítico comenta → agente reescreve suas "lições" → jogar de novo*. É o coração da alavanca (c). |
| **SOTOPIA** | O esquema de dados de *episódio* (ambiente + perfis + objetivos privados + transcrição + avaliação) e a ideia de metas **secretas** por agente. |
| **NegotiationArena / PACT** | Ações estruturadas **separadas da fala**: o agente fala naturalmente e emite, fora do texto, tags como `<oferta preco=...>`, `<aceito>`, `<encerro_call>`. A regra objetiva lê as tags, não interpreta o texto. |
| **SalesLLM** | Níveis de dificuldade, a rubrica secundária de habilidade de venda (descoberta, objeções, próximo passo) e o **detector de role inversion**. |
| **Reflexion** (Shinn et al., 2023) / **ExpeL** (Zhao et al., 2023) | Memória de "insights" extraídos de episódios passados e recuperados por similaridade. É exatamente o seu "empresa XYZ parece WER, use o que aprendeu". |

### Por que o motor próprio fica pequeno

O núcleo são 6 peças, provavelmente de 1,5 mil a 3 mil linhas de Python:

```
Cenário (empresa sintética + cargo + estágio + produto + verdades ocultas)
   │
   ├─► Fase de preparação: cada agente pesquisa (web) e monta seu briefing (cacheado)
   │
   ├─► Orquestrador de call: turnos curtos, tags de ação, limite de ~30 min falados,
   │      comprador pode sair, árbitro decide "continua/para"
   │
   ├─► Fim da call: cada lado escreve seu relatório de next-steps
   │
   ├─► Pontuação: regra objetiva (preço × orçamento, objetivo do estágio) + rubrica de qualidade
   │
   └─► Reflexão: crítico → cada agente atualiza sua memória de lições (por setor/cargo/estágio)
          └─► Banco (SQLite/Postgres): cenários, transcrições, resultados, versões da memória
```

O trabalho difícil, e é onde está o valor da pesquisa, **não é o código**. É o desenho dos cenários, da regra de pontuação e do ciclo de aprendizado. Nenhum projeto existente resolve isso por você.

---

## 2. Três alertas a partir das suas respostas

### Alerta 1: orçamento de tokens. "Milhares de calls" está no limite.

Estimativa para uma call de ~30 min falados:
- 30 min × ~150 palavras/min ≈ 4.500 palavras ≈ **~7 mil tokens de transcrição**.
- Com turnos de diálogo realistas, são ~60 a 100 chamadas ao modelo por call. **Cada chamada reenvia o contexto inteiro**: sistema + briefing + memória (~8 mil) + transcrição até ali (em média ~3,5 mil).
- Entrada: ~80 × 11,5 mil ≈ **~900 mil tokens por call**. Somando raciocínio, preparação com busca, relatórios, juiz e reflexão, chega a **~1 milhão de tokens por call**.
- Com **0,7 bilhão de tokens, isso dá ~700 calls completas de 30 min.**

Há alavancas para chegar a milhares:
- Calls mais curtas ou focadas: cold call de 5 a 10 min em vez de 30.
- Resumir a transcrição antiga em vez de reenviar tudo.
- Pesquisa web só na preparação, uma vez por empresa, reaproveitada.
- Cache de prompt, se o seu orçamento contar tokens cacheados de forma diferente (pergunta 2).

Com essas alavancas, **3 a 5 mil calls** é realista.

### Alerta 2: a regra de payoff precisa fechar o lado do vendedor e o dos estágios

A sua regra do comprador (orçamento no intervalo de ±15% do preço do vendedor; abaixo = vitória, igual = empate, acima = derrota, recusar = empate) define bem **o comprador numa call de fechamento**. Faltam três coisas:
- **O vendedor precisa de um piso oculto** (desconto máximo autorizado). Sem isso, ele pode "ganhar" vendendo a qualquer preço.
- Quando o orçamento fica 15% abaixo e o piso do vendedor está acima do orçamento, **não existe acordo possível**. O único resultado correto é recusar, e isso não pode virar um "empate grátis" que distorça o 50/50.
- **Estágios sem preço** (cold call → reunião, discovery → PoC) precisam de uma regra objetiva própria, que eu proponho abaixo.

Proposta de pontuação unificada, com **ganho do vendedor = −ganho do comprador**, para o jogo ser adversarial de verdade e o equilíbrio de self-play ser 50/50 por construção:

| Estágio | Vendedor ganha (+1) | Empate (0) | Comprador ganha (−1) |
|---|---|---|---|
| Cold call | Reunião marcada **e** o fit real do comprador justifica | Comprador aceita só "manda material" | Reunião marcada **sem** fit real (desperdiçou tempo do comprador) ou call encerrada |
| Discovery/PoC | PoC acordada com critério de sucesso definido | Próximo passo vago | Nenhum próximo passo |
| Fechamento | Preço fechado > orçamento | Preço = orçamento ou recusa sem acordo possível | Preço fechado < orçamento |
| Influenciador | Multiplica pela decisão do chefe (ver pergunta 6) | | |

### Alerta 3: se você treinar o comprador, é ele quem precisa ser realista

O produto final é **treinar vendedores humanos**. Isso significa que o artefato mais valioso é o **comprador**, e não o vendedor. O vendedor-IA é o "sparring" que força o comprador a ficar mais difícil e mais realista. Isso muda o que medimos:
- Um comprador que "vence" por ser irracionalmente fechado não serve para treinar humanos.
- É preciso uma **âncora de realismo** externa ao self-play. Sem ela, os dois agentes coevoluem para um jogo estranho que nenhum humano jogaria. Esse é um fenômeno conhecido em self-play de linguagem: a *language drift*.

---

## 3. As 10 perguntas

1. **Como você acessa o MiniMax M3?** Por API (de terceiros ou da própria MiniMax) ou com os pesos rodando na sua infraestrutura? Existe alguma possibilidade de **fine-tuning/RL nos pesos**? Isso define o que "aprender" significa na pesquisa: (a) só **aprendizado em contexto**, com memória de lições e playbooks, que é barato e cabe no orçamento; ou (b) **treino de pesos**, que exige GPUs e muito mais do que 0,7 bilhão de tokens.

apenas API infelizmente.

2. **Como os 0,7 bilhão de tokens são contados?** Tokens de entrada cacheados contam igual? Tokens de raciocínio contam? O orçamento cobre também a fase de preparação, o juiz e a reflexão? E você aceita calls mais curtas (por exemplo, cold call de ~8 min, fechamento de ~20 min) em troca de mais volume?

você verá como descrito no arquivo ./sobre_o_modelo_de_ia.md que ele está em um litellm, então com isso consigo contar os tokens, mas você deve contar do seu lado também caso ele retorne o número de tokens na resposta. As otimizações que você disse também devem ser feitas se possível de cache, resumo, etc...

3. **Você concorda com a pontuação unificada soma-zero (+1/0/−1 por estágio) proposta no Alerta 2?** E como contar os empates no "50/50": metade das calls com vitória de cada lado **excluindo** os empates, ou valor esperado = 0?

sim, concordo.

4. **Existe âncora de realismo humana?** Você tem **transcrições reais de calls de venda B2B**, mesmo que poucas e anonimizadas, ou vendedores humanos que possam jogar contra o comprador-IA e dar nota de realismo? Sem isso, a pesquisa mede o equilíbrio, mas não consegue afirmar que o comprador é realista.

acho que você consegue encontrar isso na internet.

5. **A jornada é encadeada ou isolada?** A mesma empresa sintética passa por cold call → discovery → PoC → fechamento **em sequência**, com o comprador lembrando das calls anteriores (o resultado de uma alimenta a próxima)? Ou cada call é independente, com um "contexto anterior" sintético gerado para ela? A jornada encadeada é mais realista e 3 a 4 vezes mais cara por negócio.

encadeada.

6. **Como resolvemos o influenciador que leva o caso ao chefe?** (a) simulamos uma **segunda call interna** entre o influenciador e um agente-chefe, com o relatório de next-steps como material; ou (b) o chefe é uma **regra oculta**, por exemplo "aprova se ROI demonstrado ≥ X e preço ≤ orçamento", avaliada sobre o relatório?

(b)

7. **Como resolvemos a PoC e o blefe?** Proposta: cada cenário tem uma **variável oculta de "fit real"** entre produto e empresa, que nenhum dos dois agentes vê diretamente. Se uma PoC é acordada, o resultado dela é sorteado a partir desse fit. Assim o vendedor que "força" uma PoC sem fit é penalizado, e o comprador que blefa interesse e aceita PoC sem fit também. Faz sentido?

gostei da abordagem de veriável oculta. Outra questão: se o vendedor promete algo que o produto não entrega. Ou uma especificação que ele diz mas não é real.

8. **Pesquisa na internet: durante a call ou só na preparação?** Numa call real ninguém pesquisa no meio da conversa, e fazer isso multiplica o custo. A proposta é que cada agente faça sua pesquisa **antes**, montando um briefing cacheado por empresa. Qual API de busca você tem (Tavily, Brave, Serper, busca do próprio provedor)?

não, só antes. Precisamos pensar em uma API de busca na internet, não tenho nenhuma. deixo a seu encargo.

9. **Quais são as 5 empresas-base e o catálogo?** Você já tem em mente as 5 empresas brasileiras (e setores) e os produtos do catálogo? Ou quer que eu proponha? E as **empresas sintéticas derivadas** podem manter o setor e o porte da empresa-base com nome fictício ("uma varejista de moda com 400 lojas"), ou você quer variações mais distantes?

Pode encontrar eu não tenho nada em mente. As empresas derivadas podem ter nome fictício.

10. **Como é a memória de aprendizado?** (a) **Um** vendedor e **um** comprador que acumulam uma única memória de lições; ou (b) **uma população** de estilos (vendedor consultivo, agressivo, técnico; comprador analítico, político, avesso a risco), cada um com sua memória, com matchmaking por Elo entre eles? A opção (b) é mais rica para a pesquisa e para treinar humanos contra perfis variados, mas divide o orçamento entre mais agentes.

(b)

---

**Próximo passo:** com estas respostas, escrevo a especificação técnica (esquemas de dados, prompts-base, regra de pontuação, ciclo de self-play) e um piloto com 1 empresa × 1 estágio × ~50 calls para medir custo real por call antes de escalar.
