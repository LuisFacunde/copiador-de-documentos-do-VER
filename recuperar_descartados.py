"""
Recuperador de Prontuários Descartados.

Lê prontuários da tabela 'prontuarios_descartados' que ainda não foram
recuperados, reprocessa-os usando a busca em dois formatos (antigo + novo),
e registra os recuperados com sucesso na tabela 'prontuarios_recuperados'.
"""

import sys
import argparse
from datetime import datetime
from pathlib import Path

reconfigure_stdout = getattr(sys.stdout, "reconfigure", None)
if callable(reconfigure_stdout):
    reconfigure_stdout(encoding="utf-8")

from src.config import (
    DIRS_EXAMES_ORIGEM,
    DIR_SSD_TI,
    BANCO_HISTORICO,
    LIMITE_PACIENTES_LOTE,
)
from src.copiador import processar_prontuario
from src.relatorio import imprimir_relatorio
from src.historico import (
    inicializar_banco,
    obter_proximo_numero_lote,
    criar_lote,
    registrar_copia,
    registrar_descarte,
    finalizar_lote,
    registrar_recuperacao,
)
from src.logger import configurar_logger


def recuperar_descartados(
    dirs_origem: list[str] = DIRS_EXAMES_ORIGEM,
    dir_destino: str = DIR_SSD_TI,
    banco: str = str(BANCO_HISTORICO),
    forcar: bool = False,
    limite: int | None = LIMITE_PACIENTES_LOTE,
    verbose: bool = True,
) -> None:
    conn = inicializar_banco(banco)

    # ── Buscar prontuários descartados e já recuperados ──
    try:
        cursor = conn.execute(
            "SELECT DISTINCT prontuario FROM prontuarios_descartados"
        )
        todos_descartados = [row[0] for row in cursor.fetchall()]

        cursor = conn.execute(
            "SELECT DISTINCT prontuario FROM prontuarios_recuperados"
        )
        ja_recuperados = set(row[0] for row in cursor.fetchall())
    except Exception as exc:
        print(f"  ❌ Erro ao consultar banco: {exc}")
        conn.close()
        return

    total_descartados = len(todos_descartados)
    total_ja_recuperados = len(ja_recuperados)

    if forcar:
        prontuarios_pendentes = todos_descartados
    else:
        prontuarios_pendentes = [p for p in todos_descartados if p not in ja_recuperados]

    total_pendentes = len(prontuarios_pendentes)

    print(f"  📋 Total de prontuários descartados no banco: {total_descartados}")
    print(f"  ⏭️  Prontuários descartados já recuperados/copiados: {total_ja_recuperados}")
    print(f"  📋 Prontuários pendentes de recuperação: {total_pendentes}")

    if total_pendentes == 0:
        print("  ✅ Todos os prontuários descartados já foram recuperados/copiados.")
        if not forcar:
            print("     Use --force para reprocessar os já recuperados.")
        conn.close()
        return

    meta = min(limite, total_pendentes) if limite else total_pendentes

    # ── Criar lote de recuperação ──
    numero_lote = obter_proximo_numero_lote(conn)
    data_envio = datetime.now().strftime("%d-%m-%Y")
    nome_lote = f"Recuperação {numero_lote} - {data_envio}"
    lote_id = criar_lote(conn, numero_lote, data_envio)

    pasta_lote = Path(dir_destino) / nome_lote
    pasta_lote.mkdir(parents=True, exist_ok=True)

    caminho_log = pasta_lote / f"log_recuperacao_{numero_lote}.txt"
    logger = configurar_logger(caminho_log, numero_lote)

    logger.info("=" * 70)
    logger.info(f"  🔄 RECUPERAÇÃO DE DESCARTADOS — LOTE {numero_lote}")
    logger.info(f"  📅 {data_envio}")
    logger.info("=" * 70)
    logger.info(f"  📋 Total de prontuários descartados: {total_descartados}")
    logger.info(f"  ⏭️  Prontuários já recuperados/copiados: {total_ja_recuperados}")
    logger.info(f"  📋 Prontuários pendentes de recuperação: {total_pendentes}")
    logger.info(f"  🎯 Meta de pacientes recuperados neste lote: {meta}")
    logger.info(f"  📂 Origem: {dirs_origem}")
    logger.info(f"  🗄️  Banco: {banco}")
    if forcar:
        logger.info("  ⚠️  Modo --force ativo (reprocessando inclusive os já recuperados)")
    logger.info("")

    # ── Estatísticas ──
    estatisticas = {
        "pacientes_processados": 0,
        "pasta_nao_encontrada": 0,
        "pasta_sem_arquivos": 0,
        "exames_sem_correspondencia": 0,
        "arquivos_copiados": 0,
        "arquivos_pulados": 0,
        "arquivos_invalidos": 0,
        "arquivos_tipo_invalido": 0,
        "arquivos_fora_periodo": 0,
        "arquivos_fora_janela": 0,
        "erros": 0,
    }

    recuperados = 0
    analisados = 0

    # ── Processar cada prontuário ──
    for prontuario in prontuarios_pendentes:
        if recuperados >= meta:
            break

        analisados += 1
        indice_exibicao = min(recuperados + 1, meta)

        resultado = processar_prontuario(
            prontuario=prontuario,
            dirs_origem=dirs_origem,
            dir_destino=str(pasta_lote),
            indice=indice_exibicao,
            total=meta,
            logger=logger,
            verbose=verbose,
        )

        motivo = resultado["motivo_exclusao"]

        if motivo:
            # Continua descartado — não registra novamente
            estatisticas[motivo] += 1
        else:
            # ✅ Recuperado com sucesso
            recuperados += 1
            estatisticas["pacientes_processados"] += 1

            for arq in resultado.get("arquivos_copiados", []):
                registrar_copia(
                    conn=conn,
                    lote_id=lote_id,
                    prontuario=prontuario,
                    arquivo=arq["nome"],
                    tipo_exame=arq.get("tipo"),
                    data_exame=arq.get("data"),
                )

            try:
                registrar_recuperacao(conn, lote_id, prontuario)
            except Exception as exc:
                logger.error(
                    f"  Erro ao registrar recuperação de {prontuario}: {exc}"
                )

        estatisticas["arquivos_copiados"] += resultado["copiados"]
        estatisticas["arquivos_pulados"] += resultado["pulados"]
        estatisticas["arquivos_invalidos"] += resultado["invalidos"]
        estatisticas["arquivos_tipo_invalido"] += resultado["tipo_invalido"]
        estatisticas["arquivos_fora_periodo"] += resultado["fora_periodo"]
        estatisticas["arquivos_fora_janela"] += resultado["fora_janela"]
        estatisticas["erros"] += resultado["erros"]

    restantes = total_pendentes - analisados

    # ── Finalizar lote ──
    status = "concluido" if estatisticas["erros"] == 0 else "concluido_com_erros"
    finalizar_lote(
        conn=conn,
        lote_id=lote_id,
        total_prontuarios=estatisticas["pacientes_processados"],
        total_arquivos=estatisticas["arquivos_copiados"],
        status=status,
    )

    # ── Relatório ──
    info_lote = {
        "numero": numero_lote,
        "data_envio": data_envio,
        "pendentes": restantes,
    }
    imprimir_relatorio(estatisticas, info_lote=info_lote, logger=logger)

    logger.info(f"\n  📁 Arquivos salvos em: {pasta_lote}")
    logger.info(f"  📁 Log salvo em: {caminho_log}")

    conn.close()


