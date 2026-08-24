import logging
from datetime import datetime
from pathlib import Path

from .parser import extrair_info_arquivo
from .perfil import PerfilSerie


def e_arquivo_permitido(arquivo: Path, extensao: str | None) -> bool:
    if not extensao:
        return True
    return arquivo.suffix.lower() == extensao.lower()


def dentro_do_periodo(data: datetime, data_min: datetime, data_max: datetime) -> bool:
    return data_min <= data <= data_max


def agrupar_por_tipo(
    arquivos_pasta: list[Path],
    perfil: PerfilSerie,
    logger: logging.Logger | None = None,
    verbose: bool = False,
) -> dict:
    """
    Agrupa os arquivos da pasta de um prontuário por tipo de exame,
    de acordo com os tipos definidos no perfil da série.

    Retorna um dict com uma chave por tipo (ex: 'RET', 'OCTPAPILA')
    e chaves de contadores internos: '_invalidos', '_tipo_invalido', '_fora_periodo'.
    """
    # Inicializa resultado com todos os tipos do perfil + contadores internos
    resultado: dict = {tipo: [] for tipo in perfil.mapa_tipos.values()}
    resultado.update({'_invalidos': 0, '_tipo_invalido': 0, '_fora_periodo': 0})

    def _log(nivel: str, msg: str) -> None:
        if logger:
            getattr(logger, nivel)(msg)
        elif verbose:
            print(msg)

    for arquivo in arquivos_pasta:
        if not arquivo.is_file():
            continue
        if not e_arquivo_permitido(arquivo, perfil.extensao_permitida):
            continue

        data, prontuario, tipo = extrair_info_arquivo(arquivo.name, perfil.mapa_tipos)

        if data is None:
            _log('debug', f"    📭 {arquivo.name} - não foi possível extrair data")
            resultado['_invalidos'] += 1
            continue

        if tipo is None:
            _log('debug', f"    📭 {arquivo.name} - tipo não reconhecido nesta série")
            resultado['_tipo_invalido'] += 1
            continue

        if not dentro_do_periodo(data, perfil.data_min, perfil.data_max):
            _log('debug',
                f"    📭 {arquivo.name} - fora do período "
                f"({perfil.data_min.strftime('%d/%m/%Y')} a {perfil.data_max.strftime('%d/%m/%Y')})"
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


def avaliar_criterio_paciente(
    agrupados: dict,
    perfil: PerfilSerie,
    logger: logging.Logger | None = None,
    verbose: bool = False,
) -> tuple[bool, list[dict], list[str]]:
    """
    Avalia se o paciente atende ao critério de inclusão da série:
    - Todos os tipos em `perfil.tipos_obrigatorios` devem ter pelo menos um exame válido.
    - Deve existir ao menos um par de exames (um de cada tipo obrigatório) cujas datas
      estejam dentro de `perfil.janela_dias` entre si.

    Suporta séries com 2 ou mais tipos obrigatórios.
    Para séries com mais de 2 tipos, a janela é avaliada em relação ao primeiro tipo.
    """
    def _log(nivel: str, msg: str) -> None:
        if logger:
            getattr(logger, nivel)(msg)
        elif verbose:
            print(msg)

    tipos = perfil.tipos_obrigatorios
    janela = perfil.janela_dias

    # Verifica presença de todos os tipos obrigatórios
    for tipo in tipos:
        if not agrupados.get(tipo):
            return False, [], [f"sem exame {tipo} válido no período"]

    # Para séries com exatamente 2 tipos obrigatórios
    if len(tipos) == 2:
        tipo_a, tipo_b = tipos
        lista_a = agrupados[tipo_a]
        lista_b = agrupados[tipo_b]

        pares_correspondentes = []
        for a in lista_a:
            for b in lista_b:
                diferenca_dias = (b['data'] - a['data']).days
                if abs(diferenca_dias) <= janela:
                    pares_correspondentes.append((a, b, diferenca_dias))

        if pares_correspondentes:
            for a, b, dias in pares_correspondentes:
                sinal = f"+{dias}" if dias >= 0 else f"{dias}"
                _log('debug',
                    f"    🎯 Correspondência: {tipo_a} {a['data'].strftime('%d/%m/%Y')} "
                    f"↔ {tipo_b} {b['data'].strftime('%d/%m/%Y')} ({sinal} dias)"
                )
            # Copia todos os exames dos tipos obrigatórios (não só o par)
            para_copiar = lista_a + lista_b
            return True, para_copiar, []

        menor_diferenca = min(
            abs((b['data'] - a['data']).days)
            for a in lista_a
            for b in lista_b
        )
        _log('debug',
            f"    📭 Nenhuma correspondência {tipo_a} ↔ {tipo_b} em ±{janela} dias "
            f"(menor intervalo: {menor_diferenca} dias)"
        )
        motivo = (
            f"nenhum {tipo_b} a ±{janela} dias de um {tipo_a} "
            f"(menor intervalo: {menor_diferenca} dias)"
        )
        return False, [], [motivo]

    # Para séries com 3+ tipos obrigatórios:
    # Verifica se existe ao menos um exame do tipo_0 que tenha correspondência
    # com pelo menos um exame de CADA outro tipo, dentro da janela.
    tipo_ancora = tipos[0]
    outros_tipos = tipos[1:]

    para_copiar: list[dict] = []
    algum_valido = False

    for ancora in agrupados[tipo_ancora]:
        correspondencias = {t: [] for t in outros_tipos}
        for tipo in outros_tipos:
            for exame in agrupados[tipo]:
                if abs((exame['data'] - ancora['data']).days) <= janela:
                    correspondencias[tipo].append(exame)

        # Todos os outros tipos precisam ter ao menos um correspondente
        if all(correspondencias[t] for t in outros_tipos):
            algum_valido = True
            _log('debug',
                f"    🎯 Correspondência encontrada ancorada em "
                f"{tipo_ancora} {ancora['data'].strftime('%d/%m/%Y')}"
            )

    if algum_valido:
        para_copiar = sum((agrupados[t] for t in tipos), [])
        return True, para_copiar, []

    motivo = f"nenhuma correspondência entre todos os tipos {tipos} em ±{janela} dias"
    return False, [], [motivo]
