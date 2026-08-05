import logging


def imprimir_relatorio(
    estatisticas: dict,
    info_lote: dict | None = None,
    logger: logging.Logger | None = None,
) -> None:

    sep = "=" * 70
    sep_menor = "-" * 70

    linhas = [
        f"\n{sep}",
        "📊  RELATÓRIO FINAL",
    ]

    if info_lote:
        linhas.append(f"📦  Lote {info_lote['numero']} — {info_lote['data_envio']}")

    linhas.extend([
        sep,
        f"✓  Prontuários com exames copiados : {estatisticas['pacientes_processados']}",
        f"⊘  Prontuários sem exames válidos  : {estatisticas['pacientes_sem_exames']}",
        f"✓  Arquivos PDF copiados           : {estatisticas['arquivos_copiados']}",
        f"⏭  Arquivos já existentes (pulados) : {estatisticas['arquivos_pulados']}",
        sep_menor,
        f"⊘  Arquivos com nome inválido      : {estatisticas['arquivos_invalidos']}",
        f"⊘  Arquivos com tipo inválido      : {estatisticas['arquivos_tipo_invalido']}",
        f"⊘  Arquivos fora do período        : {estatisticas['arquivos_fora_periodo']}",
        f"⊘  Arquivos fora da janela         : {estatisticas['arquivos_fora_janela']}",
        f"❌  Erros na cópia                 : {estatisticas['erros']}",
    ])

    if info_lote and 'pendentes' in info_lote:
        linhas.append(sep_menor)
        linhas.append(
            f"📋  Prontuários pendentes (próximo lote): {info_lote['pendentes']}"
        )

    linhas.append(sep)

    for linha in linhas:
        if logger:
            logger.info(linha)
        else:
            print(linha)
