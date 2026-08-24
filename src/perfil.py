"""
    perfil.py
    ---------
    Define o PerfilSerie — objeto que encapsula todos os parâmetros
    variáveis de uma série de exames — e a função que carrega esse
    perfil a partir de um arquivo YAML em series/<nome>/config.yaml.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
import yaml

_BASE = Path(__file__).resolve().parent.parent
_SERIES_DIR = _BASE / 'series'


@dataclass
class PerfilSerie:
    nome: str
    planilha: Path
    aba_planilha: str
    coluna_prontuario: str
    dirs_origem: list[str]
    dir_destino: str
    banco_historico: Path
    data_min: datetime
    data_max: datetime
    mapa_tipos: dict[str, str]        # ex: {"RETIN": "RET", "OCTPAPILA": "OCTPAPILA"}
    tipos_obrigatorios: list[str]     # ex: ["RET", "OCTPAPILA"] — todos devem estar presentes
    janela_dias: int                  # tolerância em dias entre os tipos obrigatórios
    extensao_permitida: str           # ex: ".pdf"
    limite_pacientes_lote: int        # max de pacientes processados por execução


def carregar_perfil(nome: str) -> PerfilSerie:
    """
    Carrega o PerfilSerie a partir de series/<nome>/config.yaml.

    Uso:
        perfil = carregar_perfil("ret_oct_papila")
    """
    caminho = _SERIES_DIR / nome / 'config.yaml'
    if not caminho.exists():
        series_disponiveis = [
            d.name for d in _SERIES_DIR.iterdir() if d.is_dir()
        ] if _SERIES_DIR.exists() else []
        raise FileNotFoundError(
            f"Série '{nome}' não encontrada em {_SERIES_DIR}.\n"
            f"Séries disponíveis: {series_disponiveis or '(nenhuma)'}"
        )

    with caminho.open(encoding='utf-8') as f:
        dados = yaml.safe_load(f)

    return PerfilSerie(
        nome=dados['nome'],
        planilha=_BASE / dados['planilha'],
        aba_planilha=dados['aba_planilha'],
        coluna_prontuario=dados['coluna_prontuario'],
        dirs_origem=dados['dirs_origem'],
        dir_destino=dados['dir_destino'],
        banco_historico=_BASE / dados.get('banco_historico', f'dados/bd/{nome}.db'),
        data_min=datetime.fromisoformat(dados['data_min']),
        data_max=datetime.fromisoformat(dados['data_max']),
        mapa_tipos=dados['mapa_tipos'],
        tipos_obrigatorios=dados['tipos_obrigatorios'],
        janela_dias=dados['janela_dias'],
        extensao_permitida=dados.get('extensao_permitida', '.pdf'),
        limite_pacientes_lote=dados.get('limite_pacientes_lote', 2500),
    )


def listar_series() -> list[str]:
    """
        Retorna os nomes de todas as séries disponíveis em series/.
    """
    if not _SERIES_DIR.exists():
        return []
    return [
        d.name
        for d in sorted(_SERIES_DIR.iterdir())
        if d.is_dir() and (d / 'config.yaml').exists()
    ]
