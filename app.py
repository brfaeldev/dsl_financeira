"""
Ponto de Entrada do Playground Web em Streamlit (app.py)

Atalho de execucao na raiz do projeto (`streamlit run app.py`) que delega a
renderizacao e os servicos do Playground para `dsl_financeira.playground`.
"""

from dsl_financeira.playground import (
    compilar_e_simular_dsl,
    gerar_bloco_investimento_dsl,
    gerar_declaracao_indice_dsl,
    listar_exemplos_disponiveis,
    renderizar_app,
)

__all__ = [
    "compilar_e_simular_dsl",
    "gerar_bloco_investimento_dsl",
    "gerar_declaracao_indice_dsl",
    "listar_exemplos_disponiveis",
    "renderizar_app",
]

if __name__ == "__main__":
    renderizar_app()
