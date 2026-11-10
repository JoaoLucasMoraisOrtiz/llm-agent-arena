# Simulação de Vendas Agente vs. Agente: Perguntas de Clarificação + Estado da Arte

> Objetivo entendido: dois agentes LLM conversam. O **Comprador** faz o papel de um gestor de uma empresa real (com dados públicos). O **Vendedor** tenta vender um produto relevante para essa empresa. O sistema precisa ser **calibrado para ~50/50**: o vendedor fecha em metade das simulações e o comprador resiste na outra metade.

---

## Parte 1: As 20 perguntas

### A. Propósito e uso
1. **Para que serve o sistema?** (a) treinar vendedores humanos, que em algum momento vão substituir o agente vendedor; (b) fazer benchmark/avaliação de agentes vendedores de IA; (c) gerar dataset sintético de conversas de venda; (d) pesquisa. A resposta muda quase todas as outras decisões.

temos dois motivos centrais: (a) e (b) e (d) são os principais, justamente nessa ordem. A ideia é que eu consiga como objetivo final treinar vendedores humanos. Para isso eu preciso fazer esses benchmarks e avaliações para entender o funcionamento e como conseguir fazer esses modelos se comportarem de forma realista e por isso estamos fazendo (d).

2. **O 50/50 é uma meta de calibração ou uma propriedade de equilíbrio?** Ou seja: você quer que *eu ajuste* parâmetros (dificuldade do comprador, orçamento, objeções) até a taxa de vitória ficar em 50%, ou quer que os dois agentes *aprendam/evoluam* (self-play) e o equilíbrio apareça naturalmente?

self-play e quero aprender como esses agentes aprendem. Esse é o report de pesquisa.

3. **O 50/50 vale no agregado ou por segmento?** Por exemplo: 50% no total, ou 50% por empresa, por produto, por cargo do comprador ou por nível de dificuldade?

a ideia de 50/50 é que é o nível de empate em modelos adversariais. A ideia é que teremos um agente que aprende ao ler sobre o role que ele tem que interpretar, ele consegue ser um vendedor primaz, ou um comprador primaz.

### B. Definição de "ganhar"
4. **O que conta como vitória do vendedor?** Contrato fechado? Um próximo passo concreto (reunião com o decisor, POC, envio de proposta)? Fechar acima de um preço mínimo? Em B2B real, quase nenhuma primeira conversa termina em contrato.

reunião no geral é a win. POC e envio de proposta também podem ser. Na verdade acho que precisamos adicionar mais uma variável: estagio da negociação, para conseguir saber exatamente qual o critério de objetivo: vender o produto em si (é uma conversa de fechamento), conseguir uma primeira reunião (era uma cold-call), conseguir uma poc (é um middle negociation)...

5. **O que conta como vitória do comprador?** Só "não comprar"? Ou também "comprar, mas com desconto grande / condições melhores"? Ou seja: é um jogo binário (venda/não venda) ou uma negociação com payoff contínuo (preço, prazo, escopo)?

Com payoff contínuo. Eu pensei em sempre o comprador ter um budget entre 15% a mais do valor que o vendedor pode oferecer, ou 15% a menos. variando nesse range. então se ele conseguir economizar dinheiro (fechar abaixo do budget) ele teve uma grande vitória. Se ele fechar no budget foi empate, se ele fechar acima, derrota. Se ele não conseguir abaixar o preço e decidir negar o negócio, para não fechar acima do budget, também seria empate.

6. **Quem decide o resultado?** (a) o próprio agente comprador declara; (b) um **terceiro agente juiz** lê a transcrição; (c) uma regra objetiva (por exemplo, preço final ≥ preço de reserva oculto do comprador). A literatura mostra que LLMs no papel de comprador tendem a ceder fácil demais (bajulação), por isso um critério externo costuma ser necessário.

Acho que uma regra objetiva, como eu descrevi em 5 ou talvez um pouco mais elaborada.

7. **O comprador deve ter uma "verdade oculta"?** Por exemplo: orçamento máximo, dor real (de 0 a 10), prioridades concorrentes, fornecedor atual, pessoas que precisam aprovar. Isso cria assimetria de informação, e o vendedor só vence se descobrir essas coisas fazendo perguntas.

