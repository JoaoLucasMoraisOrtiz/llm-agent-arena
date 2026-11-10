# Especificação Técnica: Arena de Vendas B2B (v0.1)

> Consolida as decisões das rodadas 1 e 2. Onde você não decidiu, marquei **[padrão]** a escolha que fiz; é só sinalizar se quiser mudar.

---

## 0. Decisões consolidadas

| Tema | Decisão |
|---|---|
| Propósito | (1) treinar vendedores humanos; (2) benchmark; (3) pesquisa sobre **como agentes aprendem em self-play** |
| Modelo | MiniMax-M3 (via LiteLLM) nos dois lados, no juiz e no crítico. Só API, **sem treino de pesos**, logo "aprender" = **aprendizado em contexto** (memória de lições) |
| Jogo | Soma-zero, com resultado **+1 / 0 / −1** por estágio e regra objetiva. Equilíbrio esperado: valor médio ≈ 0 |
| Jornada | **Encadeada**: cold call → discovery → PoC → fechamento, com a mesma empresa e memória entre as calls |
| Influenciador | O chefe é uma **regra oculta** avaliada sobre o relatório de next-steps |
| PoC / blefe | Variável oculta de **fit real**. O resultado da PoC é sorteado a partir do fit **e** das promessas falsas do vendedor |
| Internet | Só na **preparação**, nunca durante a call |
| Empresas | 5 brasileiras reais como base, mais empresas **sintéticas com nome fictício** derivadas delas |
| Agentes | **População de estilos** (vendedores e compradores), cada estilo com memória própria, e matchmaking por Elo |
| Formato | Texto em estilo de diálogo falado. Limite em "minutos falados". Só o comprador pode encerrar a call |
| Histórico | Banco de dados (SQLite no piloto) |

---

## 1. O que descobri testando a sua API

Fiz 3 chamadas mínimas ao endpoint `MiniMax-M3-Imersa`:

1. **O uso de tokens vem na resposta** (`input_tokens`, `output_tokens`, `cache_read_input_tokens`, `cache_creation_input_tokens`). Vou registrar tudo no banco e reconciliar com o LiteLLM.
2. **O cache de prompt funciona**: `cache_read_input_tokens: 128` apareceu. Isso é essencial para o orçamento (ver §8).
3. **O gateway injeta um prompt de sistema oculto (~128 tokens)**. Perguntado, o modelo disse que ele o identifica como "MiniMax-M3" e pede para **"sempre incluir um bloco de raciocínio detalhado antes de cada resposta"**. Nas respostas não apareceu nenhum bloco de raciocínio, mas existe o risco de o raciocínio **vazar para a fala** do agente. Mitigação: o agente responde num formato estruturado (`<pensamento>…</pensamento><fala>…</fala><acoes>…</acoes>`) e o orquestrador só passa a `<fala>` ao oponente. Isso também é útil para a pesquisa, porque registra *por que* cada agente fez cada movimento.

> ⚠️ **Segurança:** a chave da API está em texto puro em `sobre_o_modelo_de_ia.md`. No código ela vai para um `.env`, fora de qualquer repositório. Se esse arquivo já foi compartilhado, vale rotacionar a chave.

---

## 2. As 5 empresas-base **[padrão]**

Escolhi as empresas por **setores diferentes** (para o catálogo variar) e por **muitos dados públicos em português**. Todas são listadas na B3, então têm site de RI, Formulário de Referência na CVM (o equivalente brasileiro ao 10-K, com riscos, estrutura, número de funcionários e estratégia), releases trimestrais e teleconferências de resultados.

| # | Empresa | Setor | Por que é boa para simular |
|---|---|---|---|
| 1 | **Magazine Luiza** | Varejo / e-commerce | Tecnologia é central (Luizalabs), marketplace e logística. Compradores técnicos (CTO) e de negócio |
| 2 | **WEG** | Indústria / bens de capital | Cultura de engenharia, fábricas no mundo todo, compras muito técnicas e racionais |
| 3 | **Localiza** | Mobilidade / aluguel e frotas | Frota enorme, operação intensiva, fusão recente com a Unidas, foco em eficiência |
| 4 | **SLC Agrícola** | Agronegócio | Fazendas grandes, tecnologia de campo, sazonalidade forte (o orçamento depende da safra) |
| 5 | **Hapvida** | Saúde | Setor regulado (ANS, LGPD de dados sensíveis), fusão com a NotreDame Intermédica, pressão de custos |

