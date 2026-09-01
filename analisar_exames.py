import sys
import argparse
from collections import defaultdict
from datetime import datetime
from pathlib import Path

reconfigure_stdout = getattr(sys.stdout, "reconfigure", None)
if callable(reconfigure_stdout):
    reconfigure_stdout(encoding="utf-8")

from src.config import (
    DIR_EXAMES_GERAL,
    DIR_RECUPERACAO_ARQUIVOSFAV,
    BANCO_HISTORICO,
    LIMITE_PACIENTES_LOTE,
    PLANILHA_PRONTUARIOS,
)
from src.leitor_planilha import ler_prontuarios
from src.parser import extrair_info_arquivo_antigo, extrair_info_arquivo_novo
from src.filtros import (
    e_arquivo_permitido,
    agrupar_exames_antigos,
    coletar_exames_novos,
    agrupar_por_tipo,
    avaliar_criterio_paciente,
)
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


def descobrir_prontuarios(
    dir_origem: str, verbose: bool = True
) -> dict[str, list[Path]]:
    import os

    pasta = Path(dir_origem)
    if not pasta.exists():
        print(f"  ❌ Pasta de origem não encontrada: {dir_origem}")
        return {}

    agrupados: dict[str, list[Path]] = defaultdict(list)
    total_arquivos = 0
    total_ignorados = 0

    if verbose:
        print(f"  🔍 Varrendo recursivamente: {dir_origem}")
        print(f"     (progresso a cada 1.000 arquivos analisados)", flush=True)

    def _varrer(caminho: str) -> None:
        nonlocal total_arquivos, total_ignorados
        try:
            with os.scandir(caminho) as it:
                for entrada in it:
                    try:
                        if entrada.is_dir(follow_symlinks=False):
                            _varrer(entrada.path)
                        elif entrada.is_file(follow_symlinks=False):
                            arquivo = Path(entrada.path)
                            if not e_arquivo_permitido(arquivo):
                                continue

                            total_arquivos += 1

                            if verbose and total_arquivos % 1000 == 0:
                                print(
                                    f"     ... {total_arquivos} arquivos analisados, "
                                    f"{len(agrupados)} prontuários encontrados",
                                    flush=True,
                                )

                            data, prontuario, tipo = extrair_info_arquivo_novo(arquivo)
                            if prontuario is None:

                                data, prontuario, tipo = extrair_info_arquivo_antigo(
                                    arquivo
                                )

                            if prontuario is None:
                                total_ignorados += 1
                                continue

                            agrupados[prontuario].append(arquivo)
                    except (PermissionError, OSError):
                        continue
        except (PermissionError, OSError) as exc:
            if verbose:
                print(f"     ⚠️  Erro ao acessar {caminho}: {exc}")

    _varrer(str(pasta))

    if verbose:
        print(f"  📁 Arquivos analisados: {total_arquivos}")
        print(f"  📭 Arquivos sem prontuário identificável: {total_ignorados}")
        print(f"  👤 Prontuários distintos identificados: {len(agrupados)}")

    return dict(agrupados)


