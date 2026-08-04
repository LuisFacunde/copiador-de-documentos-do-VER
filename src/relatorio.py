def imprimir_relatorio(estatisticas: dict) -> None:

    sep = "=" * 70
    sep_menor = "-" * 70

    print(f"\n{sep}")
    print("📊  RELATÓRIO FINAL")
    print(sep)
    print(f"✓  Prontuários com exames copiados : {estatisticas['pacientes_processados']}")
    print(f"⊘  Prontuários sem exames válidos  : {estatisticas['pacientes_sem_exames']}")
    print(f"✓  Arquivos PDF copiados           : {estatisticas['arquivos_copiados']}")
    print(f"⏭  Arquivos já existentes (pulados) : {estatisticas['arquivos_pulados']}")
    print(sep_menor)
    print(f"⊘  Arquivos com nome inválido      : {estatisticas['arquivos_invalidos']}")
    print(f"⊘  Arquivos com tipo inválido      : {estatisticas['arquivos_tipo_invalido']}")
    print(f"⊘  Arquivos fora do período        : {estatisticas['arquivos_fora_periodo']}")
    print(f"⊘  Arquivos fora da janela         : {estatisticas['arquivos_fora_janela']}")
    print(f"❌  Erros na cópia                 : {estatisticas['erros']}")
    print(sep)
