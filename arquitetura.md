# Arquitetura: Arena de Vendas B2B (v0.1)

> Foco deste documento: **como as memórias são orquestradas**. O resto da arquitetura aparece na medida em que a memória depende dele.

---

## 0. Regra de orçamento (decisão desta rodada)

- **Tokens contados** = `input_tokens + output_tokens + cache_creation_input_tokens`. O **`cache_read_input_tokens` não conta**. Conto a escrita de cache por segurança, porque ela é processada como entrada nova.
- **Teto por jornada: 1,5 mi de tokens contados.** Ao atingir o teto, o jogo para na hora, a jornada é marcada `abortada_orcamento` e **não entra no placar nem no aprendizado** (para não enviesar).
- **Teto global: 0,7 bi**, com parada limpa: termina as calls em andamento e não abre novas.
- **Interpretação:** entendi o "1,5 mi" como teto **por jornada**. Se você quis dizer um **teto global** para esta fase de testes, é só mudar uma linha de configuração (`orcamento.teto_global`).

---

## 1. Visão geral dos componentes

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                               GERENTE DA LIGA                                │
│  rodadas alternadas (vendedores aprendem ↔ compradores aprendem) · Elo       │
│  matchmaking · hall of fame · guarda de orçamento global                     │
└───────────────┬──────────────────────────────────────────────▲───────────────┘
                │ agenda N jornadas por rodada                 │ fim da rodada
                ▼                                              │
┌──────────────────────────────┐                ┌──────────────┴───────────────┐
│    GERADOR DE CENÁRIOS       │                │   CONSOLIDADOR ("sono")      │
│  empresa sintética × cargo × │                │  staging → nova versão da    │
│  produto × verdades ocultas  │                │  memória estratégica (v+1)   │
└───────────────┬──────────────┘                └──────────────▲───────────────┘
                ▼                                              │ lições candidatas
┌──────────────────────────────────────────────────────────┐   │ + crédito das usadas
│                 EXECUTOR DE JORNADA                      │   │
│ máquina de estados: cold call → discovery → [PoC] →      │   │
│ fechamento · guarda de orçamento por jornada             │   │
│                                                          │   │
│   ┌──────────────────────────────────────────────────┐   │   │
│   │            ORQUESTRADOR DE CALL                  │   │   │
│   │  loop de turnos · relógio · árbitro de           │   │   │
│   │  estagnação · guarda de papel                    │   │   │
│   │                                                  │   │   │
│   │   ┌────────────┐   só <fala>   ┌────────────┐    │   │   │
│   │   │  AGENTE    │ ◄──────────►  │  AGENTE    │    │   │   │
│   │   │  VENDEDOR  │               │  COMPRADOR │    │   │   │
│   │   └─────┬──────┘               └─────┬──────┘    │   │   │
│   └─────────┼────────────────────────────┼───────────┘   │   │
│             │ montagem de prompt         │               │   │
│   ┌─────────▼────────────────────────────▼───────────┐   │   │
│   │               SERVIÇO DE MEMÓRIA                 │   │   │
│   │  M1 trabalho · M2 jornada · M3 estratégica       │   │   │
│   └──────────────────────────────────────────────────┘   │   │
│                                                          │   │
│  pós-call: verificador de afirmações · pontuador         │   │
│  determinístico · regra do chefe · simulador de PoC      │   │
│  · CRÍTICO ──────────────────────────────────────────────────┘
└──────────────────────────────────────────────────────────┘
                │ tudo
                ▼
┌──────────────────────────────────────────────────────────┐
│ SQLite: cenários · jornadas · calls · turnos · afirmações│
│ · lições · versões · uso de tokens · Elo                 │
└──────────────────────────────────────────────────────────┘
```

---

## 2. As três camadas de memória

A memória segue o modelo cognitivo clássico, com uma camada para cada escala de tempo:

| Camada | Escala | Dono | Conteúdo | Análogo humano |
|---|---|---|---|---|
| **M1: Trabalho** | Um turno → uma call | Cada agente | Transcrição recente + resumo rolante + **estado privado de crenças** | "O que estou pensando agora nesta call" |
| **M2: Jornada** | Uma call → uma jornada (3 a 4 calls) | Cada agente | Vendedor: **ficha de CRM**. Comprador: **notas internas + registro de promessas** | "Minhas anotações sobre este cliente/fornecedor" |
| **M3: Estratégica** | Entre jornadas (a vida toda) | Cada **estilo** (linhagem) | **Playbook** (sempre ativo) + **lições** (recuperadas por semelhança) | "Minha experiência como profissional" |

O ponto central do desenho é que **cada camada é escrita por um processo diferente e lida num ponto diferente do prompt**, e isso casa com o cache:

```
PROMPT DE CADA TURNO (a ordem importa: do mais estável ao mais volátil)

  ┌─ [gateway] prompt oculto do LiteLLM (~128)                     ← sempre cacheado
  ├─ BLOCO A: regras do jogo + prompt do estilo + PLAYBOOK (M3)    ← estável por VERSÃO
  │           ~2,5 mil tokens                          ◆ breakpoint de cache 1
  ├─ BLOCO B: cenário (o que este agente sabe) + LIÇÕES           ← estável por CALL
  │           recuperadas (M3) + memória da jornada (M2)
  │           ~3 mil tokens                            ◆ breakpoint de cache 2
  ├─ BLOCO C: resumo rolante da call, em blocos append-only (M1)  ← cresce a cada ~10 turnos
  │           ~0 a 1,5 mil tokens                      ◆ breakpoint de cache 3
  └─ BLOCO D: últimos ~10 turnos literais + estado privado (M1)   ← muda a cada turno
              + instrução do turno
              ~1 a 2 mil tokens                          (não cacheado: é o que conta)
