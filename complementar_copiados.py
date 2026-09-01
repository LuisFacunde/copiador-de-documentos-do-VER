import sys
import argparse
import sqlite3
from collections import Counter
from datetime import datetime
from pathlib import Path
from src.config import (
    DIRS_EXAMES_ORIGEM,
    DIR_SSD_TI,
    BANCO_HISTORICO,
    BANCO_HISTORICO_COMPLETO,
)
from src.parser import extrair_info_arquivo_antigo, extrair_info_arquivo_novo
from src.filtros import e_arquivo_permitido
from src.relatorio import imprimir_relatorio
from src.historico import (
    inicializar_banco,
    obter_proximo_numero_lote,
    criar_lote,
    registrar_copia,
    finalizar_lote,
)
from src.logger import configurar_logger

reconfigure_stdout = getattr(sys.stdout, "reconfigure", None)
if callable(reconfigure_stdout):
    reconfigure_stdout(encoding="utf-8")


def coletar_prontuarios_copiados(*caminhos_banco: str) -> set[str]:
    prontuarios = set()

    for caminho in caminhos_banco:
        caminho_db = Path(caminho)
        if not caminho_db.exists():
            print(f"  ⚠️  Banco não encontrado (ignorado): {caminho}")
            continue

        try:
            conn = sqlite3.connect(str(caminho_db))
            cursor = conn.execute("SELECT DISTINCT prontuario FROM historico_copias")
            encontrados = {row[0] for row in cursor.fetchall()}
            print(f"  📋 {caminho_db.name}: {len(encontrados)} prontuários copiados")
            prontuarios |= encontrados
            conn.close()
        except Exception as exc:
            print(f"  ❌ Erro ao ler {caminho_db.name}: {exc}")

    return prontuarios


def coletar_arquivos_ja_copiados(*caminhos_banco: str) -> dict[str, set[str]]:
    arquivos_por_prontuario: dict[str, set[str]] = {}

    for caminho in caminhos_banco:
        caminho_db = Path(caminho)
        if not caminho_db.exists():
            continue

        try:
            conn = sqlite3.connect(str(caminho_db))
            cursor = conn.execute("SELECT prontuario, arquivo FROM historico_copias")
            for row in cursor.fetchall():
                pront, arq = row[0], row[1]
                if pront not in arquivos_por_prontuario:
                    arquivos_por_prontuario[pront] = set()
                arquivos_por_prontuario[pront].add(arq)
            conn.close()
        except Exception:
            continue

    return arquivos_por_prontuario


def _identificar_tipo_exame(arquivo: Path) -> str | None:

    data, prontuario, tipo = extrair_info_arquivo_novo(arquivo)
    if tipo is not None:
        return tipo

    data, prontuario, tipo = extrair_info_arquivo_antigo(arquivo)
    if tipo is not None:
        return tipo

    return None


def _coletar_exames_prontuario(
    prontuario: str,
    dirs_origem: list[str],
) -> list[dict]:
    exames = []
    paths_vistos = set()

    for dir_orig in dirs_origem:
        pasta = Path(dir_orig) / prontuario
        if not pasta.exists():
            continue

        try:
            for arquivo in pasta.iterdir():
                if not arquivo.is_file():
                    continue
                if not e_arquivo_permitido(arquivo):
                    continue

                caminho_str = str(arquivo)
                if caminho_str in paths_vistos:
                    continue
                paths_vistos.add(caminho_str)

                tipo = _identificar_tipo_exame(arquivo)
                if tipo is None:
                    continue

                data_exame = None
                d, _, _ = extrair_info_arquivo_novo(arquivo)
                if d is not None:
                    data_exame = d
                else:
                    d, _, _ = extrair_info_arquivo_antigo(arquivo)
                    if d is not None:
                        data_exame = d

                exames.append(
                    {
                        "path": arquivo,
                        "nome": arquivo.name,
                        "tipo": tipo,
                        "data": data_exame,
                    }
                )
        except (PermissionError, OSError):
            continue

    return exames


