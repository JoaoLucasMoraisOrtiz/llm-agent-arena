"""Cliente do LLM (MiniMax-M3 via LiteLLM, API compatível com Anthropic).

Responsável por: montar blocos com cache, repetir em falhas, registrar uso de tokens
e aplicar os tetos de orçamento (por jornada e global).
"""
import asyncio
import os
import random
import time

from anthropic import AsyncAnthropic, APIError, APIStatusError, APITimeoutError, APIConnectionError
from dotenv import load_dotenv

from .config import CFG, RAIZ

load_dotenv(RAIZ.parent / ".env")


class OrcamentoEsgotado(Exception):
    pass


class LLM:
    def __init__(self, db):
        self.db = db
        self.cliente = AsyncAnthropic(base_url=os.environ["ARENA_BASE_URL"], api_key=os.environ["ARENA_API_KEY"],
                                      timeout=CFG["modelo"]["timeout_s"], max_retries=0)
        self.modelo = os.environ.get("ARENA_MODELO", os.environ.get("ARENA_MODEL"))
        # vazão adaptativa (AIMD): o limite de chamadas simultâneas cai pela metade num 429 e sobe devagar
        self.max_conc = CFG["modelo"]["max_concorrencia"]
        self.limite = self.max_conc
        self.ativas = 0
        self.cond = asyncio.Condition()
        self.pausa_ate = 0.0
        self.cooldown = 30.0
        self.sucessos = 0
        self.n_429 = 0
        # Fase 0.6: cota da janela esgotada -> dorme e sonda a cada `sonda_s`, uma chamada por vez
        self.cota_esgotada_desde = None
        self.sonda_s = float(CFG["modelo"].get("sonda_cota_s", 600))
        self.ao_evento = lambda ev: print(f"  [cota] {ev}", flush=True)
        # contadores em memória: evitam SUM no banco a cada chamada
        self.gasto_global = db.tokens_contados()
        self.gasto_jornada: dict[str, int] = {}

    def checar_orcamento(self, jornada_id: str | None):
        if self.gasto_global >= CFG["orcamento"]["teto_global"]:
            raise OrcamentoEsgotado("teto global atingido")
        if jornada_id and self.gasto_jornada.get(jornada_id, 0) >= CFG["orcamento"]["teto_por_jornada"]:
            raise OrcamentoEsgotado(f"teto da jornada {jornada_id} atingido")

    async def chamar(self, *, sistema: list[str], usuario: list[str], temperatura: float, max_tokens: int,
                     componente: str, jornada_id: str | None = None, call_id: str | None = None) -> str:
        """sistema/usuario: listas de blocos de texto, do mais estável ao mais volátil.
        Todos os blocos exceto o último do usuário recebem cache_control."""
        self.checar_orcamento(jornada_id)
        system = [{"type": "text", "text": t, "cache_control": {"type": "ephemeral"}} for t in sistema if t]
        conteudo = []
        for i, t in enumerate(u for u in usuario if u):
            bloco = {"type": "text", "text": t}
            if i < len(usuario) - 1:
                bloco["cache_control"] = {"type": "ephemeral"}
            conteudo.append(bloco)
        ultimo_erro = None
        falhas = 0          # erros que não são limite de taxa
        espera_429 = 0.0    # tempo total esperando por limite de taxa
        while True:
            await self._entrar()
            try:
                r = await self.cliente.messages.create(
                    model=self.modelo, max_tokens=max_tokens, system=system,
                    messages=[{"role": "user", "content": conteudo}],
                    extra_body={"temperature": temperatura})
                self._sair(sucesso=True)
                self._registrar(r.usage, componente, jornada_id, call_id)
                return "".join(getattr(b, "text", "") for b in r.content if b.type == "text")
            except APIStatusError as e:
                self._sair(sucesso=False)
                ultimo_erro = e
                if e.status_code == 429:
                    self._limitado()
                    if self.cota_esgotada_desde is None:     # enquanto a cota está esgotada, espera sem teto
                        espera_429 += self.cooldown
                        if espera_429 > CFG["modelo"].get("espera_max_429_s", 6 * 3600):
                            raise RuntimeError(f"limite de taxa persistente por horas: {e}")
                    continue
                if e.status_code < 500:
                    raise
                falhas += 1
            except (APITimeoutError, APIConnectionError, APIError) as e:
                self._sair(sucesso=False)
                ultimo_erro = e
                falhas += 1
            if falhas >= CFG["modelo"]["tentativas"]:
                raise RuntimeError(f"LLM falhou após tentativas: {ultimo_erro}")
            await asyncio.sleep(2 ** falhas + random.random())

    async def _entrar(self):
        while True:
            agora = asyncio.get_running_loop().time()
            if agora < self.pausa_ate:
                await asyncio.sleep(self.pausa_ate - agora + random.random())
                continue
            async with self.cond:
                if self.ativas < self.limite:
                    self.ativas += 1
                    return
                await self.cond.wait()

    def _sair(self, sucesso: bool):
        self.ativas -= 1
        if sucesso and self.cota_esgotada_desde is not None:
            dormiu = time.time() - self.cota_esgotada_desde
            self.cota_esgotada_desde = None
            self.cooldown = 30.0
            self.ao_evento({"tipo": "cota_reaberta", "ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "dormiu_s": round(dormiu)})
        if sucesso:
            self.sucessos += 1
            if self.sucessos % 20 == 0:
                self.limite = min(self.max_conc, self.limite + 1)
                self.cooldown = max(30.0, self.cooldown / 2)
        asyncio.get_running_loop().create_task(self._notificar())

    async def _notificar(self):
        async with self.cond:
            self.cond.notify_all()

    def _limitado(self):
        agora = asyncio.get_running_loop().time()
        self.n_429 += 1
        if agora >= self.pausa_ate:          # primeiro 429 desta onda: reduz e pausa
            if self.cooldown >= 600.0 and self.cota_esgotada_desde is None:
                # 429 mesmo depois das esperas longas: a cota da janela acabou. Uma chamada por vez, sondando.
                self.cota_esgotada_desde = time.time()
                self.ao_evento({"tipo": "cota_esgotada", "ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "n_429": self.n_429})
            if self.cota_esgotada_desde is not None:
                self.limite = 1
                self.pausa_ate = agora + self.sonda_s
            else:
                self.limite = max(1, self.limite // 2)
                self.pausa_ate = agora + self.cooldown
                print(f"  [vazão] 429 do provedor: pausa de {self.cooldown:.0f}s, concorrência → {self.limite}", flush=True)
                self.cooldown = min(600.0, self.cooldown * 2)
            self.sucessos = 0

    def _registrar(self, u, componente, jornada_id, call_id):
        inp = u.input_tokens or 0
        out = u.output_tokens or 0
        cw = u.cache_creation_input_tokens or 0
        cr = u.cache_read_input_tokens or 0
        contado = inp + out + cw
        self.gasto_global += contado
        if jornada_id:
            self.gasto_jornada[jornada_id] = self.gasto_jornada.get(jornada_id, 0) + contado
        self.db.inserir("uso_tokens", jornada_id=jornada_id, call_id=call_id, componente=componente,
                        input=inp, output=out, cache_creation=cw, cache_read=cr, contado=contado)
