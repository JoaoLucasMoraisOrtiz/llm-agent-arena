# Arena de Vendas B2B

Dois agentes LLM (MiniMax-M3 via LiteLLM) negociam: um **comprador**, gestor de uma empresa brasileira (real ou sintética), contra um **vendedor** de um produto B2B fictício. Eles aprendem por **self-play com memória**: um crítico escreve lições depois de cada call, e um consolidador gera novas versões da memória no fim de cada rodada.

Documentos de desenho: `especificacao_tecnica.md`, `arquitetura.md`, `prompts_e_tecnicas.md`.
Resultados do smoke test: `resultados_smoke_test.md`.

## Estrutura

```
arena/
  config.yaml            tetos de orçamento, tamanhos, flags (critico_onisciente, regra_fechamento...)
  dados/empresas/*.yaml  5 dossiês-base (Magalu, WEG, Localiza, SLC, Hapvida), com pesquisa pública
  dados/produtos/*.yaml  8 produtos fictícios com ficha técnica verdadeira (existente / roadmap / limitações)
  cenarios.py            empresas sintéticas + verdades ocultas (fit, orçamento, piso, papel, nível técnico)
  conhecimento.py        catálogo de técnicas (vendedor/comprador), estilos, exemplos de tom
  agentes.py             montagem de prompt (blocos A-D) e parser do turno
  call.py                orquestrador de turnos, ações, relógio, árbitro, M1 (resumo append-only)
  jornada.py             cold call → discovery → PoC → fechamento, M2, placar, crítico
  juizes.py              resumidor, estagnação, verificador de afirmações, regra do chefe, PoC, placar
  memoria/estrategica.py M3: recuperação por atributos + Thompson, crédito, validação
  memoria/aprendizado.py crítico e consolidador ("sono")
  liga.py                rodadas alternadas, Elo, hall of fame, avaliação pareada com ablação, modo contínuo
  relatorio.py           relatório Markdown + transcrições
  cli.py                 linha de comando
```

## Uso

```bash
# credenciais em .env (ARENA_BASE_URL, ARENA_API_KEY, ARENA_MODEL) — nunca versionar
.venv/bin/python -m arena.cli --db runs/x.db sinteticas --por-base 2        # gera empresas sintéticas
.venv/bin/python -m arena.cli --db runs/x.db smoke --jornadas 5             # jornadas sem consolidação
.venv/bin/python -m arena.cli --db runs/x.db liga --rodadas 4 --jornadas 12 # rodadas com aprendizado
.venv/bin/python -m arena.cli --db runs/x.db avaliar --lado vendedor --n 12 # avaliação pareada + ablação
.venv/bin/python -m arena.cli --db runs/x.db continuo                       # liga até o teto de orçamento
.venv/bin/python -m arena.cli --db runs/x.db relatorio                      # relatório + transcrições
ARENA_CONFIG=outro.yaml ...                                                 # usa outra configuração
.venv/bin/python -m arena.cli --db runs/x.db deriva --rodadas 1-14          # painel de deriva de realismo (offline)
.venv/bin/python -m arena.cli --db runs/x.db regras                         # hash das regras congeladas
```

Saídas de cada banco `runs/x.db` ficam em `runs/x/`: `relatorio.md`, `transcricoes/*.md`, `evolucao.jsonl` e `avaliacao_final.json`.

## Execução de 23/09/2026 (encerrada)

Duas ligas paralelas rodaram até a cota de 5h da conta do provedor acabar (~70 mi de tokens, 956 calls):

| liga | config | crítico |
|---|---|---|
| A_realista | `runs/cfg_liga_A_realista.yaml` | não vê as informações ocultas do oponente |
| B_onisciente | `runs/cfg_liga_B_onisciente.yaml` | vê orçamento, fit e piso depois do jogo |

- **Análise completa:** `analise_experimento.md`.
- **Relatórios:** `runs/liga_*/relatorio.md`, `runs/comparativo.md`, transcrições em `runs/liga_*/transcricoes/`.
- **Retomar** (da última rodada gravada): `runs/lancar_ligas.sh`. Estado: `runs/status.sh`. Parar: `pkill -f arena.cli`.
- **Não rodou:** a avaliação final com ablação (`avaliacao_final.json`). Para rodá-la avulsa: `ARENA_CONFIG=runs/cfg_liga_A_realista.yaml .venv/bin/python -m arena.cli --db runs/liga_A_realista.db avaliar --lado vendedor --n 24`.

## Contabilidade de tokens

Contado = `input + output + cache_creation` (a leitura de cache não conta). Teto por jornada: 1,5 mi (a jornada é abortada e sai do placar). Teto global por liga: em `config.yaml`.

## Fase 0 da próxima rodada (28/09/2026)

Estão implementadas as correções de `plano_proxima_rodada.md`, junto com o comprador que nem sempre responde à pergunta do vendedor. O que foi feito e o que ficou de fora está no próprio plano, na seção "Estado da implementação".

- **Testes offline:** `.venv/bin/python tests/test_fase0.py` (ou com pytest).
- **Cópia do código anterior:** `arena_backup_2026-09-28/`.
- **Banco novo:** a próxima corrida deve usar um banco novo, porque o `continuo` recusa misturar versões de regras.