```

Por turno, só o bloco D (~1,5 mil) mais a saída (~300) contam para o orçamento. Todo o resto é leitura de cache. Esta é a principal alavanca de custo e o motivo de a memória ser dividida desse jeito.

---

## 3. M1: Memória de trabalho (dentro da call)

### 3.1 Saída estruturada de cada turno

```xml
<pensamento>Ele citou "integração SAP" duas vezes. Deve ser a dor principal. Ainda não sei quem decide.</pensamento>
<estado>
  dor_principal: integração com SAP (confiança 0.7)
  decisor: desconhecido, perguntar
  orcamento: não revelado
  objecoes_abertas: [preço alto vs. concorrente X]
  concessoes_feitas: []
  perguntas_feitas: 6
</estado>
<fala>Entendi. E hoje, quando dá erro nessa integração, quem é que resolve do seu lado?</fala>
<acoes></acoes>
```

- **`<pensamento>`** é descartado do contexto depois do turno. Fica só no banco, para a pesquisa. Isso contém o vazamento de raciocínio do prompt oculto do gateway.
- **`<estado>`** é o **estado privado de crenças**. O agente reescreve esse bloco a cada turno e **só a versão mais recente** entra no prompt seguinte. Isso substitui reler todos os pensamentos antigos: o custo é constante, não cresce com a call.
- **`<fala>`** é o único texto que chega ao oponente.
- **`<acoes>`** são lidas pelo pontuador. O texto não é interpretado.

### 3.2 Resumo rolante append-only

- A cada **10 turnos**, os turnos mais antigos que saem da janela literal são resumidos numa chamada curta ao modelo (~150 tokens de saída) e o resultado é **anexado** ao bloco C como um novo parágrafo. **Nunca se reescreve** o que já foi resumido, para o prefixo continuar idêntico e cacheado.
- O resumo é **neutro**: só o que foi falado, sem pensamentos de nenhum dos lados. É o mesmo texto para os dois agentes, o que evita mais uma chamada.
- A perspectiva privada de cada agente vive no `<estado>`, não no resumo.

---

## 4. M2: Memória de jornada (entre calls com o mesmo cliente)

Quando uma call termina, cada agente escreve sua memória de jornada. Os formatos imitam o que os profissionais reais mantêm.

**Vendedor: ficha de CRM (estrutura MEDDIC)**
```yaml
empresa: Rede Varejista Aurora
interlocutor: {cargo: CTO, decisor: "não; responde ao CFO (descoberto na call 2)"}
metricas: "reduzir 30% dos chamados de integração"
dor: "integração SAP ↔ e-commerce falha em pico"
processo_decisao: "CTO recomenda, CFO aprova acima de R$ 200 mil"
criterios: [integração nativa SAP, SLA 99,9%, implantação < 90 dias]
concorrente: "mencionou fornecedor X (possível blefe)"
compromissos_meus: ["enviar case de varejo", "PoC de 30 dias com critério: -20% chamados"]
proximos_passos: "reunião de PoC em 12/10 com CTO + analista"
```

**Comprador: notas internas + registro de promessas**
```yaml
impressao_do_fornecedor: "sabe do assunto, mas empurrou preço cedo"
promessas_ouvidas:
  - "integração nativa com SAP S/4HANA"      # ← confrontada com a ficha técnica depois da call
  - "implantação em 45 dias"
