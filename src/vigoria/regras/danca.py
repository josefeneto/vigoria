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

In = Intensidade
# D3: minutos de dança por intensidade, na fase 1 e nas fases 2 a 4.
MINUTOS_FASE_1 = {In.LIGEIRA: 10, In.MEDIA: 15, In.ALTA: 20}
MINUTOS_FASES_2_A_4 = {In.LIGEIRA: 10, In.MEDIA: 20, In.ALTA: 30}
# Decisão de 17/11/2026: a sessão guarda 10 min para o aquecimento e o retorno à calma;
# a dança nunca tem menos de 10 min.
RESERVA_MIN = 10
MINIMO_MIN = 10
NIVEL_ABAIXO = {In.ALTA: In.MEDIA, In.MEDIA: In.LIGEIRA, In.LIGEIRA: None}


def tem_danca(q: Questionario) -> bool:
    """D1: o bloco só aparece a quem marcou «dança» nas preferências."""
    return Preferencia.DANCA in q.preferencias


def minutos_danca(fase: int, intensidade: Intensidade, minutos_dia: int) -> int:
    """D3, limitado à sessão: min(D3, minutos_dia − 10), nunca abaixo de 10."""
    if not 1 <= fase <= 4:
        raise ValueError(f"fase {fase} fora do programa (1 a 4)")
    tabela = MINUTOS_FASE_1 if fase == 1 else MINUTOS_FASES_2_A_4
    return max(MINIMO_MIN, min(tabela[intensidade], minutos_dia - RESERVA_MIN))


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


def nivel_das_ligacoes(intensidade: Intensidade, so_ligeira: bool) -> Intensidade:
    """D6: o nível da pessoa, ou ligeira com a regressão por condições."""
    return In.LIGEIRA if so_ligeira else intensidade


def nivel_mais_calmo(intensidade: Intensidade, so_ligeira: bool) -> Intensidade | None:
    """D6: o nível abaixo («para um dia mais calmo»); nenhum na ligeira."""
    return NIVEL_ABAIXO[nivel_das_ligacoes(intensidade, so_ligeira)]


def mostra_mais_aulas(intensidade: Intensidade, so_ligeira: bool) -> bool:
    """«Mais aulas» (esforço misto) só para media e alta, e nunca com a regressão."""
    return not so_ligeira and intensidade in (In.MEDIA, In.ALTA)


def sugere_subir(intensidade: Intensidade, so_ligeira: bool) -> bool:
    """D6: «experimente o nível acima» só sem a regressão e se houver nível acima."""
    return not so_ligeira and intensidade is not In.ALTA