Sim, ele tem que estar como que inserido no contexto da empresa: ele tem que saber negar argumentação falha, ele pode ter um perfil técnico que se o vendedor não souber falar tecnicamente ele vai perder a venda. ele tem que ter um formato de negociação real mesmo.

### C. Empresas e personas (lado comprador)
8. **Quais empresas?** Brasileiras (dados na CVM, RI, relatórios de sustentabilidade), americanas (10-K da SEC, earnings calls) ou ambas? Quantas no piloto: 5, 20, 100?

brasileiras, vamos pensar em 5 empresas. mas eu quero que dessas 5 base, geremos várias outras, para que o modelo possa depois ver a empresa XYZ que tem um perfil parecido com a empresa WER que ele já fez uma call, e possa usar os conhecimentos.

9. **Qual o cargo do gestor simulado?** CFO, CIO/CTO, Head de Compras, Diretor Comercial, COO? 
Ele é o decisor final ou um influenciador que precisa "vender internamente"?

vamos pensar nos dois cenários: ele é decisor, ou é influênciador. Isso determina também aquilo que eu disse sobre ter sucesso ou falha no contexto do tipo de call que é. por exemplo, se o cliente influênciador realmente levar para seu chefe e convence-lo a fechar negócio, foi um sucesso, mas se ele sair da call sem levar para o chefe, é uma perda. então no final da call ambos os modelos devem produzir como um relatório de next-steps.

10. **Quanto do contexto da empresa é real e quanto é inventado?** Dados públicos (receita, estratégia, riscos citados no 10-K, notícias recentes) mais detalhes internos plausíveis e fictícios (orçamento do departamento, stack atual, dores específicas)? Existe restrição de usar nomes reais de executivos? A recomendação é **não** simular pessoas reais, só cargos.

isso, simule cargos com toda a informação que tiver disponível online. eu queria também que esses agentes tivessem acesso à internet para poder fazer buscas e pensar.

11. **O agente comprador deve buscar dados em tempo real** (web search, RAG sobre documentos da empresa) ou recebe um "dossiê" pré-compilado e fixo por empresa? Um dossiê fixo é muito mais reprodutível.

sim

### D. Produtos (lado vendedor)
12. **Quem define o produto?** (a) catálogo fixo de produtos fictícios (SaaS de CRM, cibersegurança, consultoria, etc.); (b) um produto gerado automaticamente como "relevante" para cada empresa; (c) produtos reais seus ou de clientes? Se for gerado, quem garante que ele é *de fato* relevante? Isso afeta o equilíbrio: produto irrelevante gera derrota trivial.

pode ser um catalogo fixo, pensado para as empresas que estamos trabalhando.

13. **O vendedor sabe o quê sobre o comprador antes da conversa?** Só o nome da empresa e o cargo (como uma cold call), ou um briefing de pesquisa prévia (como uma discovery call preparada)?

sabe um briefing sobre a empresa em si, não sobre quem vai atender o telefone (se for uma cold-call), se não for cold-call, ele sabe o contexto da conversa anterior. Ele sabe também, de alguma forma, a experiência acumulada dele entre  outras empresas.

### E. Formato da conversa
14. **Qual o formato da interação?** Cold call, reunião de discovery, demo, negociação final? Ou um ciclo completo com várias reuniões? Qual o limite de turnos (por exemplo, 10 a 20 mensagens por lado)?

todos os formatos a ideia é que o modelo converse, por um tempo que em fala fosse no máximo 30min. e ai um arbitro pode avaliar: continuar ou parar. Se parar, ele considera que perdeu. mas acho isso difícil porque o modelo do cliente estará indiretamente tantando resolver logo a reunião. O agente cliente pode escolher deixar a reunião a qualquer momento, finalizando-a, o vendedor não.

15. **Texto ou voz?** Só texto por enquanto, ou você imagina TTS/STT depois (simulação de ligação)?

só texto, depois teremos STT/TTS, mas por enquanto texto, mas as conversas devem ocorrer como ocorreriam em caso de um diálogo. não quero o modelo escrevendo uma carta em cada mensagem. Devemos usar as técnicas de venda de como seria num diálogo/call.

