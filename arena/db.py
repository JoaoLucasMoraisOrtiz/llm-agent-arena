"""Persistência em SQLite. Um único processo asyncio escreve; conexões síncronas bastam."""
import json
import sqlite3
from pathlib import Path

ESQUEMA = """
CREATE TABLE IF NOT EXISTS linhagens(id TEXT PRIMARY KEY, lado TEXT, estilo TEXT);
CREATE TABLE IF NOT EXISTS versoes(linhagem_id TEXT, numero INTEGER, playbook TEXT, elo REAL DEFAULT 1500,
    partidas INTEGER DEFAULT 0, criada_rodada INTEGER, PRIMARY KEY(linhagem_id, numero));
CREATE TABLE IF NOT EXISTS licoes(id TEXT PRIMARY KEY, linhagem_id TEXT, condicao TEXT, tipo TEXT, tema TEXT,
    acao TEXT, porque TEXT, tecnicas TEXT, alpha REAL, beta REAL, recuperada INTEGER DEFAULT 0,
    aplicada INTEGER DEFAULT 0, ajudou INTEGER DEFAULT 0, atrapalhou INTEGER DEFAULT 0, status TEXT,
    versao_criada INTEGER, versao_aposentada INTEGER, evidencias TEXT);
CREATE TABLE IF NOT EXISTS staging(id INTEGER PRIMARY KEY AUTOINCREMENT, rodada INTEGER, linhagem_id TEXT,
    conteudo TEXT, call_id TEXT);
CREATE TABLE IF NOT EXISTS empresas_sinteticas(id TEXT PRIMARY KEY, base_id TEXT, atributos TEXT, dossie TEXT);
CREATE TABLE IF NOT EXISTS jornadas(id TEXT PRIMARY KEY, rodada INTEGER, cenario TEXT, vendedor TEXT,
    comprador TEXT, status TEXT, placar INTEGER, detalhe TEXT, criada_em TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS calls(id TEXT PRIMARY KEY, jornada_id TEXT, estagio TEXT, resultado INTEGER,
    motivo_fim TEXT, minutos REAL, detalhe TEXT, metricas TEXT);
CREATE TABLE IF NOT EXISTS turnos(call_id TEXT, n INTEGER, agente TEXT, pensamento TEXT, estado TEXT,
    tecnica TEXT, fala TEXT, acoes TEXT, palavras INTEGER, bruto TEXT);
CREATE TABLE IF NOT EXISTS afirmacoes(call_id TEXT, conteudo TEXT);
CREATE TABLE IF NOT EXISTS licoes_uso(call_id TEXT, licao_id TEXT, linhagem_id TEXT, aplicada INTEGER,
    turno INTEGER, efeito TEXT);
CREATE TABLE IF NOT EXISTS memoria_jornada(jornada_id TEXT, agente TEXT, apos_call TEXT, conteudo TEXT);
CREATE TABLE IF NOT EXISTS resumos(call_id TEXT, bloco INTEGER, texto TEXT);
CREATE TABLE IF NOT EXISTS uso_tokens(ts TEXT DEFAULT CURRENT_TIMESTAMP, jornada_id TEXT, call_id TEXT,
    componente TEXT, input INTEGER, output INTEGER, cache_creation INTEGER, cache_read INTEGER, contado INTEGER);
CREATE TABLE IF NOT EXISTS criticas(call_id TEXT, linhagem_id TEXT, conteudo TEXT);
"""


class DB:
    def __init__(self, caminho: str | Path):
        self.caminho = str(caminho)
        self.con = sqlite3.connect(self.caminho, check_same_thread=False, isolation_level=None)
        self.con.row_factory = sqlite3.Row
        self.con.execute("PRAGMA journal_mode=WAL")
        self.con.executescript(ESQUEMA)

    def ex(self, sql: str, params=()):
        return self.con.execute(sql, params)

    def um(self, sql: str, params=()):
        return self.con.execute(sql, params).fetchone()

    def todos(self, sql: str, params=()):
        return self.con.execute(sql, params).fetchall()

    def inserir(self, tabela: str, **campos):
        campos = {k: (json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v)
                  for k, v in campos.items()}
        cols = ",".join(campos)
        marcas = ",".join("?" * len(campos))
        self.con.execute(f"INSERT OR REPLACE INTO {tabela}({cols}) VALUES({marcas})", tuple(campos.values()))

    def tokens_contados(self, jornada_id: str | None = None) -> int:
        if jornada_id:
            r = self.um("SELECT COALESCE(SUM(contado),0) s FROM uso_tokens WHERE jornada_id=?", (jornada_id,))
        else:
            r = self.um("SELECT COALESCE(SUM(contado),0) s FROM uso_tokens")
        return r["s"]
