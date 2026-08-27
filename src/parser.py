from datetime import datetime
from pathlib import Path
import re

from .config import MAPA_TIPOS


def extrair_info_arquivo_antigo(arquivo: Path) -> tuple:
    """Extrai informações apenas de arquivos no formato antigo.

    Formato antigo: PRONTUARIO - NOME - DESC_EXAME (com ou sem hífen)
    A data é obtida pelo metadado de modificação do arquivo.
    Não possui data no nome do arquivo.

    Retorna (data, prontuario, tipo) ou (None, None, None).
    """
    # Verifica primeiro se NÃO é formato novo (que tem >=4 partes separadas por hífen
    # e a terceira parte é uma data YYYYMMDD)
    stem = arquivo.stem
    partes = stem.split('-')
    if len(partes) >= 4:
        data_str = partes[2].strip() if len(partes) > 2 else None
        if data_str and len(data_str) == 8 and data_str.isdigit():
            # É formato novo — não processar como antigo
            return None, None, None

    # Formato antigo: prontuário no início do nome
    match_prontuario = re.match(r"^(\d+)", arquivo.name)
    prontuario = match_prontuario.group(1) if match_prontuario else None

    tipo = _mapear_tipo(arquivo.name.upper())

    if prontuario and tipo:
        try:
            estatisticas = arquivo.stat()
            timestamp = min(estatisticas.st_mtime, estatisticas.st_ctime)
            data = datetime.fromtimestamp(timestamp)
            return data, prontuario, tipo
        except Exception:
            pass

    return None, None, None


def extrair_info_arquivo_novo(arquivo: Path) -> tuple:
    """Extrai informações apenas de arquivos no formato novo.

    Formato novo: PRONTUARIO-ID-YYYYMMDD-TIPO-OLHO-TIMESTAMP
    A data é extraída do nome do arquivo.

    Retorna (data, prontuario, tipo) ou (None, None, None).
    """
    stem = arquivo.stem
    partes = stem.split('-')

    if len(partes) >= 4:
        prontuario = partes[0] or None
        data_str = partes[2] if len(partes) > 2 else None
        data = _parse_data(data_str)
        if data is not None:
            tipo_raw = partes[3].upper() if len(partes) > 3 else ''
            tipo = _mapear_tipo(tipo_raw)
            if tipo is not None:
                return data, prontuario, tipo

    return None, None, None


def extrair_info_arquivo(arquivo: Path) -> tuple:
    """Extrai informações do arquivo tentando formato novo e depois antigo (fallback).

    Mantido para compatibilidade. O fluxo principal usa as funções
    específicas extrair_info_arquivo_antigo e extrair_info_arquivo_novo.
    """
    # Tenta formato novo primeiro
    data, prontuario, tipo = extrair_info_arquivo_novo(arquivo)
    if data is not None:
        return data, prontuario, tipo

    # Fallback para formato antigo
    return extrair_info_arquivo_antigo(arquivo)


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
