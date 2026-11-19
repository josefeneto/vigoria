"""Dança (opcional): minutos e nível das ligações (REGRAS_DOMINIO §5.1, D1 a D7).

Funções puras, sem I/O: as ligações vêm de conteudo/danca.yaml e chegam já carregadas.
"""

from vigoria.modelos.questionario import (
    Articulacao,
    Condicao,
    Intensidade,
    Limitacao,
    Preferencia,
    Questionario,
)
from vigoria.regras.atividades import (
    MINIMO_MIN,
    MINUTOS_FASE_1,
    MINUTOS_FASES_2_A_4,
    RESERVA_MIN,
    minutos_atividade,
    nivel_das_ligacoes,
    nivel_mais_calmo,
)

__all__ = [
    "MINIMO_MIN",
    "MINUTOS_FASE_1",
    "MINUTOS_FASES_2_A_4",
    "RESERVA_MIN",
    "minutos_danca",
    "mostra_mais_aulas",
    "nivel_das_ligacoes",
    "nivel_mais_calmo",
    "so_nivel_ligeira",
    "sugere_subir",
    "tem_danca",
]

In = Intensidade

# Minutos (D3) e níveis (D6) comuns ao Tai Chi: regras/atividades.py.
minutos_danca = minutos_atividade


def tem_danca(q: Questionario) -> bool:
    """D1: o bloco só aparece a quem marcou «dança» nas preferências."""
    return Preferencia.DANCA in q.preferencias


def so_nivel_ligeira(q: Questionario) -> bool:
    """D6: com joelhos, osteoporose, equilíbrio ou doença cardiovascular, só o nível ligeira.

    Joelhos: a limitação «joelhos» (qualquer gravidade), a dor articular persistente nos
    joelhos, ou prótese/cirurgia recente (o questionário não diz qual a articulação: conta
    sempre, porque pode ser um membro inferior). A hipertensão controlada não limita.
    """
    condicoes = set(q.condicoes)
    return bool(
        Limitacao.JOELHOS in q.limitacoes
        or Limitacao.EQUILIBRIO in q.limitacoes
        or (
            Condicao.DOR_ARTICULAR_PERSISTENTE in condicoes
            and Articulacao.JOELHOS in q.dor_articular_zonas
        )
        or condicoes
        & {
            Condicao.PROTESE_OU_CIRURGIA_RECENTE,
            Condicao.OSTEOPOROSE,
            Condicao.DOENCA_CARDIOVASCULAR,
        }
    )


def mostra_mais_aulas(intensidade: Intensidade, so_ligeira: bool) -> bool:
    """«Mais aulas» (esforço misto) só para media e alta, e nunca com a regressão."""
    return not so_ligeira and intensidade in (In.MEDIA, In.ALTA)


def sugere_subir(intensidade: Intensidade, so_ligeira: bool) -> bool:
    """D6: «experimente o nível acima» só na media sem a regressão (decisão de 17/11/2026):
    na ligeira, os links do nível acima não aparecem; na alta, não há nível acima."""
    return not so_ligeira and intensidade is In.MEDIA
