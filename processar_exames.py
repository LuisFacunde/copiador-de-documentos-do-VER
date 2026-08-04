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
    Path(dir_destino).mkdir(parents=True, exist_ok=True)


    try:
        pronunciarios = ler_pronunciarios()
    except (FileNotFoundError, ValueError) as exc:
        print(f"❌ {exc}")
        return

    total = len(pronunciarios)
    print(f"📋 Total de prontuários na planilha: {total}\n")

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

    imprimir_relatorio(estatisticas)


if __name__ == '__main__':
    processar_exames(verbose=True)