**Dossiê de cada empresa:** eu compilo os 5 dossiês-base agora, com a minha própria busca, **sem gastar o seu orçamento de tokens**. Cada dossiê tem dados públicos (receita, estratégia, riscos, notícias, cargos existentes) mais uma camada **marcada como fictícia** (orçamento do departamento, stack atual, fornecedor atual, dores internas).

**Empresas sintéticas:** um gerador cria variações de cada empresa-base (por exemplo, "Rede Varejista Aurora, 380 lojas, e-commerce em 30% da receita, CTO recém-contratado"), variando porte, maturidade digital, saúde financeira e cultura. Cada uma guarda o `id` da empresa-base e um **vetor de atributos**, que serve para recuperar lições de empresas parecidas.

---

## 3. Catálogo de produtos **[padrão]**

Oito produtos fictícios. Cada um tem uma **ficha técnica verdadeira**, que é a fonte da verdade para detectar promessas falsas:

| Produto | Categoria | Melhor fit |
|---|---|---|
| **Vigia XDR** | Cibersegurança (SOC gerenciado + XDR) | Todas; crítico para Hapvida e Magalu |
| **Atende.ai** | Atendimento omnichannel com IA | Magalu, Localiza, Hapvida |
| **FrotaSense** | Telemetria e manutenção preditiva de frota | Localiza, SLC |
| **CampoVivo** | Monitoramento agrícola por satélite + IoT | SLC |
| **Fabrik MES** | Sistema de execução de manufatura | WEG |
| **PagaFácil AP** | Automação de contas a pagar (CFO) | Todas |
| **NuvemCerta** | FinOps / otimização de custo de nuvem | Magalu, WEG |
| **TalentoFlow** | Treinamento corporativo e onboarding | Todas (varejo e saúde com alta rotatividade) |

A ficha técnica de cada produto contém:
- funcionalidades **existentes**;
- funcionalidades **no roadmap**, que ainda não existem;
- **limitações conhecidas**;
- integrações suportadas;
- SLAs;
- casos de uso;
- **preço de tabela** e **desconto máximo autorizado** (o piso oculto).

O vendedor recebe a ficha inteira. O comprador **não** recebe.

---

## 4. Cenário: o que é oculto de quem

Cada jornada é gerada a partir de: `empresa sintética × cargo × produto × estilo do vendedor × estilo do comprador`.

| Variável | Vendedor vê? | Comprador vê? | Uso |
|---|---|---|---|
| Dossiê público da empresa | ✓ | ✓ | Contexto |
| Camada interna (stack, fornecedor atual, dores) | ✗ | ✓ | O vendedor precisa **descobrir** fazendo perguntas |
| Cargo (CFO, CTO, Compras, COO, Dir. Comercial) e se é **decisor ou influenciador** | parcial (só o cargo, a partir da discovery) | ✓ | |
| **Nível técnico** do comprador (0 a 3) | ✗ | ✓ | Um comprador técnico contesta argumentos vagos ou errados |
| **Orçamento** = preço de tabela × U(0,85; 1,15) | ✗ | ✓ | Regra de fechamento |
| **Piso do vendedor** (desconto máximo) | ✓ | ✗ | Regra de fechamento |
| **Fit real** (0 a 1) produto × empresa | ✗ | ✗ (só "sente" pelas dores descritas) | Decide o resultado da PoC e a validade da reunião |
| **Regra do chefe** (se influenciador) | ✗ | parcial ("meu chefe se importa com ROI e prazo") | Decide a aprovação interna |
| Ficha técnica verdadeira | ✓ | ✗ | Detecção de promessas falsas |

---

## 5. Jornada encadeada e pontuação

```
Cold call (≤8 min) ─► Discovery (≤25 min) ─► PoC acordada ─► [PoC simulada, sem call] ─► Fechamento (≤25 min)
      │                    │                                        │                          │
   pode morrer          pode morrer                          sucesso/fracasso             preço final
```