### F. Modelos, custo e tecnologia
16. **Quais modelos?** O mesmo modelo nos dois lados (Claude vs. Claude), ou modelos diferentes (Claude vs. GPT, grande vs. pequeno)? Modelos diferentes introduzem um viés de "força" que também precisa ser calibrado.

é o minimax m3 dos dois lados.

17. **Orçamento e volume:** quantas simulações você quer rodar (100? 10.000?) e qual o custo aceitável por conversa? Isso define se usamos modelos menores para o comprador e para o juiz.

não temos modelos menores... eu quero milhares de calls, não sei um número. temos 0.7B de tokens de orçamento.

18. **Stack e interface:** Python puro com a SDK da Anthropic? Precisa de UI (web para assistir às conversas e ver o dashboard de win-rate) ou basta CLI + logs/JSON? Precisa de banco de dados?

pode ser, sem nenhuma preferência quanto a isso. acho legal ter um banco de dados apenas para guardarmos o histórico


### G. Mecanismo de equilíbrio
19. **Qual alavanca você aceita usar para puxar para 50/50?** Opções:
    - (a) **dificuldade do comprador** (ceticismo, orçamento, número de objeções), ajustada automaticamente por um controlador, como um "staircase" ou Elo;
    - (b) **mix de cenários** (proporção de empresas com fit alto ou baixo com o produto);
    - (c) **self-play com reflexão**: cada lado recebe feedback do juiz e melhora o prompt/memória, e o lado que está ganhando fica "congelado";
    - (d) **Elo/TrueSkill** para personas e vendedores, com matchmaking que emparelha oponentes de força similar.
    Você prefere algo simples (a+b) ou algo de pesquisa (c+d)?
use tudo, principalmente (c), eu quero um motor onde eu tenho que passar o contexto para o vendedor e o contexto para o comprador e ele age.
20. **O comprador deve "trapacear" ou ser sempre racional?** Deve ser permitido usar táticas reais de compradores (blefar orçamento, citar concorrente, "vou pensar", pedir desconto agressivo)? E o vendedor pode usar pressão/urgência artificial? Existem limites éticos ou regras de conduta que o juiz deve penalizar?

pode blefar, mas se ele chegar a fazer uma PoC e não der resultado, ele será penalizado, e isso é obvio.


---

## Parte 2: O que já existe (open-source e artigos)

### Mais próximos da sua ideia

