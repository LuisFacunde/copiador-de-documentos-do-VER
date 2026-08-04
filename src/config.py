from datetime import datetime
from pathlib import Path

_BASE = Path(__file__).resolve().parent.parent

PLANILHA_PRONUNCIARIOS = _BASE / 'dados' / 'planilha_de_testes.xlsx'

ABA_PLANILHA = 'Select fav_pesquisa'

COLUNA_PRONUNCIARIO = 'PRONT'

DIR_EXAMES_ORIGEM = 'C:/users/luis.silva/Desktop/Sistemas FAV/pdfs'

DIR_EXAMES_DESTINO = 'C:/Users/luis.silva/Desktop/Sistemas FAV/destino_copias'

# PERÍODO PERMITIDO
DATA_MIN = datetime(2020, 1, 1)
DATA_MAX = datetime(2026, 6, 30)

# TIPOS DE EXAME
MAPA_TIPOS = {
    'RETIN': 'RET',
    'OCT':   'OCT',
}

# CRITÉRIO DE JANELA TEMPORAL
JANELA_DIAS = 120  # 4 meses