def analisar_exames(
    dir_origem: str = DIR_EXAMES_GERAL,
    dir_destino: str = DIR_RECUPERACAO_ARQUIVOSFAV,
    banco: str = str(BANCO_HISTORICO),
    forcar: bool = False,
    limite: int | None = LIMITE_PACIENTES_LOTE,
    verbose: bool = True,
) -> None:
    conn = inicializar_banco(banco)

    print("\n" + "=" * 70)
    print("  🔎 ANÁLISE DE EXAMES — VARREDURA RECURSIVA")
    print("=" * 70)

    prontuarios_arquivos = descobrir_prontuarios(dir_origem, verbose=verbose)

    if not prontuarios_arquivos:
        print("  ⚠️  Nenhum prontuário encontrado na pasta de origem.")
        conn.close()
        return

    try:
        prontuarios_planilha = set(ler_prontuarios())
        total_antes = len(prontuarios_arquivos)
        prontuarios_arquivos = {
            p: arqs
            for p, arqs in prontuarios_arquivos.items()
            if p in prontuarios_planilha
        }
        filtrados = total_antes - len(prontuarios_arquivos)
        if verbose:
            print(f"  📋 Prontuários na planilha: {len(prontuarios_planilha)}")
            print(
                f"  ✅ Prontuários com match na planilha: {len(prontuarios_arquivos)}"
            )
            if filtrados > 0:
                print(
                    f"  ⏭️  Prontuários ignorados (não estão na planilha): {filtrados}"
                )
    except FileNotFoundError as exc:
        print(f"  ❌ {exc}")
        conn.close()
        return
    except Exception as exc:
        print(f"  ⚠️  Erro ao ler planilha: {exc}")
        print("     Continuando sem filtro de planilha...")

    if not prontuarios_arquivos:
        print("  ⚠️  Nenhum prontuário encontrado coincide com a planilha.")
        conn.close()
        return

    if not forcar:
        try:
            cursor = conn.execute(
                "SELECT DISTINCT prontuario FROM prontuarios_recuperados"
            )
            ja_recuperados = set(row[0] for row in cursor.fetchall())
        except Exception:
            ja_recuperados = set()

        try:
            cursor = conn.execute("SELECT DISTINCT prontuario FROM historico_copias")
            ja_copiados = set(row[0] for row in cursor.fetchall())
        except Exception:
            ja_copiados = set()

        ja_processados = ja_recuperados | ja_copiados
        total_antes = len(prontuarios_arquivos)

        prontuarios_arquivos = {
            p: arqs
            for p, arqs in prontuarios_arquivos.items()
            if p not in ja_processados
        }

        ignorados = total_antes - len(prontuarios_arquivos)
        if ignorados > 0:
            print(f"  ⏭️  Prontuários já recuperados/copiados (ignorados): {ignorados}")
    else:
        print("  ⚠️  Modo --force ativo: reprocessando todos os prontuários")

    total_pendentes = len(prontuarios_arquivos)
    print(f"  📋 Prontuários pendentes de análise: {total_pendentes}")

    if total_pendentes == 0:
        print("  ✅ Todos os prontuários já foram processados.")
        if not forcar:
            print("     Use --force para reprocessar.")
        conn.close()
        return

    meta = min(limite, total_pendentes) if limite else total_pendentes

    numero_lote = obter_proximo_numero_lote(conn)
    data_envio = datetime.now().strftime("%d-%m-%Y")
    nome_lote = f"Análise {numero_lote} - {data_envio}"
    lote_id = criar_lote(conn, numero_lote, data_envio)

    pasta_lote = Path(dir_destino) / nome_lote
    pasta_lote.mkdir(parents=True, exist_ok=True)

    caminho_log = pasta_lote / f"log_analise_{numero_lote}.txt"
    logger = configurar_logger(caminho_log, numero_lote)

    logger.info("=" * 70)
    logger.info(f"  🔎 ANÁLISE DE EXAMES — LOTE {numero_lote}")
    logger.info(f"  📅 {data_envio}")
    logger.info("=" * 70)
    logger.info(f"  📂 Origem: {dir_origem}")
    logger.info(f"  📂 Destino: {pasta_lote}")
    logger.info(f"  🗄️  Banco: {banco}")
    logger.info(f"  📋 Prontuários pendentes: {total_pendentes}")
    logger.info(f"  🎯 Meta neste lote: {meta}")
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

    copiados_sucesso = 0
    analisados = 0

    for prontuario, arquivos in prontuarios_arquivos.items():
        if copiados_sucesso >= meta:
            break

        analisados += 1
        indice_exibicao = min(copiados_sucesso + 1, meta)

        resultado = _processar_prontuario_direto(
            prontuario=prontuario,
            arquivos=arquivos,
            dir_destino=str(pasta_lote),
            indice=indice_exibicao,
            total=meta,
            logger=logger,
            verbose=verbose,
        )

        motivo = resultado["motivo_exclusao"]

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
                logger.error(f"  Erro ao registrar recuperação de {prontuario}: {exc}")

        estatisticas["arquivos_copiados"] += resultado["copiados"]
        estatisticas["arquivos_pulados"] += resultado["pulados"]
        estatisticas["arquivos_invalidos"] += resultado["invalidos"]
        estatisticas["arquivos_tipo_invalido"] += resultado["tipo_invalido"]
        estatisticas["arquivos_fora_periodo"] += resultado["fora_periodo"]
        estatisticas["arquivos_fora_janela"] += resultado["fora_janela"]
        estatisticas["erros"] += resultado["erros"]

    restantes = total_pendentes - analisados

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
        "pendentes": restantes,
    }
    imprimir_relatorio(estatisticas, info_lote=info_lote, logger=logger)

    logger.info(f"\n  📁 Arquivos salvos em: {pasta_lote}")
    logger.info(f"  📁 Log salvo em: {caminho_log}")

    conn.close()