def complementar_copiados(
    dirs_origem: list[str] = DIRS_EXAMES_ORIGEM,
    dir_destino: str = DIR_SSD_TI,
    banco_registro: str = str(BANCO_HISTORICO_COMPLETO),
    forcar: bool = False,
    verbose: bool = True,
) -> None:

    print("\n" + "=" * 70)
    print("  🔄 COMPLEMENTAÇÃO DE EXAMES — PRONTUÁRIOS JÁ COPIADOS")
    print("=" * 70)

    prontuarios_copiados = coletar_prontuarios_copiados(
        str(BANCO_HISTORICO),
        str(BANCO_HISTORICO_COMPLETO),
    )

    if not prontuarios_copiados:
        print("  ⚠️  Nenhum prontuário encontrado nas bases de dados.")
        return

    total_prontuarios = len(prontuarios_copiados)
    print(f"  📋 Total de prontuários copiados (união das bases): {total_prontuarios}")

    arquivos_ja_copiados = coletar_arquivos_ja_copiados(
        str(BANCO_HISTORICO),
        str(BANCO_HISTORICO_COMPLETO),
    )
    total_arquivos_conhecidos = sum(len(v) for v in arquivos_ja_copiados.values())
    print(f"  📄 Arquivos já registrados nas bases: {total_arquivos_conhecidos}")

    conn = inicializar_banco(banco_registro)

    if not forcar:
        try:
            cursor = conn.execute("SELECT DISTINCT prontuario FROM historico_copias")
            ja_complementados = {row[0] for row in cursor.fetchall()}
        except Exception:
            ja_complementados = set()

        pendentes = sorted(prontuarios_copiados - ja_complementados)
        ignorados = total_prontuarios - len(pendentes)
        if ignorados > 0:
            print(f"  ⏭️  Prontuários já complementados (ignorados): {ignorados}")
    else:
        pendentes = sorted(prontuarios_copiados)
        print("  ⚠️  Modo --force ativo: reprocessando todos os prontuários")

    total_pendentes = len(pendentes)
    print(f"  📋 Prontuários pendentes de complementação: {total_pendentes}")

    if total_pendentes == 0:
        print("  ✅ Todos os prontuários já foram complementados.")
        if not forcar:
            print("     Use --force para reprocessar.")
        conn.close()
        return

    total = total_pendentes

    numero_lote = obter_proximo_numero_lote(conn)
    data_envio = datetime.now().strftime("%d-%m-%Y")
    nome_lote = f"Complementação {numero_lote} - {data_envio}"
    lote_id = criar_lote(conn, numero_lote, data_envio)

    pasta_lote = Path(dir_destino) / nome_lote
    pasta_lote.mkdir(parents=True, exist_ok=True)

    caminho_log = pasta_lote / f"log_complementacao_{numero_lote}.txt"
    logger = configurar_logger(caminho_log, numero_lote)

    logger.info("=" * 70)
    logger.info(f"  🔄 COMPLEMENTAÇÃO DE EXAMES — LOTE {numero_lote}")
    logger.info(f"  📅 {data_envio}")
    logger.info("=" * 70)
    logger.info(f"  📂 Origens: {dirs_origem}")
    logger.info(f"  📂 Destino: {pasta_lote}")
    logger.info(f"  🗄️  Banco de registro: {banco_registro}")
    logger.info(f"  📋 Prontuários copiados (total): {total_prontuarios}")
    logger.info(f"  📋 Prontuários pendentes: {total_pendentes}")
    logger.info(f"  📋 Total a processar: {total}")
    if forcar:
        logger.info("  ⚠️  Modo --force ativo")
    logger.info("")

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

    processados_sucesso = 0
    analisados = 0

    for analisados, prontuario in enumerate(pendentes, 1):
        prefixo = f"[{analisados}/{total}]"

        pasta_encontrada = False
        for dir_orig in dirs_origem:
            if (Path(dir_orig) / prontuario).exists():
                pasta_encontrada = True
                break

        if not pasta_encontrada:
            logger.info(f"{prefixo} Prontuário {prontuario} ⚠️  Pasta não encontrada")
            estatisticas["pasta_nao_encontrada"] += 1
            continue

        exames = _coletar_exames_prontuario(prontuario, dirs_origem)

        if not exames:
            logger.info(
                f"{prefixo} Prontuário {prontuario} 📭 "
                f"Sem exames RET/OCTPAPILA na pasta"
            )
            estatisticas["pasta_sem_arquivos"] += 1
            continue

        copiados_prontuario = 0
        pulados_prontuario = 0
        erros_prontuario = 0
        arquivos_copiados_info = []

        nomes_ja_copiados = arquivos_ja_copiados.get(prontuario, set())
        pendentes_copia = []

        for item in exames:
            if item["nome"] in nomes_ja_copiados:
                pulados_prontuario += 1
                continue
            pendentes_copia.append(item)

        if not pendentes_copia:
            continue

        pasta_destino = pasta_lote / prontuario
        pasta_destino.mkdir(parents=True, exist_ok=True)

        for item in pendentes_copia:
            arquivo_destino = pasta_destino / item["nome"]
            if arquivo_destino.exists():
                pulados_prontuario += 1
                continue

            try:
                import shutil

                shutil.copy2(item["path"], arquivo_destino)

                data_str = (
                    item["data"].strftime("%d/%m/%Y") if item.get("data") else "s/data"
                )
                logger.debug(
                    f"  ✅ {prontuario}/{item['nome']} "
                    f"({item['tipo']}) - {data_str}"
                )
                copiados_prontuario += 1
                arquivos_copiados_info.append(
                    {
                        "nome": item["nome"],
                        "tipo": item["tipo"],
                        "data": item["data"].isoformat() if item.get("data") else None,
                    }
                )
            except Exception as exc:
                logger.debug(f"  ❌ {prontuario}/{item['nome']}: {exc}")
                erros_prontuario += 1

        if copiados_prontuario > 0:
            processados_sucesso += 1
            estatisticas["pacientes_processados"] += 1

            for arq in arquivos_copiados_info:
                registrar_copia(
                    conn=conn,
                    lote_id=lote_id,
                    prontuario=prontuario,
                    arquivo=arq["nome"],
                    tipo_exame=arq.get("tipo"),
                    data_exame=arq.get("data"),
                )

        estatisticas["arquivos_copiados"] += copiados_prontuario
        estatisticas["arquivos_pulados"] += pulados_prontuario
        estatisticas["erros"] += erros_prontuario

        partes = []
        if copiados_prontuario:
            tipos = Counter(a["tipo"] for a in arquivos_copiados_info)
            detalhe_tipos = ", ".join(f"{v} {k}" for k, v in tipos.items())
            partes.append(f"{copiados_prontuario} copiado(s) ({detalhe_tipos})")
        if pulados_prontuario:
            partes.append(f"{pulados_prontuario} já existente(s)")
        if erros_prontuario:
            partes.append(f"{erros_prontuario} erro(s)")

        emoji = "✅" if copiados_prontuario else "❌"
        logger.info(f"{prefixo} Prontuário {prontuario} {emoji} {' | '.join(partes)}")

    status = "concluido" if estatisticas["erros"] == 0 else "concluido_com_erros"
    finalizar_lote(
        conn=conn,
        lote_id=lote_id,
        total_prontuarios=estatisticas["pacientes_processados"],
        total_arquivos=estatisticas["arquivos_copiados"],
        status=status,
    )

    info_lote = {
        "numero": numero_lote,
        "data_envio": data_envio,
        "pendentes": 0,
    }
    imprimir_relatorio(estatisticas, info_lote=info_lote, logger=logger)

    logger.info(f"\n  📁 Arquivos salvos em: {pasta_lote}")
    logger.info(f"  📁 Log salvo em: {caminho_log}")

    conn.close()


def main():
    parser = argparse.ArgumentParser(
        description="Complementador de Exames — Busca exames adicionais "
        "(RET/OCTPAPILA) para prontuários já copiados nas duas bases",
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
        "--banco",
        type=str,
        default=str(BANCO_HISTORICO_COMPLETO),
        help=f"Banco de dados para registrar cópias (padrão: {BANCO_HISTORICO_COMPLETO})",
    )

    parser.add_argument(
        "--force",
        action="store_true",
        default=False,
        help="Reprocessa todos os prontuários, mesmo os já complementados",
    )
    parser.add_argument(
        "--silencioso",
        action="store_true",
        default=False,
        help="Suprime saída detalhada no console",
    )
    args = parser.parse_args()

    complementar_copiados(
        dirs_origem=args.origem,
        dir_destino=args.destino,
        banco_registro=args.banco,
        forcar=args.force,
        verbose=not args.silencioso,
    )


if __name__ == "__main__":
    main()
