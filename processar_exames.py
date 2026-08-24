import sys
import argparse
from datetime import datetime
from pathlib import Path

reconfigure_stdout = getattr(sys.stdout, 'reconfigure', None)
if callable(reconfigure_stdout):
    reconfigure_stdout(encoding='utf-8')

from src.perfil import carregar_perfil, listar_series, PerfilSerie
from src.leitor_planilha import ler_prontuarios
from src.copiador import processar_prontuario
from src.relatorio import imprimir_relatorio
from src.historico import (
    inicializar_banco,
    obter_proximo_numero_lote,
    criar_lote,
    registrar_copia,
    registrar_descarte,
    finalizar_lote,
    listar_prontuarios_processados,
)
from src.logger import configurar_logger


def processar_exames(
    perfil: PerfilSerie,
    forcar: bool = False,
    verbose: bool = True,
) -> None:
    conn = inicializar_banco(perfil.banco_historico)

    try:
        todos_prontuarios = ler_prontuarios(
            caminho=perfil.planilha,
            aba=perfil.aba_planilha,
            coluna=perfil.coluna_prontuario,
        )
    except (FileNotFoundError, ValueError) as exc:
        print(f"  ❌ {exc}")
        conn.close()
        return

    total_planilha = len(todos_prontuarios)
    print(f"  📋 Total de prontuários na planilha: {total_planilha}")

    if forcar:
        print("  ⚠️  Modo --force ativo: reprocessando todos os prontuários")
        prontuarios_pendentes = todos_prontuarios
    else:
        ja_processados = listar_prontuarios_processados(conn)
        prontuarios_pendentes = [
            p for p in todos_prontuarios if p not in ja_processados
        ]
        excluidos = total_planilha - len(prontuarios_pendentes)
        if excluidos > 0:
            print(f"  ⏭️ Prontuários já processados (ignorados): {excluidos}")

    total_pendentes = len(prontuarios_pendentes)
    if total_pendentes == 0:
        print("  ✅ Todos os prontuários já foram processados em lotes anteriores.")
        print("     Use --force para reprocessar.")
        conn.close()
        return

    meta_lote = perfil.limite_pacientes_lote

    # Criar lote
    numero_lote = obter_proximo_numero_lote(conn)
    data_envio = datetime.now().strftime('%d-%m-%Y')
    nome_lote = f"Lote {numero_lote} - {data_envio}"
    lote_id = criar_lote(conn, numero_lote, data_envio)

    # Criar pasta do lote
    pasta_lote = Path(perfil.dir_destino) / nome_lote
    pasta_lote.mkdir(parents=True, exist_ok=True)

    # Configurar logger (dentro da pasta do lote)
    caminho_log = pasta_lote / f"log_lote_{numero_lote}.txt"
    logger = configurar_logger(caminho_log, numero_lote)

    logger.info("=" * 70)
    logger.info(f"  📦 LOTE {numero_lote} - {data_envio}  [{perfil.nome}]")
    logger.info("=" * 70)
    logger.info(f"  📋 Prontuários na planilha: {total_planilha}")
    logger.info(f"  📋 Prontuários pendentes: {total_pendentes}")
    logger.info(f"  🎯 Meta de pacientes copiados neste lote: {meta_lote}")
    if forcar:
        logger.info("  ⚠️  Modo --force ativo")
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

    copiados_sucesso = 0
    prontuarios_analisados = 0

    for prontuario in prontuarios_pendentes:
        prontuarios_analisados += 1
        indice_exibicao = min(copiados_sucesso + 1, meta_lote)

        resultado = processar_prontuario(
            prontuario=prontuario,
            perfil=perfil,
            dir_destino=str(pasta_lote),
            indice=indice_exibicao,
            total=meta_lote,
            logger=logger,
            verbose=verbose,
        )

        motivo = resultado['motivo_exclusao']
        if motivo:
            estatisticas[motivo] += 1
            registrar_descarte(
                conn=conn,
                lote_id=lote_id,
                prontuario=prontuario,
                motivo=motivo,
            )
        else:
            copiados_sucesso += 1
            estatisticas['pacientes_processados'] += 1
            for arq in resultado.get('arquivos_copiados', []):
                registrar_copia(
                    conn=conn,
                    lote_id=lote_id,
                    prontuario=prontuario,
                    arquivo=arq['nome'],
                    tipo_exame=arq.get('tipo'),
                    data_exame=arq.get('data'),
                )

        estatisticas['arquivos_copiados']      += resultado['copiados']
        estatisticas['arquivos_pulados']       += resultado['pulados']
        estatisticas['arquivos_invalidos']     += resultado['invalidos']
        estatisticas['arquivos_tipo_invalido'] += resultado['tipo_invalido']
        estatisticas['arquivos_fora_periodo']  += resultado['fora_periodo']
        estatisticas['arquivos_fora_janela']   += resultado['fora_janela']
        estatisticas['erros']                  += resultado['erros']

        if copiados_sucesso >= meta_lote:
            break

    restantes = total_pendentes - prontuarios_analisados

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

    logger.info(f"\n  📁 Arquivos salvos em: {pasta_lote}")
    logger.info(f"  📁 Log salvo em: {caminho_log}")

    conn.close()


def main():
    series_disponiveis = listar_series()

    parser = argparse.ArgumentParser(
        description='Processador de Exames — Cópia com filtros e lotes',
    )
    parser.add_argument(
        'serie',
        nargs='?',
        default=series_disponiveis[0] if len(series_disponiveis) == 1 else None,
        help=(
            f'Nome da série a processar. '
            f'Disponíveis: {series_disponiveis or "(nenhuma)"}'
        ),
    )
    parser.add_argument(
        '--force',
        action='store_true',
        default=False,
        help='Reprocessa prontuários mesmo que já constem no histórico',
    )
    parser.add_argument(
        '--silencioso',
        action='store_true',
        default=False,
        help='Suprime saída detalhada no console',
    )
    parser.add_argument(
        '--listar-series',
        action='store_true',
        default=False,
        help='Lista as séries disponíveis e encerra',
    )

    args = parser.parse_args()

    if args.listar_series:
        if series_disponiveis:
            print("Séries disponíveis:")
            for s in series_disponiveis:
                print(f"  • {s}")
        else:
            print("Nenhuma série encontrada em series/")
        return

    if not args.serie:
        parser.error(
            f"Informe o nome da série. Disponíveis: {series_disponiveis or '(nenhuma)'}\n"
            f"Uso: python processar_exames.py <serie> [--force] [--silencioso]"
        )

    try:
        perfil = carregar_perfil(args.serie)
    except FileNotFoundError as exc:
        print(f"  ❌ {exc}")
        sys.exit(1)

    print(f"  🔬 Série: {perfil.nome}")
    processar_exames(
        perfil=perfil,
        forcar=args.force,
        verbose=not args.silencioso,
    )


if __name__ == '__main__':
    main()