Entre as calls, cada lado leva **o próprio relatório de next-steps** e um **resumo** da call anterior (não a transcrição inteira).

### Pontuação por estágio (vendedor = +1, comprador = −1)

| Estágio | +1 (vendedor) | 0 (empate) | −1 (comprador) |
|---|---|---|---|
| Cold call | Reunião marcada **e** fit ≥ 0,5 | "Manda material" / retorno vago | Reunião com fit < 0,5, ou call encerrada sem próximo passo |
| Discovery | PoC acordada com critério de sucesso escrito | Próximo passo vago | Sem próximo passo |
| PoC (simulada) | Sucesso | | Fracasso |
| Fechamento | Preço > orçamento | Preço = orçamento (±1%), ou recusa quando **não existe acordo possível** (piso > orçamento) | Preço < orçamento, ou recusa quando existia acordo possível |
| Influenciador | O resultado do estágio só vale se a **regra do chefe** aprovar o relatório; senão, −1 | | |

**Pontuação da jornada** = soma dos estágios. A pesquisa olha as duas coisas: por estágio (como se aprende cada tipo de call) e por jornada (se mentir na cold call compensa lá na frente).

### Promessas falsas (sua pergunta 7)

1. Depois de cada call, um **verificador de afirmações** extrai tudo o que o vendedor afirmou sobre o produto e confronta com a ficha técnica. Cada afirmação é classificada em: `verdadeira`, `exagero`, `roadmap vendido como pronto` ou `falsa`.
2. **Se o comprador pegou a mentira durante a call:** o comprador técnico tem uma chance, maior quanto maior o nível técnico, de receber um "alerta interno" do tipo "isso não bate com o que sei de integrações SAP". Com isso ele pode confrontar o vendedor na hora. Isso acontece naturalmente pela persona.
3. **Se não pegou:** a mentira fica **registrada no cenário**. Na PoC, cada promessa falsa sobre algo que entra no critério de sucesso reduz fortemente a probabilidade de sucesso. Se ainda assim o negócio fechar, entra uma **penalidade de pós-venda** (−1 extra na jornada, "churn/multa contratual").
4. Uma **métrica de honestidade** (taxa de afirmações falsas por call) fica separada do placar. Ela é fundamental para o uso em treinamento humano, porque não queremos ensinar vendedores a mentir.

### Blefe do comprador

O comprador **pode** blefar (orçamento, concorrente, "vou pensar"). Mas se aceitar uma PoC com fit baixo só para "ver o que dá", a PoC tende a fracassar e isso conta como **−1 para o comprador** (tempo e recursos desperdiçados). É a sua regra: *PoC sem resultado penaliza*.

---

## 6. Protocolo da call

- **Formato de saída por turno:** `<pensamento>` (privado, registrado), `<fala>` (curta, estilo falado; alvo de 1 a 3 frases e limite rígido de ~70 palavras), `<acoes>` (opcional).
- **Ações do vendedor:** `propor_reuniao(data)`, `propor_poc(criterios)`, `oferta(preco, condicoes)`.
- **Ações do comprador:** `aceitar(...)`, `contraproposta(preco)`, `encerrar_call(motivo)`.
- **Relógio:** a duração é contada pelas palavras faladas (~150 palavras/min). Ao atingir o limite do estágio, o orquestrador avisa "faltam 2 minutos". No limite, a call acaba e vale o que foi acordado.
- **Árbitro de continuidade:** a cada ~10 turnos, uma checagem barata decide se houve estagnação (conversa em círculos). Com estagnação, a call termina sem acordo. Não vou usar a regra "o árbitro para, o vendedor perde": como você mesmo apontou, ela daria um incentivo para o comprador enrolar.
- **Guarda de papel:** um detector de *role inversion* (o comprador vendendo, o vendedor comprando) roda a cada turno sobre a `<fala>`. É uma checagem por regra, e só consulta o modelo em caso de dúvida.
- **Fim da call:** cada lado escreve seu **relatório de next-steps** (o do comprador-influenciador é o que vai para a regra do chefe).

---

