"""
processar_exames.py — Ponto de entrada e orquestrador.

Este arquivo NÃO contém regras de negócio.
Ele apenas:
  1. Lê a lista de prontuários da planilha Excel  (src/leitor_planilha.py)
  2. Itera cada prontuário, copia os PDFs válidos  (src/copiador.py)
  3. Acumula estatísticas e exibe o relatório final (src/relatorio.py)

Para ajustar caminhos ou critérios, edite src/config.py.
"""
from pathlib import Path

from src.config import DIR_EXAMES_ORIGEM, DIR_EXAMES_DESTINO
from src.leitor_planilha import ler_pronunciarios
from src.copiador import processar_pronunciario
from src.relatorio import imprimir_relatorio


def processar_exames(
    dir_origem: str = DIR_EXAMES_ORIGEM,
    dir_destino: str = DIR_EXAMES_DESTINO,
    verbose: bool = True,
) -> None:
    """
    Fluxo principal: lê prontuários da planilha, processa e copia PDFs válidos.

    Parâmetros:
        dir_origem  : diretório raiz com subpastas de prontuários
        dir_destino : diretório de saída (criado automaticamente)
        verbose     : exibir detalhes de cada arquivo processado
    """
    Path(dir_destino).mkdir(parents=True, exist_ok=True)

    # 1. Ler lista de prontuários da planilha
    try:
        pronunciarios = ler_pronunciarios()
    except (FileNotFoundError, ValueError) as exc:
        print(f"❌ {exc}")
        return

    total = len(pronunciarios)
    print(f"📋 Total de prontuários na planilha: {total}\n")

    # 2. Acumulador de estatísticas
    estatisticas = {
        'pacientes_processados': 0,
        'pacientes_sem_exames': 0,
        'arquivos_copiados': 0,
        'arquivos_invalidos': 0,
        'arquivos_tipo_invalido': 0,
        'arquivos_fora_periodo': 0,
        'arquivos_fora_janela': 0,
        'erros': 0,
    }

    # 3. Processar cada prontuário
    for pronunciario in pronunciarios:
        resultado = processar_pronunciario(
            pronunciario=pronunciario,
            dir_origem=dir_origem,
            dir_destino=dir_destino,
            verbose=verbose,
        )

        if resultado['sem_exames']:
            estatisticas['pacientes_sem_exames'] += 1
        else:
            estatisticas['pacientes_processados'] += 1

        estatisticas['arquivos_copiados']      += resultado['copiados']
        estatisticas['arquivos_invalidos']     += resultado['invalidos']
        estatisticas['arquivos_tipo_invalido'] += resultado['tipo_invalido']
        estatisticas['arquivos_fora_periodo']  += resultado['fora_periodo']
        estatisticas['arquivos_fora_janela']   += resultado['fora_janela']
        estatisticas['erros']                  += resultado['erros']

    # 4. Relatório final 
    imprimir_relatorio(estatisticas)


if __name__ == '__main__':
    processar_exames(verbose=True)