def main():
    parser = argparse.ArgumentParser(
        description="Recuperador de Prontuários Descartados — "
        "Reprocessa descartados e registra recuperações",
    )
    parser.add_argument(
        "--banco",
        type=str,
        default=str(BANCO_HISTORICO),
        help=f"Caminho do banco de dados (padrão: {BANCO_HISTORICO})",
    )
    parser.add_argument(
        "--origem",
        type=str,
        nargs="+",
        default=DIRS_EXAMES_ORIGEM,
        help=f"Diretório(s) de origem dos exames (padrão: {DIRS_EXAMES_ORIGEM})",
    )
    parser.add_argument(
        "--destino",
        type=str,
        default=DIR_SSD_TI,
        help=f"Diretório de destino das cópias (padrão: {DIR_SSD_TI})",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        default=False,
        help="Reprocessa todos os descartados, mesmo os já recuperados",
    )
    parser.add_argument(
        "--limite",
        type=int,
        default=LIMITE_PACIENTES_LOTE,
        help=f"Número máximo de prontuários a recuperar nesta execução (padrão: {LIMITE_PACIENTES_LOTE})",
    )
    parser.add_argument(
        "--silencioso",
        action="store_true",
        default=False,
        help="Suprime saída detalhada no console",
    )
    args = parser.parse_args()

    recuperar_descartados(
        dirs_origem=args.origem,
        dir_destino=args.destino,
        banco=args.banco,
        forcar=args.force,
        limite=args.limite,
        verbose=not args.silencioso,
    )


if __name__ == "__main__":
    main()
