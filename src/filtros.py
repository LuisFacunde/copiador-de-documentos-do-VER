import logging
from datetime import datetime, timedelta
from pathlib import Path

from .parser import extrair_info_arquivo_antigo, extrair_info_arquivo_novo
from .config import DATA_MIN, DATA_MAX, JANELA_DIAS, EXTENSAO_PERMITIDA


def e_arquivo_permitido(arquivo: Path) -> bool:
    if EXTENSAO_PERMITIDA is None:
        return True
    return arquivo.suffix.lower() == EXTENSAO_PERMITIDA.lower()


def dentro_do_periodo(data: datetime) -> bool:
    return DATA_MIN <= data <= DATA_MAX


def agrupar_exames_antigos(
    arquivos_pasta: list[Path],
    logger: logging.Logger | None = None,
    verbose: bool = False,
) -> dict:
    """Agrupa exames no formato antigo por tipo (RET / OCTPAPILA).

    Apenas arquivos no formato antigo são considerados.
    A data é obtida do metadado de modificação do arquivo.
    """
    resultado = {
        "RET": [],
        "OCTPAPILA": [],
        "_invalidos": 0,
        "_tipo_invalido": 0,
        "_fora_periodo": 0,
    }

    def _log(nivel: str, msg: str) -> None:
        if logger:
            getattr(logger, nivel)(msg)
        elif verbose:
            print(msg)

    for arquivo in arquivos_pasta:
        if not arquivo.is_file():
            continue
        if not e_arquivo_permitido(arquivo):
            continue

        data, prontuario, tipo = extrair_info_arquivo_antigo(arquivo)

        if data is None:
            # Pode ser formato novo — não contabilizar como inválido aqui
            continue

        if tipo is None:
            _log(
                "debug",
                f"    📭 {arquivo.name} (antigo) - tipo de exame não é RET nem OCTPAPILA",
            )
            resultado["_tipo_invalido"] += 1
            continue

        if not dentro_do_periodo(data):
            _log(
                "debug",
                f"    📭 {arquivo.name} (antigo) - fora do período "
                f"({DATA_MIN.strftime('%d/%m/%Y')} a {DATA_MAX.strftime('%d/%m/%Y')})",
            )
            resultado["_fora_periodo"] += 1
            continue

        resultado[tipo].append(
            {
                "path": arquivo,
                "data": data,
                "tipo": tipo,
                "nome": arquivo.name,
                "formato": "antigo",
            }
        )

    return resultado


def coletar_exames_novos(
    arquivos_pasta: list[Path],
    tipos_aprovados: set[str],
    logger: logging.Logger | None = None,
    verbose: bool = False,
) -> list[dict]:
    """Coleta exames no formato novo dos tipos aprovados.

    Após o paciente ser aprovado pelo critério com exames antigos,
    esta função coleta os exames novos dos mesmos tipos para cópia.
    """
    resultado = []

    def _log(nivel: str, msg: str) -> None:
        if logger:
            getattr(logger, nivel)(msg)
        elif verbose:
            print(msg)

    for arquivo in arquivos_pasta:
        if not arquivo.is_file():
            continue
        if not e_arquivo_permitido(arquivo):
            continue

        data, prontuario, tipo = extrair_info_arquivo_novo(arquivo)

        if data is None or tipo is None:
            continue

        if tipo not in tipos_aprovados:
            _log(
                "debug",
                f"    📭 {arquivo.name} (novo) - tipo {tipo} não está nos aprovados",
            )
            continue

        if not dentro_do_periodo(data):
            _log(
                "debug",
                f"    📭 {arquivo.name} (novo) - fora do período "
                f"({DATA_MIN.strftime('%d/%m/%Y')} a {DATA_MAX.strftime('%d/%m/%Y')})",
            )
            continue

        resultado.append(
            {
                "path": arquivo,
                "data": data,
                "tipo": tipo,
                "nome": arquivo.name,
                "formato": "novo",
            }
        )

    return resultado


def agrupar_por_tipo(
    arquivos_pasta: list[Path],
    logger: logging.Logger | None = None,
    verbose: bool = False,
) -> dict:
    """Agrupa exames por tipo usando ambos os formatos.

    Mantido para compatibilidade. O fluxo principal usa
    agrupar_exames_antigos + coletar_exames_novos.
    """
    from .parser import extrair_info_arquivo

    resultado = {
        "RET": [],
        "OCTPAPILA": [],
        "_invalidos": 0,
        "_tipo_invalido": 0,
        "_fora_periodo": 0,
    }

    def _log(nivel: str, msg: str) -> None:
        if logger:
            getattr(logger, nivel)(msg)
        elif verbose:
            print(msg)

    for arquivo in arquivos_pasta:
        if not arquivo.is_file():
            continue
        if not e_arquivo_permitido(arquivo):
            continue

        data, prontuario, tipo = extrair_info_arquivo(arquivo)

        if data is None:
            _log("debug", f"    📭 {arquivo.name} - não foi possível extrair data")
            resultado["_invalidos"] += 1
            continue

        if tipo is None:
            _log(
                "debug",
                f"    📭 {arquivo.name} - tipo de exame não é RET nem OCTPAPILA",
            )
            resultado["_tipo_invalido"] += 1
            continue

        if not dentro_do_periodo(data):
            _log(
                "debug",
                f"    📭 {arquivo.name} - fora do período "
                f"({DATA_MIN.strftime('%d/%m/%Y')} a {DATA_MAX.strftime('%d/%m/%Y')})",
            )
            resultado["_fora_periodo"] += 1
            continue

        resultado[tipo].append(
            {
                "path": arquivo,
                "data": data,
                "tipo": tipo,
                "nome": arquivo.name,
            }
        )

    return resultado


def avaliar_criterio_paciente(
    ret_lista: list[dict],
    oct_lista: list[dict],
    janela_dias: int = JANELA_DIAS,
    logger: logging.Logger | None = None,
    verbose: bool = False,
) -> tuple[bool, list[dict], list[str]]:
    def _log(nivel: str, msg: str) -> None:
        if logger:
            getattr(logger, nivel)(msg)
        elif verbose:
            print(msg)

    if not ret_lista and not oct_lista:
        return False, [], ["sem exames RET e OCTPAPILA válidos no período"]

    if not ret_lista:
        return False, [], ["sem exame RET válido no período"]

    if not oct_lista:
        return False, [], ["sem exame OCTPAPILA válido no período"]

    pares_correspondentes = []
    for r in ret_lista:
        for o in oct_lista:
            diferenca_dias = (o["data"] - r["data"]).days
            if abs(diferenca_dias) <= janela_dias:
                pares_correspondentes.append((r, o, diferenca_dias))

    if pares_correspondentes:
        for r, o, dias in pares_correspondentes:
            sinal = f"+{dias}" if dias >= 0 else f"{dias}"
            _log(
                "debug",
                f"    🎯 Correspondência: RET {r['data'].strftime('%d/%m/%Y')} "
                f"↔ OCTPAPILA {o['data'].strftime('%d/%m/%Y')} ({sinal} dias)",
            )
        para_copiar = ret_lista + oct_lista
        return True, para_copiar, []

    menor_diferenca = min(
        abs((o["data"] - r["data"]).days) for r in ret_lista for o in oct_lista
    )
    _log(
        "debug",
        f"    📭 Nenhuma correspondência RET ↔ OCTPAPILA em ±{janela_dias} dias "
        f"(menor intervalo: {menor_diferenca} dias)",
    )
    motivo = f"nenhum OCTPAPILA a ±{janela_dias} dias de uma RET (menor intervalo: {menor_diferenca} dias)"
    return False, [], [motivo]
