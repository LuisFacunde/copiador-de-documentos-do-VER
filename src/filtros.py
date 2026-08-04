from datetime import datetime, timedelta
from pathlib import Path

from .parser import extrair_info_arquivo
from .config import DATA_MIN, DATA_MAX, JANELA_DIAS, EXTENSAO_PERMITIDA


def e_arquivo_permitido(arquivo: Path) -> bool:
    if EXTENSAO_PERMITIDA is None:
        return True
    return arquivo.suffix.lower() == EXTENSAO_PERMITIDA.lower()


def dentro_do_periodo(data: datetime) -> bool:
    return DATA_MIN <= data <= DATA_MAX


def agrupar_por_tipo(arquivos_pasta: list[Path], verbose: bool = False) -> dict:
    resultado = {'RET': [], 'OCT': [], '_invalidos': 0, '_tipo_invalido': 0, '_fora_periodo': 0}

    for arquivo in arquivos_pasta:
        if not arquivo.is_file():
            continue
        if not e_arquivo_permitido(arquivo):
            continue

        data, prontuario, tipo = extrair_info_arquivo(arquivo.name)

        if data is None:
            if verbose:
                print(f"   ⊘ {arquivo.name} — não foi possível extrair data")
            resultado['_invalidos'] += 1
            continue

        if tipo is None:
            if verbose:
                print(f"   ⊘ {arquivo.name} — tipo de exame não é RET nem OCT")
            resultado['_tipo_invalido'] += 1
            continue

        if not dentro_do_periodo(data):
            if verbose:
                print(
                    f"   ⊘ {arquivo.name} — fora do período "
                    f"({DATA_MIN.strftime('%d/%m/%Y')}–{DATA_MAX.strftime('%d/%m/%Y')})"
                )
            resultado['_fora_periodo'] += 1
            continue

        resultado[tipo].append({
            'path': arquivo,
            'data': data,
            'tipo': tipo,
            'nome': arquivo.name,
        })

    return resultado


def aplicar_janela_temporal(exames: list[dict], verbose: bool = False) -> tuple[list, int]:
    if not exames:
        return [], 0

    ordenados = sorted(exames, key=lambda x: x['data'], reverse=True)
    mais_recente = ordenados[0]
    data_limite = mais_recente['data'] - timedelta(days=JANELA_DIAS)

    if verbose:
        print(
            f"   📅 {mais_recente['tipo']} mais recente: "
            f"{mais_recente['data'].strftime('%d/%m/%Y')} | "
            f"Limite de {JANELA_DIAS} dias: {data_limite.strftime('%d/%m/%Y')}"
        )

    para_copiar = []
    descartados = 0

    for exame in ordenados:
        if exame['data'] >= data_limite:
            para_copiar.append(exame)
        else:
            if verbose:
                print(
                    f"      ⊘ {exame['nome']} ({exame['tipo']}) — "
                    f"{exame['data'].strftime('%d/%m/%Y')} "
                    f"(anterior aos {JANELA_DIAS} dias)"
                )
            descartados += 1

    return para_copiar, descartados