o_que_revelei: [dor SAP, prazo de 90 dias]
o_que_escondi: [orçamento, CFO precisa aprovar]
relatorio_para_chefe: "..."                 # ← entra na regra oculta do chefe (se influenciador)
posicao_atual: "interessado, mas cético quanto ao prazo"
```

**Leitura na call seguinte:** a M2 do próprio agente vai para o bloco B, junto com o resumo neutro da call anterior (~300 tokens). **Nenhum agente vê a M2 do outro.**

O registro de promessas do comprador também é a **entrada do simulador de PoC**. Cada promessa marcada como falsa pelo verificador e presente no critério de sucesso reduz a probabilidade de sucesso.

---

## 5. M3: Memória estratégica (entre jornadas)

É aqui que está o aprendizado do self-play.

### 5.1 Dois níveis

| Nível | Tamanho | Onde entra | Muda quando |
|---|---|---|---|
| **Playbook** | ≤ 600 tokens | Bloco A, **sempre** | Na consolidação (fim da rodada) |
| **Lições** | ~8 por call, ≤ 1,2 mil tokens | Bloco B, **recuperadas por semelhança** | Novas entram na consolidação; estatísticas atualizam a cada call |

O playbook é a **generalização** ("com CFOs, abra por impacto financeiro"). As lições são **específicas e condicionais** ("em varejo com CTO novo, perguntar sobre o legado antes de falar de preço").

### 5.2 Estrutura de uma lição

```json
{
  "id": "L-vend-consultivo-0142",
  "linhagem": "vendedor/consultivo",
  "condicao": {
    "setor": "varejo",
    "porte": null,
    "maturidade_digital": ">=alta",
    "cargo": "CTO",
    "papel": "influenciador",
    "estagio": "discovery",
    "estilo_oponente": null
  },
  "tipo": "fazer",
  "acao": "Antes de propor PoC, mapear explicitamente quem aprova o orçamento e o que essa pessoa precisa ver.",
  "porque": "Em 3 jornadas o CTO aceitou a PoC, mas o relatório ao chefe não tinha ROI e a regra do chefe reprovou.",
  "evidencias": ["call-0931", "call-1022", "call-1107"],
  "stats": { "recuperada": 14, "aplicada": 9, "ajudou": 6, "atrapalhou": 1 },
  "beta": [7, 2],
  "status": "ativa",
  "versao_criada": 3,
  "versao_aposentada": null
}
```

- **`condicao`** usa **atributos, não nomes de empresa**. É isso que faz o conhecimento transferir de "WER" para "XYZ". `null` é curinga.
- **`beta`** é a distribuição Beta(α, β) da utilidade da lição, alimentada pelo crédito (§5.4).

### 5.3 Leitura: recuperação antes de cada call

```
entrada: perfil da call = {setor, porte, maturidade, cargo, papel, estágio, estilo do oponente*}
         (* o vendedor não sabe o estilo do comprador antes da call: esse campo fica vazio para ele)

1. FILTRO:   lições ativas da linhagem, com a versão congelada da rodada
2. MATCH:    s_match = Σ peso_attr × casa(attr)       (curinga = 0,5 × peso; conflito = descarta)
             pesos: estágio 3, cargo 2, setor 2, papel 1,5, maturidade 1, porte 1, estilo 1
3. UTILIDADE: u ~ Beta(α, β)                           ← AMOSTRAGEM DE THOMPSON
4. SCORE:    s = s_match × u
5. DIVERSIDADE: top-8 por score, com no máximo 3 lições do mesmo "tema" (abertura, descoberta,
                objeção, preço, fechamento) e pelo menos 1 lição "candidata" (exploração)
```

**Por que Thompson em vez de "as melhores"?** Uma lição nova tem Beta(1,1): muita incerteza, e às vezes é sorteada alto. Assim ela **ganha chance de ser testada**, sem regra manual de exploração. Com o uso, a incerteza cai e as boas se firmam. Para a pesquisa, isso é um mecanismo limpo e mensurável de **exploração vs. aproveitamento** na memória.

A recuperação é **puro código**, sem chamada ao modelo e sem modelo de embeddings, logo custa zero tokens.

### 5.4 Escrita: crítico + atribuição de crédito (depois de cada call)

**Uma única chamada** ao crítico por call, e só para o **lado que está aprendendo nesta rodada**:

```
ENTRADA DO CRÍTICO (lado L):
  transcrição completa · pensamentos privados de L · resultado objetivo do estágio
  · lições que L recebeu nesta call · o que o oponente revelou em fala
  · [configurável] verdades ocultas do oponente  ← flag `critico_onisciente`

SAÍDA:
  creditos:  [{licao: "L-...-0142", aplicada: true, turno: 14, efeito: "ajudou"}, ...]
  novas:     1 a 3 lições candidatas no formato de §5.2
  honestidade: nota sobre afirmações falsas (só para o vendedor)
