import sqlite3
from datetime import datetime
from pathlib import Path


def inicializar_banco(caminho_db: Path) -> sqlite3.Connection:
    caminho_db = Path(caminho_db)
    caminho_db.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(caminho_db))
    conn.row_factory = sqlite3.Row

    conn.executescript("""
        CREATE TABLE IF NOT EXISTS lote (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            numero            INTEGER NOT NULL UNIQUE,
            data_envio        TEXT    NOT NULL,
            data_inicio       TEXT    NOT NULL,
            data_fim          TEXT,
            total_prontuarios INTEGER DEFAULT 0,
            total_arquivos    INTEGER DEFAULT 0,
            status            TEXT    DEFAULT 'em_andamento'
        );

        CREATE TABLE IF NOT EXISTS historico_copias (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            lote_id         INTEGER NOT NULL,
            prontuario      TEXT    NOT NULL,
            arquivo         TEXT    NOT NULL,
            tipo_exame      TEXT,
            data_exame      TEXT,
            data_copia      TEXT    NOT NULL,
            FOREIGN KEY (lote_id) REFERENCES lote(id)
        );

        CREATE TABLE IF NOT EXISTS prontuarios_descartados (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            lote_id             INTEGER NOT NULL,
            prontuario          TEXT    NOT NULL,
            motivo              TEXT    NOT NULL,
            data_processamento  TEXT    NOT NULL,
            FOREIGN KEY (lote_id) REFERENCES lote(id)
        );

        CREATE INDEX IF NOT EXISTS idx_prontuario
            ON historico_copias(prontuario);
        CREATE INDEX IF NOT EXISTS idx_lote
            ON historico_copias(lote_id);
        CREATE INDEX IF NOT EXISTS idx_descartado_prontuario
            ON prontuarios_descartados(prontuario);
        CREATE INDEX IF NOT EXISTS idx_descartado_lote
            ON prontuarios_descartados(lote_id);
    """)

    conn.commit()
    return conn


def obter_proximo_numero_lote(conn: sqlite3.Connection) -> int:
    cursor = conn.execute("SELECT MAX(numero) FROM lote")
    resultado = cursor.fetchone()[0]
    return 1 if resultado is None else resultado + 1


def criar_lote(conn: sqlite3.Connection, numero: int, data_envio: str) -> int:
    agora = datetime.now().isoformat()
    cursor = conn.execute(
        "INSERT INTO lote (numero, data_envio, data_inicio) VALUES (?, ?, ?)",
        (numero, data_envio, agora),
    )
    conn.commit()
    return cursor.lastrowid


def finalizar_lote(
    conn: sqlite3.Connection,
    lote_id: int,
    total_prontuarios: int,
    total_arquivos: int,
    status: str = 'concluido',
) -> None:
    conn.execute(
        """UPDATE lote
           SET data_fim = ?, total_prontuarios = ?,
               total_arquivos = ?, status = ?
           WHERE id = ?""",
        (datetime.now().isoformat(), total_prontuarios,
         total_arquivos, status, lote_id),
    )
    conn.commit()


def registrar_copia(
    conn: sqlite3.Connection,
    lote_id: int,
    prontuario: str,
    arquivo: str,
    tipo_exame: str | None = None,
    data_exame: str | None = None,
) -> None:
    conn.execute(
        """INSERT INTO historico_copias
           (lote_id, prontuario, arquivo, tipo_exame, data_exame, data_copia)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (lote_id, prontuario, arquivo, tipo_exame, data_exame,
         datetime.now().isoformat()),
    )
    conn.commit()


def registrar_descarte(
    conn: sqlite3.Connection,
    lote_id: int,
    prontuario: str,
    motivo: str,
) -> None:
    conn.execute(
        """INSERT INTO prontuarios_descartados
           (lote_id, prontuario, motivo, data_processamento)
           VALUES (?, ?, ?, ?)""",
        (lote_id, prontuario, motivo, datetime.now().isoformat()),
    )
    conn.commit()


def listar_prontuarios_processados(conn: sqlite3.Connection) -> set[str]:
    cursor = conn.execute(
        """SELECT DISTINCT prontuario FROM historico_copias
           UNION
           SELECT DISTINCT prontuario FROM prontuarios_descartados"""
    )
    return {row[0] for row in cursor.fetchall()}