def _processar_prontuario_direto(
    prontuario: str,
    arquivos: list[Path],
    dir_destino: str,
    indice: int = 0,
    total: int = 0,
    logger=None,
    verbose: bool = True,
) -> dict:
    import shutil
    from collections import Counter

    stats = {
        "copiados": 0,
        "pulados": 0,
        "invalidos": 0,
        "tipo_invalido": 0,
        "fora_periodo": 0,
        "fora_janela": 0,
        "erros": 0,
        "motivo_exclusao": None,
        "arquivos_copiados": [],
    }

    prefixo = f"[{indice}/{total}]" if total else ""

    def _log(nivel: str, msg: str) -> None:
        if logger:
            getattr(logger, nivel)(msg)
        elif verbose:
            print(msg)

    def _resumo(emoji: str, descricao: str) -> None:
        _log("info", f"{prefixo} Prontuário {prontuario} {emoji} {descricao}")

    if not arquivos:
        _resumo("📭", "Sem arquivos de exame")
        stats["motivo_exclusao"] = "pasta_sem_arquivos"
        return stats

    try:
        agrupados_antigos = agrupar_exames_antigos(
            arquivos,
            logger=logger,
            verbose=verbose,
        )

        tem_antigos = bool(agrupados_antigos["RET"]) or bool(
            agrupados_antigos["OCTPAPILA"]
        )

        if tem_antigos:
            agrupados = agrupados_antigos
        else:
            agrupados = agrupar_por_tipo(
                arquivos,
                logger=logger,
                verbose=verbose,
            )
    except Exception as exc:
        _resumo("❌", f"Erro ao analisar exames: {exc}")
        stats["erros"] += 1
        return stats

    stats["invalidos"] += agrupados["_invalidos"]
    stats["tipo_invalido"] += agrupados["_tipo_invalido"]
    stats["fora_periodo"] += agrupados["_fora_periodo"]

    aprovado, para_copiar, motivos_reprovacao = avaliar_criterio_paciente(
        ret_lista=agrupados["RET"],
        oct_lista=agrupados["OCTPAPILA"],
        logger=logger,
        verbose=verbose,
    )

    if aprovado and tem_antigos:
        tipos_aprovados = {item["tipo"] for item in para_copiar}
        exames_novos = coletar_exames_novos(
            arquivos,
            tipos_aprovados=tipos_aprovados,
            logger=logger,
            verbose=verbose,
        )
        paths_ja_incluidos = {str(item["path"]) for item in para_copiar}
        for exame_novo in exames_novos:
            if str(exame_novo["path"]) not in paths_ja_incluidos:
                para_copiar.append(exame_novo)
                paths_ja_incluidos.add(str(exame_novo["path"]))

    total_arquivos_analisados = (
        len(agrupados["RET"])
        + len(agrupados["OCTPAPILA"])
        + agrupados["_invalidos"]
        + agrupados["_tipo_invalido"]
        + agrupados["_fora_periodo"]
    )

    if not aprovado or not para_copiar:
        if total_arquivos_analisados == 0:
            _resumo("📭", "Sem arquivos de exame válidos")
            stats["motivo_exclusao"] = "pasta_sem_arquivos"
        else:
            if agrupados["RET"] and agrupados["OCTPAPILA"]:
                stats["fora_janela"] += len(agrupados["RET"]) + len(
                    agrupados["OCTPAPILA"]
                )

            motivos = list(motivos_reprovacao)
            if agrupados["_fora_periodo"]:
                motivos.append(f"{agrupados['_fora_periodo']} fora do período")
            if stats["fora_janela"]:
                motivos.append(f"{stats['fora_janela']} fora da janela")
            if agrupados["_tipo_invalido"]:
                motivos.append(f"{agrupados['_tipo_invalido']} tipo inválido")
            if agrupados["_invalidos"]:
                motivos.append(f"{agrupados['_invalidos']} nome inválido")
            detalhe = f" ({', '.join(motivos)})" if motivos else ""
            _resumo("📭", f"Nenhum exame atende aos filtros{detalhe}")
            stats["motivo_exclusao"] = "exames_sem_correspondencia"
        return stats

    pasta_destino = Path(dir_destino) / prontuario
    pasta_destino.mkdir(parents=True, exist_ok=True)

    for item in para_copiar:
        arquivo_destino = pasta_destino / item["nome"]
        if arquivo_destino.exists():
            _log(
                "debug",
                f"  ⏭️  {prontuario}/{item['nome']} " f"({item['tipo']}) - já copiado",
            )
            stats["pulados"] += 1
            continue
        try:
            shutil.copy2(item["path"], arquivo_destino)
            _log(
                "debug",
                f"  ✅ {prontuario}/{item['nome']} "
                f"({item['tipo']}) - {item['data'].strftime('%d/%m/%Y')}",
            )
            stats["copiados"] += 1
            stats["arquivos_copiados"].append(
                {
                    "nome": item["nome"],
                    "tipo": item["tipo"],
                    "data": item["data"].isoformat() if item.get("data") else None,
                }
            )
        except Exception as exc:
            _log("debug", f"  ❌ {prontuario}/{item['nome']}: {exc}")
            stats["erros"] += 1

    partes = []
    if stats["copiados"]:
        tipos = Counter(a["tipo"] for a in stats["arquivos_copiados"])
        detalhe_tipos = ", ".join(f"{v} {k}" for k, v in tipos.items())
        partes.append(f"{stats['copiados']} copiado(s) ({detalhe_tipos})")
    if stats["pulados"]:
        partes.append(f"{stats['pulados']} já existente(s)")
    if stats["erros"]:
        partes.append(f"{stats['erros']} erro(s)")

    emoji = "✅" if stats["copiados"] else "⏭️"
    if stats["erros"]:
        emoji = "❌"

    if stats["copiados"] == 0 and stats["pulados"] > 0:
        _resumo(
            "⏭️",
            f"Prontuário já copiado anteriormente ({stats['pulados']} arquivo(s) existente(s))",
        )
    else:
        _resumo(emoji, " | ".join(partes))

    return stats