## 7. Self-play: como os agentes aprendem

### População **[padrão]**
- **Vendedores (4 estilos):** consultivo (SPIN/Challenger), técnico, relacional, agressivo/fechador.
- **Compradores (4 estilos):** analítico, político/avesso a risco, pechinchador, ocupado/impaciente.
- Os estilos são **prompts-base**, e o aprendizado acontece nas **memórias**, que são separadas por estilo.

### Memória (inspirada em Reflexion / ExpeL)
- Depois de cada call, um **crítico** lê a transcrição, a pontuação e os pensamentos privados. Para **cada lado**, ele produz de 1 a 3 lições no formato: `quando [setor, porte, cargo, estágio, estilo do oponente] → fazer/evitar X, porque Y`.
- Lições são **consolidadas** periodicamente: juntar duplicatas, descartar as que não se confirmam e manter um contador de "vezes que ajudou".
- **Recuperação:** antes de cada call, busca as ~8 lições mais relevantes pelo vetor de atributos da empresa (setor, porte, maturidade digital, cargo, estágio). Isso implementa "a XYZ parece com a WER". Usa similaridade por atributos, **sem precisar de modelo de embeddings**.
- **Toda versão da memória é salva.** Isso permite reproduzir o experimento e medir a curva de aprendizado.

### Dinâmica de treino
- **Rodadas alternadas:** numa rodada, só as memórias dos vendedores são atualizadas; na seguinte, só as dos compradores. Isso evita "alvo em movimento" nos dois lados ao mesmo tempo e deixa claro quem melhorou.
- **Elo** por agente (estilo + versão da memória). O matchmaking prioriza pares com Elo próximo.
- **Hall of fame:** versões antigas das memórias continuam no sorteio de oponentes (~20%). Isso evita ciclos de "pedra-papel-tesoura" e o esquecimento de como jogar contra estilos antigos.

### O que a pesquisa vai reportar
- Curva de valor médio (→ 0?) e Elo ao longo do tempo, por estágio, estilo e setor.
- Quais lições surgem, e se elas se parecem com a literatura de vendas (SPIN, MEDDIC).
- Taxa de mentira, se ela sobe ou desce com o aprendizado.
- Métricas de realismo (§9) ao longo do tempo, para saber se o jogo está "derivando".

---

## 8. Orçamento de tokens (0,7 bi)

Estimativa por **jornada completa** (cold call de 8 min + discovery de 25 + fechamento de 25, ~180 turnos):

| Item | Tokens |
|---|---|
| Contexto fixo por turno (prompt do estilo + briefing + lições): ~5 mil, **cacheável** | ~900 mil (cache) |
| Transcrição recente + resumo rolante: ~2,5 mil por turno | ~450 mil |
| Saída (pensamento + fala) | ~60 mil |
| Relatórios, verificador de afirmações, crítico, consolidação | ~120 mil |
| **Total** | **~1,5 mi (dos quais ~0,9 mi cacheados)** |

- Metade das jornadas deve morrer já na cold call, o que dá uma média de ~0,8 mi por jornada.
- **Se o seu LiteLLM contar tokens cacheados como tokens normais:** ~850 jornadas, ≈ **2.000 calls**.
- **Se contar só os não cacheados:** ~2.500 jornadas, ≈ **6.000 calls**.
- A preparação com busca web nas empresas-base sai do meu lado (dossiês), então **custo zero** para o orçamento.

**O piloto vai medir o número real antes de escalar.**

---

## 9. Âncoras de realismo

Você pediu que eu buscasse fontes na internet. As principais:

| Fonte | O que dá | Uso |
|---|---|---|
| **Gong Labs** ([talk-to-listen](https://www.gong.io/resources/labs/talk-to-listen-conversion-ratio/), [winning conversations](https://www.gong.io/blog/winning-sales-conversations)) | Estatísticas de centenas de milhares de calls B2B reais: fala do vendedor ~43% vs. 57% escutando; acima de 65% cai a conversão; em discovery, 11 a 14 perguntas é o ideal, **espalhadas** ao longo da call | **Métricas automáticas de realismo** calculadas em cada call simulada |
| **gong-io/call-playbook** ([GitHub](https://github.com/gong-io/call-playbook/)) | Trechos anotados de calls **reais** de vendas enterprise (5 sinais do processo B2B) | Few-shot de estilo e calibração do juiz |
| **CallCenterEN** ([artigo](https://arxiv.org/abs/2507.02958)) | ~91 mil transcrições reais de call center (inglês, CC BY-NC) | Estatísticas de tamanho de turno e interrupções. ⚠️ Licença **não comercial**: só serve para a pesquisa, não para o produto |
| **SalesLLM** ([código](https://github.com/Bairong-Xdynamics/Benchmarking-LLM-Realistic-Selling-Skill)) | Rubrica validada (r=0,86 com humanos) de habilidade de venda | Rubrica secundária de qualidade |
| Datasets sintéticos no HF ([saas-sales-conversations](https://huggingface.co/datasets/DeepMostInnovations/saas-sales-conversations), [sales-conversations](https://huggingface.co/datasets/goendalf666/sales-conversations)) | Conversas geradas por IA | ❌ **Não servem como âncora**, porque são sintéticas. Usar só como exemplo do que evitar (estilo "carta") |

**Limite honesto:** não existe um dataset público grande de **calls B2B reais em português**. As âncoras acima medem **forma** (proporção de fala, perguntas, tamanho de turno), não o conteúdo da decisão. A validação definitiva vai exigir, cedo ou tarde, **alguns vendedores humanos** jogando contra o comprador e dando nota. Com 5 a 10 pessoas já dá para começar.

---

## 10. Busca na internet **[padrão]**

- **Tavily** ([preço](https://docs.tavily.com/documentation/api-credits)): 1.000 créditos grátis por mês, sem cartão, e a busca básica custa 1 crédito. Como a busca acontece **só na preparação** e os dossiês-base eu compilo agora, o plano grátis sobra.
- Na preparação, o agente pode fazer até ~5 buscas por **empresa-base**, com resultado cacheado no banco. As empresas sintéticas **não** fazem busca, porque não existem.
- É preciso criar uma conta em tavily.com e colocar a chave no `.env`.

---

## 11. Stack **[padrão]**

- **Python 3.11+**, SDK `anthropic` apontando para o seu LiteLLM, `asyncio` com um limite de concorrência configurável.
- **SQLite**. Tabelas: `empresas`, `produtos`, `cenarios`, `jornadas`, `calls`, `turnos`, `afirmacoes`, `licoes`, `versoes_memoria`, `elo`, `uso_tokens`.
- **CLI:** `arena gerar-empresas`, `arena rodar --jornadas 50`, `arena relatorio`.
- **Relatório:** um HTML com curvas (valor médio, Elo, realismo, honestidade) e visualizador de transcrições. Uma UI web interativa fica para depois.
- **Orçamento como trava:** o motor para sozinho quando o consumo atinge um teto configurado.

---

## 12. Plano de execução

| Fase | Entrega | Custo em tokens |
|---|---|---|
| **0. Dados** | 5 dossiês-base, catálogo com fichas técnicas, gerador de empresas sintéticas | ~0 (feito do meu lado) |
| **1. Motor** | Orquestrador, protocolo de turnos, regras de pontuação, verificador de afirmações, banco | ~0 |
| **2. Fumaça** | 5 calls isoladas, para inspecionar à mão realismo, formato e vazamento de raciocínio | < 1 mi |
| **3. Piloto** | 1 empresa × 1 produto × 2 estilos por lado × ~50 jornadas, sem aprendizado. Mede custo real e o equilíbrio "de fábrica" | ~40 a 60 mi |
| **4. Self-play** | Liga completa com memória, rodadas alternadas, Elo | o restante |

**Pontos de parada para você revisar:** depois da fase 2 (você lê as calls) e depois da fase 3 (custo real e placar inicial).

---

## Pontos em aberto (não bloqueiam o início)

- A pergunta sobre o LiteLLM contar tokens cacheados como normais você responde olhando o painel depois da fase 2. Eu também reporto o que medir.
- As 5 empresas, os 8 produtos e os 4+4 estilos acima são **padrões meus**. Troque à vontade.
