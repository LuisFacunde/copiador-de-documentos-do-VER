import logging
import shutil
from pathlib import Path

from .filtros import agrupar_por_tipo, aplicar_janela_temporal


def processar_prontuario(
    prontuario: str,
    dir_origem: str | Path,
    dir_destino: str | Path,
    logger: logging.Logger | None = None,
    verbose: bool = True,
) -> dict:
    stats = {
        'copiados': 0,
        'pulados': 0,
        'invalidos': 0,
        'tipo_invalido': 0,
        'fora_periodo': 0,
        'fora_janela': 0,
        'erros': 0,
        'motivo_exclusao': None,
        'arquivos_copiados': [],
    }

    def _log(nivel: str, msg: str) -> None:
        if logger:
            getattr(logger, nivel)(msg)
        elif verbose:
            print(msg)

    pasta_origem = Path(dir_origem) / prontuario
    if not pasta_origem.exists():
        _log('warning', f"⚠️  Prontuário {prontuario}: pasta não encontrada em {dir_origem}")
        stats['motivo_exclusao'] = 'pasta_nao_encontrada'
        return stats

    try:
        arquivos_na_pasta = list(pasta_origem.iterdir())
        agrupados = agrupar_por_tipo(
            arquivos_na_pasta,
            logger=logger,
            verbose=verbose,
        )
    except Exception as exc:
        _log('error', f"❌ Erro ao listar {prontuario}: {exc}")
        stats['erros'] += 1
        return stats

    stats['invalidos']     += agrupados['_invalidos']
    stats['tipo_invalido'] += agrupados['_tipo_invalido']
    stats['fora_periodo']  += agrupados['_fora_periodo']

    total_arquivos_analisados = (
        len(agrupados['RET'])
        + len(agrupados['OCTPAPILA'])
        + agrupados['_invalidos']
        + agrupados['_tipo_invalido']
        + agrupados['_fora_periodo']
    )

    para_copiar = []
    for tipo_exame in ('RET', 'OCTPAPILA'):
        validos, descartados = aplicar_janela_temporal(
            agrupados[tipo_exame],
            logger=logger,
            verbose=verbose,
        )
        para_copiar.extend(validos)
        stats['fora_janela'] += descartados

    if not para_copiar:
        if total_arquivos_analisados == 0:
            _log('info',
                f"⊘ Prontuário {prontuario}: pasta encontrada, "
                f"mas sem arquivos de exame"
            )
            stats['motivo_exclusao'] = 'pasta_sem_arquivos'
        else:
            _log('info',
                f"⊘ Prontuário {prontuario}: exames encontrados, "
                f"mas nenhum atende aos critérios de filtro"
            )
            stats['motivo_exclusao'] = 'exames_sem_correspondencia'
        return stats

    pasta_destino = Path(dir_destino) / prontuario
    pasta_destino.mkdir(parents=True, exist_ok=True)

    for item in para_copiar:
        arquivo_destino = pasta_destino / item['nome']
        if arquivo_destino.exists():
            _log('info',
                f"⏭ {prontuario}/{item['nome']} "
                f"({item['tipo']}) — já copiado"
            )
            stats['pulados'] += 1
            continue
        try:
            shutil.copy2(item['path'], arquivo_destino)
            _log('info',
                f"✓ {prontuario}/{item['nome']} "
                f"({item['tipo']}) — {item['data'].strftime('%d/%m/%Y')}"
            )
            stats['copiados'] += 1
            stats['arquivos_copiados'].append({
                'nome': item['nome'],
                'tipo': item['tipo'],
                'data': item['data'].isoformat() if item.get('data') else None,
            })
        except Exception as exc:
            _log('error', f"❌ Erro ao copiar {prontuario}/{item['nome']}: {exc}")
            stats['erros'] += 1

    return stats
