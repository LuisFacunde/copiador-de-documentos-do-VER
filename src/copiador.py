import shutil
from pathlib import Path

from .filtros import agrupar_por_tipo, aplicar_janela_temporal


def processar_pronunciario(
    pronunciario: str,
    dir_origem: str | Path,
    dir_destino: str | Path,
    verbose: bool = True,
) -> dict:
    stats = {
        'copiados': 0,
        'invalidos': 0,
        'tipo_invalido': 0,
        'fora_periodo': 0,
        'fora_janela': 0,
        'erros': 0,
        'sem_exames': False,
    }

    pasta_origem = Path(dir_origem) / pronunciario
    if not pasta_origem.exists():
        if verbose:
            print(f"⚠️  Prontuário {pronunciario}: pasta não encontrada em {dir_origem}")
        stats['sem_exames'] = True
        return stats

    try:
        agrupados = agrupar_por_tipo(list(pasta_origem.iterdir()), verbose=verbose)
    except Exception as exc:
        if verbose:
            print(f"❌ Erro ao listar {pronunciario}: {exc}")
        stats['erros'] += 1
        return stats

    stats['invalidos']    += agrupados['_invalidos']
    stats['tipo_invalido'] += agrupados['_tipo_invalido']
    stats['fora_periodo'] += agrupados['_fora_periodo']

    para_copiar = []
    for tipo_exame in ('RET', 'OCT'):
        validos, descartados = aplicar_janela_temporal(agrupados[tipo_exame], verbose=verbose)
        para_copiar.extend(validos)
        stats['fora_janela'] += descartados

    if not para_copiar:
        if verbose:
            print(f"⊘ Prontuário {pronunciario}: nenhum exame válido encontrado\n")
        stats['sem_exames'] = True
        return stats

    pasta_destino = Path(dir_destino) / pronunciario
    pasta_destino.mkdir(parents=True, exist_ok=True)

    for item in para_copiar:
        try:
            shutil.copy2(item['path'], pasta_destino / item['nome'])
            if verbose:
                print(
                    f"✓ {pronunciario}/{item['nome']} "
                    f"({item['tipo']}) — {item['data'].strftime('%d/%m/%Y')}"
                )
            stats['copiados'] += 1
        except Exception as exc:
            if verbose:
                print(f"❌ Erro ao copiar {pronunciario}/{item['nome']}: {exc}")
            stats['erros'] += 1

    return stats