| Projeto | O que faz | Relevância para você |
|---|---|---|
| **SalesLLM / "Sell More, Play Less"** (2026). [artigo](https://arxiv.org/html/2604.07054), [código](https://github.com/Bairong-Xdynamics/Benchmarking-LLM-Realistic-Selling-Skill) | Vendedor LLM vs. simulador de cliente com **5 níveis de dificuldade** (de "easy" a "adversarial"), personas com fatores de decisão. O resultado combina intenção de compra (classificador) com um juiz LLM que avalia 4 dimensões: compromisso verbal, próximo passo, descoberta de informação e tratamento de objeções. | **A referência mais próxima.** Os níveis de dificuldade são exatamente a alavanca para o 50/50. Achado importante: **trocar o simulador de cliente muda totalmente o ranking**, e um comprador GPT-4o "vira vendedor" em 17% das conversas (role inversion). Foco B2C. |
| **Persona-driven User Simulation, SalesBot 2.0** (EMNLP Industry 2025). [artigo](https://aclanthology.org/2025.emnlp-industry.16/) | Um LLM gera personas de cliente (assertividade, precisão da necessidade) que configuram o simulador. Avaliação com juiz LLM e humanos. | Mostra como gerar personas diversas de forma sistemática. |
| **GPT-Bargaining** (Fu et al., 2023). [código](https://github.com/FranxYao/GPT-Bargaining) | Comprador vs. vendedor com preços-alvo diferentes. Um **terceiro LLM crítico** dá feedback e os agentes melhoram por self-play com aprendizado em contexto. | Modelo direto para a alavanca (c): self-play + crítico. |
| **NegotiationArena** (Bianchi et al., ICML 2024). [código](https://github.com/vinid/NegotiationArena), [artigo](https://arxiv.org/abs/2402.05863) | Plataforma LLM vs. LLM com cenários de compra e venda, ultimato e troca de recursos. | Achado: táticas comportamentais (fingir desespero, por exemplo) aumentam o payoff em cerca de 20%. Boa arquitetura de "jogo com regras". |
| **PACT**. [código](https://github.com/lechmazur/pact) | Comprador e vendedor com **valor privado oculto**, 20 rodadas de mensagem + lance. O negócio fecha quando o lance atinge o ask. | Um critério de vitória **objetivo** (sem juiz subjetivo), útil se você quiser um componente de preço. |
| **AgenticPay** (2025). [código](https://github.com/SafeRL-Lab/AgenticPay) | Benchmark multiagente de negociação comprador-vendedor em linguagem natural, com várias rodadas. | Outra base de código para comparar. |

### Frameworks de simulação social/multiagente
- **SOTOPIA** ([artigo](https://arxiv.org/abs/2310.11667), [site](https://sotopia-website.vercel.app/projects/sotopia)): agentes com **objetivos privados** em role-play, avaliados por um juiz LLM em 7 dimensões (goal completion de 0 a 10, benefício financeiro, segredo, etc.). O juiz LLM correlaciona bem com humanos em *goal completion*. O **Sotopia-RL** ([artigo](https://arxiv.org/pdf/2508.03905)) treina com recompensa por turno.
- **"Is this the real life? Is this just fantasy?"** ([artigo](https://arxiv.org/pdf/2403.05020)): alerta que, quando **um único LLM controla os dois lados** ou os agentes conhecem os objetivos um do outro, a simulação parece bem-sucedida demais. **Assimetria de informação é essencial**, o que reforça a pergunta 7.
- **Microsoft TinyTroupe** ([código](https://github.com/microsoft/tinytroupe)): simulação de personas para insights de negócio, com verificação de aderência à persona.
- **Magentic Marketplace** (Microsoft, 2025; [artigo](https://arxiv.org/abs/2510.25779)): mercado de agentes compradores vs. vendedores. Modelos são vulneráveis a táticas de autoridade/prova social e a prompt injection.
- **Awesome LLM Human Simulation** ([lista](https://github.com/Persdre/awesome-llm-human-simulation)): lista curada de artigos.

### Clássicos (datasets humanos de negociação)
- **CraigslistBargain** (He et al., 2018) e **Deal or No Deal** (Lewis et al., 2017, Meta): datasets de negociação humano-humano, úteis para validar realismo.

---

## Parte 3: Lições que já informam o design

1. **LLMs no papel de comprador cedem fácil demais.** Sem contramedidas, o vendedor ganharia bem mais de 50% das vezes. As contramedidas são dar ao comprador restrições ocultas e duras (orçamento, prioridades), ter um juiz externo e usar um "nível de dificuldade" explícito.
2. **O resultado deve ser decidido fora do comprador.** Pode ser por regra objetiva (preço de reserva oculto, critérios de qualificação tipo BANT/MEDDIC atendidos) ou por um juiz separado. Isso evita que o comprador "decida ser gentil".
3. **O 50/50 se consegue com um controlador.** Um ciclo simples funciona: roda N conversas, mede a taxa de vitória, ajusta a dificuldade (estilo *staircase*: vendedor ganhou, próxima persona fica mais difícil; perdeu, fica mais fácil). Isso converge para 50% e ainda produz uma "nota de dificuldade" por empresa/persona, análoga ao Elo.
4. **Cuidado com o role inversion.** Um verificador por turno deve checar se cada agente continua no papel.
5. **Um dossiê por empresa, pré-compilado a partir de fontes públicas** (10-K/CVM, RI, notícias), e não busca em tempo real, dá reprodutibilidade, custo menor e controle sobre o que é real e o que é fictício.

---

**Próximo passo:** com as respostas às 20 perguntas, proponho a arquitetura (dossiê → personas → orquestrador de conversa → juiz → controlador de dificuldade → dashboard) e um piloto com cerca de 5 empresas.