def main():
    parser = argparse.ArgumentParser(
        description="Analisador de Exames — Varredura recursiva de pasta "
        "geral com detecção de formatos antigo e novo",
    )
    parser.add_argument(
        "--origem",
        type=str,
        default=DIR_EXAMES_GERAL,
        help=f"Diretório de origem para varredura recursiva (padrão: {DIR_EXAMES_GERAL})",
    )
    parser.add_argument(
        "--destino",
        type=str,
        default=DIR_RECUPERACAO_ARQUIVOSFAV,
        help=f"Diretório de destino das cópias (padrão: {DIR_RECUPERACAO_ARQUIVOSFAV})",
    )
    parser.add_argument(
        "--banco",
        type=str,
        default=str(BANCO_HISTORICO),
        help=f"Caminho do banco de dados (padrão: {BANCO_HISTORICO})",
    )
    parser.add_argument(
        "--limite",
        type=int,
        default=LIMITE_PACIENTES_LOTE,
        help=f"Número máximo de prontuários a processar nesta execução (padrão: {LIMITE_PACIENTES_LOTE})",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        default=False,
        help="Reprocessa todos os prontuários, mesmo os já recuperados/copiados",
    )
    parser.add_argument(
        "--silencioso",
        action="store_true",
        default=False,
        help="Suprime saída detalhada no console",
    )
    args = parser.parse_args()

    analisar_exames(
        dir_origem=args.origem,
        dir_destino=args.destino,
        banco=args.banco,
        forcar=args.force,
        limite=args.limite,
        verbose=not args.silencioso,
    )


if __name__ == "__main__":
    main()
