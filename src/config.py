from datetime import datetime
from pathlib import Path

_BASE = Path(__file__).resolve().parent.parent

PLANILHA_PRONUNCIARIOS = _BASE / 'dados' / 'planilha_de_testes.xlsx'

ABA_PLANILHA = 'Select fav_pesquisa'

COLUNA_PRONUNCIARIO = 'PRONT'

DIR_EXAMES_ORIGEM = 'C:/Users/luis.silva/Desktop/anexos_exames'

DIR_EXAMES_DESTINO = 'C:/Users/luis.silva/Desktop/anexos_exames_copias'

DATA_MIN = datetime(2020, 1, 1)
DATA_MAX = datetime(2026, 6, 30)

MAPA_TIPOS = {
    'RETIN': 'RET',
    'OCTPAPILA': 'OCTPAPILA',
}

JANELA_DIAS = 120

EXTENSAO_PERMITIDA = '.pdf'