```

- **Crédito:** `aplicada ∧ ajudou` → α += 1; `aplicada ∧ atrapalhou` → β += 1; `não aplicada` → nada, mas conta como "recuperada, ignorada", um sinal de lição inútil ou mal escrita.
- **Novas lições** vão para a **área de staging** da rodada, e não direto para a memória (§6).

**A flag `critico_onisciente` é uma variável de pesquisa, não um detalhe.** Com ela ligada, o crítico do vendedor sabe o orçamento real do comprador depois do jogo: aprende mais rápido, mas é algo que um vendedor humano nunca sabe. Desligada, o aprendizado fica mais realista e mais lento. Proponho comparar as duas em ligas separadas.

### 5.5 Guardas contra aprendizado "errado"

| Risco | Guarda |
|---|---|
| **Vazamento de caso**: lição com fato de uma instância ("o orçamento da Aurora é 480 mil") | Validador por regra rejeita nomes de empresas sintéticas e números absolutos; permite padrões ("orçamentos costumam estar abaixo da tabela") |
| **Comprador irreal**: o comprador aprende a "desligar em 30 s" porque isso sempre empata | Lições de comprador passam por um **filtro de realismo**: um conjunto fixo de proibições mais uma checagem das métricas Gong nas calls em que a lição foi aplicada |
| **Vendedor mentiroso**: aprende que mentir gera reunião | Lição cujo `porque` depende de afirmação falsa (cruzamento com o verificador) é rejeitada; honestidade é métrica de linhagem |
| **Inchaço** da memória | Teto de ~150 lições ativas por linhagem; a consolidação aposenta as de pior média Beta com n ≥ 5 |

---

## 6. Consolidação ("sono") e versionamento

### 6.1 Por que em lote, e não online

Dentro de uma rodada, **todas as jornadas leem a mesma versão congelada** da memória. As escritas vão para a staging. Isso dá:
- **Paralelismo seguro**: 8 a 16 jornadas simultâneas sem disputa de escrita.
- **Reprodutibilidade**: "o vendedor consultivo v7" é um objeto fixo, dá para refazer partidas contra ele.
- **Métrica limpa**: o delta de desempenho entre v7 e v8 é atribuível à consolidação.

### 6.2 Ciclo de uma rodada

```
Rodada r (lado aprendiz = vendedores se r é ímpar, compradores se r é par)
│
├─ 1. Congela: cada linhagem usa a versão v_atual (as do lado adversário também, e as do hall of fame)
├─ 2. Roda ~24 jornadas (matchmaking por Elo; 20% contra versões antigas)
│        └─ após cada call: crítico → créditos (atualiza stats na hora, só contadores) + candidatas → staging
├─ 3. CONSOLIDAÇÃO, por linhagem do lado aprendiz (1 a 2 chamadas ao modelo por linhagem):
│        a. agrupa candidatas por condição sobreposta + tema
│        b. modelo funde duplicatas, detecta contradições com lições ativas, generaliza
│           (ex.: 3 lições de varejo iguais → 1 lição com setor = null)
│        c. candidatas com evidência em ≥ 2 jornadas entram ativas com Beta(2,1); as demais com Beta(1,1)
│        d. aposenta lições com média Beta < 0,35 e n ≥ 5
│        e. reescreve o PLAYBOOK (≤ 600 tokens) a partir das lições de maior confiança
│        f. grava v_atual+1 (copy-on-write: as lições têm versao_criada / versao_aposentada)
├─ 4. Atualiza Elo; v_atual vai para o hall of fame
└─ 5. Checa convergência: valor médio de placar na janela das últimas 3 rodadas
```

Na rodada seguinte, o **outro lado** aprende, enfrentando a versão recém-consolidada. Isso é o análogo de *fictitious play* / treino alternado em jogos de dois jogadores.

### 6.3 O que o versionamento permite na pesquisa

- **Curva de aprendizado**: Elo e placar de cada versão contra um **painel fixo de referência** (versões v0 dos 4 estilos adversários, que nunca mudam). Isso separa "ficou melhor" de "o oponente piorou".
- **Ablação**: rodar v8 **sem** o playbook, ou **sem** as lições, e medir quanto cada nível contribui.
- **Genealogia de lições**: de qual call nasceu cada lição, quando foi fundida, quando morreu.

---

## 7. Fluxo completo de uma call (sequência)

```
Executor              Memória           Vendedor          Comprador         Pós-call
   │  monta perfil       │                  │                 │                 │
   ├───────────────────► │ recupera M3      │                 │                 │
   │                     │ (Thompson)       │                 │                 │
   │                     │ carrega M2       │                 │                 │
   │ ◄─────────────────── blocos A,B p/ cada lado             │                 │
   │                                        │                 │                 │
   │ ── loop de turnos ─────────────────────────────────────────                │
   │   prompt(A,B,C,D) ───────────────────► │                 │                 │
   │   ◄── pensamento/estado/fala/ações ─── │                 │                 │
   │   guarda de papel · relógio · ledger de tokens           │                 │
   │   fala ─────────────────────────────────────────────────►│                 │
   │   ◄───────────────────────────────── pensamento/estado/fala/ações          │
   │   a cada 10 turnos: resumo append-only → bloco C         │                 │
   │   a cada 10 turnos: árbitro de estagnação                │                 │
   │   termina se: encerrar_call · aceite final · relógio · estagnação · teto   │
   │ ───────────────────────────────────────────────────────────                │
   │                                                                          │
   ├─ cada lado escreve M2 (CRM / notas + relatório) ────────────────────────► │
   ├─ verificador de afirmações (ficha técnica vs. falas) ───────────────────► │
   ├─ pontuador determinístico (+ regra do chefe, se aplicável) ─────────────► │
   ├─ crítico do lado aprendiz → créditos + candidatas → staging ────────────► │
   └─ próximo estágio? (PoC simulada → fechamento) ou fim da jornada
