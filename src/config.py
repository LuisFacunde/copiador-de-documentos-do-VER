"""
config.py
---------
Constantes globais de infraestrutura do projeto.

Os parâmetros específicos de cada série de exames (planilha, tipos,
períodos, janela, etc.) são definidos em series/<nome>/config.yaml
e carregados via src.perfil.carregar_perfil().
"""

from pathlib import Path

# Raiz do projeto — usado internamente por perfil.py
_BASE = Path(__file__).resolve().parent.parent
