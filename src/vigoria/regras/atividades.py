"""Atividades opcionais (dança e Tai Chi): minutos e nível das ligações, comuns às duas
(REGRAS_DOMINIO §5.1, D3 e D6; §5.2, T3 e T6). Funções puras, sem I/O."""

from vigoria.modelos.questionario import Intensidade

In = Intensidade
# D3 e T3: minutos por intensidade, na fase 1 e nas fases 2 a 4.
MINUTOS_FASE_1 = {In.LIGEIRA: 10, In.MEDIA: 15, In.ALTA: 20}
MINUTOS_FASES_2_A_4 = {In.LIGEIRA: 10, In.MEDIA: 20, In.ALTA: 30}
# Decisão de 17/11/2026: a sessão guarda 10 min para o aquecimento e o retorno à calma;
# a atividade nunca tem menos de 10 min.
RESERVA_MIN = 10
MINIMO_MIN = 10
NIVEL_ABAIXO = {In.ALTA: In.MEDIA, In.MEDIA: In.LIGEIRA, In.LIGEIRA: None}


def minutos_atividade(fase: int, intensidade: Intensidade, minutos_dia: int) -> int:
    """D3 e T3, limitados à sessão: min(tabela, minutos_dia − 10), nunca abaixo de 10."""
    if not 1 <= fase <= 4:
        raise ValueError(f"fase {fase} fora do programa (1 a 4)")
    tabela = MINUTOS_FASE_1 if fase == 1 else MINUTOS_FASES_2_A_4
    return max(MINIMO_MIN, min(tabela[intensidade], minutos_dia - RESERVA_MIN))


def nivel_das_ligacoes(intensidade: Intensidade, so_ligeira: bool) -> Intensidade:
    """D6 e T6: o nível da pessoa, ou ligeira com a regressão por condições."""
    return In.LIGEIRA if so_ligeira else intensidade


def nivel_mais_calmo(intensidade: Intensidade, so_ligeira: bool) -> Intensidade | None:
    """D6 e T6: o nível abaixo («para um dia mais calmo»); nenhum na ligeira."""
    return NIVEL_ABAIXO[nivel_das_ligacoes(intensidade, so_ligeira)]
