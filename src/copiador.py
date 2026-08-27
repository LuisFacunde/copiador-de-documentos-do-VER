import logging
import shutil
from collections import Counter
from pathlib import Path

from .filtros import (
    agrupar_exames_antigos,
    coletar_exames_novos,
    agrupar_por_tipo,
    avaliar_criterio_paciente,
)


def processar_prontuario(
    prontuario: str,
    dirs_origem: list[str | Path],
    dir_destino: str | Path,
    indice: int = 0,
    total: int = 0,
    logger: logging.Logger | None = None,
    verbose: bool = True,
) -> dict:
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

    pastas_origem = []
    for dir_orig in dirs_origem:
        candidata = Path(dir_orig) / prontuario
        if candidata.exists():
            pastas_origem.append(candidata)

    if not pastas_origem:
        _resumo("⚠️", " Pasta não encontrada")
        stats["motivo_exclusao"] = "pasta_nao_encontrada"
        return stats

    # Coletar arquivos de todas as pastas de origem
    arquivos_na_pasta = []
    for pasta_origem in pastas_origem:
        try:
            arquivos_na_pasta.extend(list(pasta_origem.iterdir()))
        except Exception as exc:
            _resumo("❌", f"Erro ao acessar pasta {pasta_origem}: {exc}")
            stats["erros"] += 1

    if stats["erros"] and not arquivos_na_pasta:
        return stats

    # ── Agrupar exames por tipo (busca híbrida: formato antigo + novo) ──
    try:
        # Fase 1: buscar exames no formato antigo
        agrupados_antigos = agrupar_exames_antigos(
            arquivos_na_pasta,
            logger=logger,
            verbose=verbose,
        )

        tem_antigos = bool(agrupados_antigos["RET"]) or bool(agrupados_antigos["OCTPAPILA"])

        if tem_antigos:
            # Usar formato antigo para validação
            agrupados = agrupados_antigos
        else:
            # Fallback: busca híbrida (formato novo + antigo)
            agrupados = agrupar_por_tipo(
                arquivos_na_pasta,
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

    # Avaliar correspondência RET↔OCTPAPILA
    aprovado, para_copiar, motivos_reprovacao = avaliar_criterio_paciente(
        ret_lista=agrupados["RET"],
        oct_lista=agrupados["OCTPAPILA"],
        logger=logger,
        verbose=verbose,
    )

    # Fase 2: se aprovado com formato antigo, coletar também exames em formato novo
    if aprovado and tem_antigos:
        tipos_aprovados = {item["tipo"] for item in para_copiar}
        exames_novos = coletar_exames_novos(
            arquivos_na_pasta,
            tipos_aprovados=tipos_aprovados,
            logger=logger,
            verbose=verbose,
        )
        # Adicionar exames novos à lista de cópia (sem duplicar)
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
            _resumo("📭", "Sem arquivos de exame na pasta")
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

    # ── Copiar arquivos ──
    pasta_destino = Path(dir_destino) / prontuario
    pasta_destino.mkdir(parents=True, exist_ok=True)

    for item in para_copiar:
        arquivo_destino = pasta_destino / item["nome"]
        if arquivo_destino.exists():
            _log(
                "debug",
                f"  ⏭️  {prontuario}/{item['nome']} "
                f"({item['tipo']}) - já copiado",
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
        _resumo("⏭️", f"Prontuário já copiado anteriormente ({stats['pulados']} arquivo(s) existente(s))")
    else:
        _resumo(emoji, " | ".join(partes))

    return stats