```

**Chamadas ao modelo por call** (discovery de 25 min, ~70 turnos):
- 70 turnos;
- ~6 resumos;
- ~6 checagens de estagnação (curtas);
- 2 escritas de M2;
- 1 verificador;
- 1 crítico.

Estimativa: ≈ **0,15 a 0,2 mi de tokens contados**, bem abaixo do teto de 1,5 mi por jornada.

---

## 8. Esquema do banco (parte de memória)

```sql
linhagens(id, lado, estilo, prompt_estilo)
versoes(id, linhagem_id, numero, playbook, criada_em_rodada, elo)
licoes(id, linhagem_id, condicao_json, tipo, acao, porque, tema,
       alpha, beta, recuperada, aplicada, ajudou, atrapalhou,
       status, versao_criada, versao_aposentada)
licoes_evidencias(licao_id, call_id)
licoes_staging(id, rodada, linhagem_id, conteudo_json, call_id)
licoes_uso(call_id, licao_id, agente, aplicada, turno, efeito)   -- crédito
memoria_jornada(jornada_id, agente, apos_call_id, conteudo_yaml)
estado_privado(turno_id, agente, estado_yaml)
resumos_call(call_id, bloco_n, texto)
uso_tokens(id, call_id, jornada_id, componente, input, output,
           cache_creation, cache_read, contado)                 -- contado = input+output+cache_creation
```

---

## 9. Estrutura de código

```
arena/
  config.yaml              # tetos de orçamento, tamanhos, flags (critico_onisciente...)
  llm.py                   # cliente LiteLLM: breakpoints de cache, retry, ledger de tokens, guarda de teto
  dados/                   # dossiês-base, catálogo, fichas técnicas
  cenarios.py              # gerador de empresas sintéticas + verdades ocultas
  agentes.py               # montagem de prompt (blocos A-D) + parser da saída estruturada
  memoria/
    trabalho.py            # M1: janela, resumo append-only, estado privado
    jornada.py             # M2: CRM / notas / promessas
    estrategica.py         # M3: recuperação (match + Thompson), crédito, staging
    consolidacao.py        # "sono": fusão, aposentadoria, playbook, versionamento
  call.py                  # orquestrador de turnos, relógio, árbitro, guarda de papel
  jornada.py               # máquina de estados dos estágios
  juizes.py                # verificador de afirmações, pontuador, regra do chefe, PoC
  critico.py
  liga.py                  # rodadas, Elo, matchmaking, hall of fame
  db.py
  relatorio.py             # HTML com curvas e visualizador de transcrições
  cli.py
```

---

## 10. Decisões de pesquisa que ficam como parâmetro

| Parâmetro | Padrão | Por que variar |
|---|---|---|
| `critico_onisciente` | desligado | Realismo vs. velocidade de aprendizado |
| `licoes_por_call` | 8 | Quanta memória ajuda antes de virar ruído |
| `thompson` | ligado | Comparar com top-k guloso |
| `jornadas_por_rodada` | 24 | Aprendizado estável vs. rápido |
| `hall_of_fame_prob` | 0,2 | Evitar ciclos |
| `playbook` | ligado | Ablação: generalização vs. lições específicas |
| `consolidacao_generaliza` | ligado | Transferência entre setores |
