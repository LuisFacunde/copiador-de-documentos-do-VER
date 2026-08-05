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
        'sem_exames': False,
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
        stats['sem_exames'] = True
        return stats

    try:
        agrupados = agrupar_por_tipo(
            list(pasta_origem.iterdir()),
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
        _log('info', f"⊘ Prontuário {prontuario}: nenhum exame válido encontrado")
        stats['sem_exames'] = True
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
