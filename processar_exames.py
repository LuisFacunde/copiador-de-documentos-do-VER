import sys
import argparse
from datetime import datetime
from pathlib import Path

reconfigure_stdout = getattr(sys.stdout, 'reconfigure', None)
if callable(reconfigure_stdout):
    reconfigure_stdout(encoding='utf-8')

from src.config import DIR_EXAMES_ORIGEM, DIR_EXAMES_DESTINO, LIMITE_PACIENTES_LOTE
from src.leitor_planilha import ler_prontuarios
from src.copiador import processar_prontuario
from src.relatorio import imprimir_relatorio
from src.historico import (
    inicializar_banco,
    obter_proximo_numero_lote,
    criar_lote,
    registrar_copia,
    finalizar_lote,
    listar_prontuarios_processados,
)
from src.logger import configurar_logger


def processar_exames(
    dir_origem: str = DIR_EXAMES_ORIGEM,
    dir_destino: str = DIR_EXAMES_DESTINO,
    forcar: bool = False,
    verbose: bool = True,
) -> None:
    conn = inicializar_banco()

    try:
        todos_prontuarios = ler_prontuarios()
    except (FileNotFoundError, ValueError) as exc:
        print(f"❌ {exc}")
        conn.close()
        return

    total_planilha = len(todos_prontuarios)
    print(f"📋 Total de prontuários na planilha: {total_planilha}")

    if forcar:
        print("⚠️  Modo --force ativo: reprocessando todos os prontuários")
        prontuarios_pendentes = todos_prontuarios
    else:
        ja_processados = listar_prontuarios_processados(conn)
        prontuarios_pendentes = [
            p for p in todos_prontuarios if p not in ja_processados
        ]
        excluidos = total_planilha - len(prontuarios_pendentes)
        if excluidos > 0:
            print(f"⏭  Prontuários já processados (ignorados): {excluidos}")

    total_pendentes = len(prontuarios_pendentes)
    if total_pendentes == 0:
        print("✅ Todos os prontuários já foram processados em lotes anteriores.")
        print("   Use --force para reprocessar.")
        conn.close()
        return

    # Aplicar limite do lote
    prontuarios_lote = prontuarios_pendentes[:LIMITE_PACIENTES_LOTE]
    restantes = total_pendentes - len(prontuarios_lote)

    # Criar lote
    numero_lote = obter_proximo_numero_lote(conn)
    data_envio = datetime.now().strftime('%d-%m-%Y')
    nome_lote = f"Lote {numero_lote} - {data_envio}"
    lote_id = criar_lote(conn, numero_lote, data_envio)

    # Criar pasta do lote
    pasta_lote = Path(dir_destino) / nome_lote
    pasta_lote.mkdir(parents=True, exist_ok=True)

    # Configurar logger (dentro da pasta do lote)
    caminho_log = pasta_lote / f"log_lote_{numero_lote}.txt"
    logger = configurar_logger(caminho_log, numero_lote)

    logger.info("=" * 70)
    logger.info(f"📦 LOTE {numero_lote} — {data_envio}")
    logger.info("=" * 70)
    logger.info(f"📋 Prontuários na planilha: {total_planilha}")
    logger.info(f"📋 Prontuários neste lote: {len(prontuarios_lote)}")
    logger.info(f"📋 Prontuários pendentes após este lote: {restantes}")
    if forcar:
        logger.info("⚠️  Modo --force ativo")
    logger.info("")

    # Processar prontuários
    estatisticas = {
        'pacientes_processados': 0,
        'pasta_nao_encontrada': 0,
        'pasta_sem_arquivos': 0,
        'exames_sem_correspondencia': 0,
        'arquivos_copiados': 0,
        'arquivos_pulados': 0,
        'arquivos_invalidos': 0,
        'arquivos_tipo_invalido': 0,
        'arquivos_fora_periodo': 0,
        'arquivos_fora_janela': 0,
        'erros': 0,
    }

    for i, prontuario in enumerate(prontuarios_lote, 1):
        logger.info(
            f"[{i}/{len(prontuarios_lote)}] Processando prontuário: {prontuario}"
        )

        resultado = processar_prontuario(
            prontuario=prontuario,
            dir_origem=dir_origem,
            dir_destino=str(pasta_lote),
            logger=logger,
            verbose=verbose,
        )

        motivo = resultado['motivo_exclusao']
        if motivo:
            estatisticas[motivo] += 1
        else:
            estatisticas['pacientes_processados'] += 1

        estatisticas['arquivos_copiados']      += resultado['copiados']
        estatisticas['arquivos_pulados']       += resultado['pulados']
        estatisticas['arquivos_invalidos']     += resultado['invalidos']
        estatisticas['arquivos_tipo_invalido'] += resultado['tipo_invalido']
        estatisticas['arquivos_fora_periodo']  += resultado['fora_periodo']
        estatisticas['arquivos_fora_janela']   += resultado['fora_janela']
        estatisticas['erros']                  += resultado['erros']

        # Registrar arquivos copiados no histórico
        for arq in resultado.get('arquivos_copiados', []):
            registrar_copia(
                conn=conn,
                lote_id=lote_id,
                prontuario=prontuario,
                arquivo=arq['nome'],
                tipo_exame=arq.get('tipo'),
                data_exame=arq.get('data'),
            )

    # Finalizar lote
    status = (
        'concluido' if estatisticas['erros'] == 0
        else 'concluido_com_erros'
    )
    finalizar_lote(
        conn=conn,
        lote_id=lote_id,
        total_prontuarios=estatisticas['pacientes_processados'],
        total_arquivos=estatisticas['arquivos_copiados'],
        status=status,
    )

    # Relatório
    info_lote = {
        'numero': numero_lote,
        'data_envio': data_envio,
        'pendentes': restantes,
    }
    imprimir_relatorio(estatisticas, info_lote=info_lote, logger=logger)

    logger.info(f"\n📁 Arquivos salvos em: {pasta_lote}")
    logger.info(f"📄 Log salvo em: {caminho_log}")

    conn.close()


def main():
    parser = argparse.ArgumentParser(
        description='Processador de Exames — Cópia com filtros e lotes',
    )
    parser.add_argument(
        '--force',
        action='store_true',
        default=False,
        help='Reprocessa prontuários mesmo que já constem no histórico',
    )
    parser.add_argument(
        '--origem',
        type=str,
        default=DIR_EXAMES_ORIGEM,
        help=f'Diretório de origem dos exames (padrão: {DIR_EXAMES_ORIGEM})',
    )
    parser.add_argument(
        '--destino',
        type=str,
        default=DIR_EXAMES_DESTINO,
        help=f'Diretório de destino das cópias (padrão: {DIR_EXAMES_DESTINO})',
    )
    parser.add_argument(
        '--silencioso',
        action='store_true',
        default=False,
        help='Suprime saída detalhada no console',
    )

    args = parser.parse_args()

    processar_exames(
        dir_origem=args.origem,
        dir_destino=args.destino,
        forcar=args.force,
        verbose=not args.silencioso,
    )


if __name__ == '__main__':
    main()
