from datetime import datetime
from pathlib import Path

_BASE = Path(__file__).resolve().parent.parent

PLANILHA_PRONTUARIOS = (
    _BASE
    / "dados"
    / "planilhas"
    / "Pesquisa Exames RET com Oct 4 meses antes e depois.xlsx"
)

ABA_PLANILHA = "Select fav_pesquisa"

COLUNA_PRONTUARIO = "PRONT"

DIRS_EXAMES_ORIGEM = [
    r"\\192.168.4.18\c$\apache24\htdocs\fav_exames\anexo",
    r"\\192.168.4.52\c$\exames",
]

DIR_EXAMES_DESTINO = "C:/Users/luis.silva/Desktop/anexos_exames_copias"

DATA_MIN = datetime(2020, 1, 1)
DATA_MAX = datetime(2026, 6, 30)

MAPA_TIPOS = {
    "RETIN": "RET",
    "OCTPAPILA": "OCTPAPILA",
}

JANELA_DIAS = 120

EXTENSAO_PERMITIDA = ".pdf"

LIMITE_PACIENTES_LOTE = 2500

BANCO_HISTORICO = _BASE / "dados" / "bd" / "historico.db"
