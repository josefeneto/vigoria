"""Depois das 16 semanas (Fase 6B): texto fixo de manutencao.yaml, sem LLM.

A única personalização são os exercícios das fases 3 e 4 do próprio plano (já com as
regressões e os filtros desta pessoa) e a recomendação da OMS, só a partir dos 65 anos
(REGRAS_DOMINIO §5). Nunca entram exercícios que não estejam no plano.
"""

from vigoria.conteudo.carregar import ParteManutencao, carregar_manutencao
from vigoria.modelos.plano import OrientacoesManutencao, ParteOrientacao, Plano

FASES_BASE = (3, 4)
IDADE_OMS = 65  # a recomendação citada no V1 é para adultos com 65 ou mais anos


def _parte(parte: ParteManutencao, *notas_antes: str) -> ParteOrientacao:
    return ParteOrientacao(
        introducao=parte.introducao,
        titulo_pontos=parte.titulo_pontos,
        pontos=parte.pontos,
        notas=(*notas_antes, *parte.notas),
    )


def exercicios_base(plano: Plano) -> tuple[str, ...]:
    """Nomes dos exercícios das fases 3 e 4, sem repetidos e pela ordem do plano."""
    nomes: dict[str, None] = {}
    for fase in plano.treino.fases:
        if fase.numero not in FASES_BASE:
            continue
        cardio = () if fase.cardio_finalizador is None else (fase.cardio_finalizador,)
        for x in (*fase.forca, *cardio, *fase.mobilidade_equilibrio):
            nomes.setdefault(x.nome)
    return tuple(nomes)


def orientacoes_manutencao(plano: Plano, idade: int | None) -> OrientacoesManutencao:
    """Sem idade conhecida, a frase da OMS fica de fora."""
    m = carregar_manutencao()
    oms = (m.treino.oms_65,) if idade is not None and idade >= IDADE_OMS else ()
    return OrientacoesManutencao(
        introducao=m.introducao,
        treino=_parte(m.treino, *oms),
        variar=m.treino.variar,
        exercicios_base=exercicios_base(plano),
        alimentacao=_parte(m.alimentacao),
        vigiar=_parte(m.vigiar),
        recomecar=_parte(m.recomecar),
    )
