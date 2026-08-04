from datetime import datetime
from pathlib import Path

from .config import MAPA_TIPOS


def extrair_info_arquivo(nome_arquivo: str) -> tuple:

    stem = Path(nome_arquivo).stem
    partes = stem.split('-')

    if len(partes) < 4:
        return None, None, None

    prontuario = partes[0] or None

    data_str = partes[2] if len(partes) > 2 else None
    data = _parse_data(data_str)
    if data is None:
        return None, None, None

    tipo_raw = partes[3].upper() if len(partes) > 3 else ''
    tipo = _mapear_tipo(tipo_raw)

    return data, prontuario, tipo


def _parse_data(data_str: str | None) -> datetime | None:
    if not data_str or len(data_str) != 8 or not data_str.isdigit():
        return None
    try:
        return datetime(int(data_str[:4]), int(data_str[4:6]), int(data_str[6:8]))
    except ValueError:
        return None


def _mapear_tipo(tipo_raw: str) -> str | None:
    for chave, rotulo in MAPA_TIPOS.items():
        if chave in tipo_raw:
            return rotulo
    return None
