"""Treino das 4 fases (determinístico, Fase 4C): fases.yaml + motor/selecao.py.

Para cada fase: as posições de força do programa, cada uma resolvida pela seleção
(o próprio exercício ou a regressão permitida), o cardio finalizador, a mobilidade e o
equilíbrio permitidos, o esforço percebido da fase e a estrutura da sessão.
Com «sem intervalos» na Estrategia, o cardio finalizador da estrutura é a variante
contínua e cada exercício usa `descricao_sem_intervalos`, se a tiver.

Regras (REGRAS_DOMINIO §6.6, decisão de 30/10/2026):
- um substituto por regressão mantém as séries e o descanso da posição, mas usa as
  repetições da sua própria posição no programa (mesma fase; senão, a fase anterior mais
  próxima; senão, a seguinte); se não tiver posição, as do original sem «(por perna)» ou
  «(por braço)»;
- o mesmo exercício nunca aparece duas vezes na mesma fase: se a regressão já lá estiver,
  segue a cadeia; se a cadeia acabar, a posição sai.
"""

import re

from vigoria.conteudo.carregar import (
    Exercicio,
    Fase,
    Grupo,
    PosicaoFase,
    carregar_avisos,
    carregar_exercicios,
    carregar_programa,
)
from vigoria.modelos.estrategia import Estrategia
from vigoria.modelos.plano import EstruturaSessao, ExercicioPlano, Treino, TreinoFase
from vigoria.modelos.questionario import Equipamento as EquipamentoDeclarado
from vigoria.modelos.questionario import Questionario
from vigoria.motor.selecao import ExercicioPermitido, selecionar_exercicios
from vigoria.regras import textos

# Cardio finalizador: o equipamento declarado primeiro; senão, sem equipamento (V2).
CARDIO_FINALIZADOR = ("passadeira", "eliptica", "marcha_rapida_lugar", "caminhada")
_LADO = re.compile(r"\s*\(por (?:perna|braço)\)")
_KG = re.compile(r"(\d+(?:[.,]\d+)?)\s*kg")
_KG_REPETIDO = re.compile(r"(\d+(?:,\d+)? kg) ou \1")


def construir_treino(e: Estrategia, q: Questionario) -> Treino:
    programa = carregar_programa()
    s = programa.estrutura_sessao
    continuo = e.restricoes.sem_intervalos
    return Treino(
        estrutura_sessao=EstruturaSessao(
            aquecimento=s.aquecimento,
            bloco_principal=s.bloco_principal,
            cardio_finalizador=s.cardio_finalizador_continuo if continuo else s.cardio_finalizador,
            retorno_calma=s.retorno_calma,
        ),
        fases=tuple(_fase(f, e, q) for f in programa.fases),
    )


def _fase(fase: Fase, e: Estrategia, q: Questionario) -> TreinoFase:
    permitidos = {p.id: p for p in selecionar_exercicios(e, fase.numero)}
    usados: set[str] = set()
    forca = []
    for posicao in fase.exercicios:
        id_ = _resolver(posicao.id, permitidos, usados)
        if id_ is None:
            continue  # nem o exercício nem uma regressão livre: a posição sai
        usados.add(id_)
        forca.append(_exercicio_da_posicao(id_, posicao, fase, permitidos, usados, e, q))

    cardio = next(
        (c for c in CARDIO_FINALIZADOR if c in permitidos and c not in usados),
        None,
    )
    continuo = e.restricoes.sem_intervalos
    notas_cardio = (textos.CARDIO_RITMO_CONTINUO,) if continuo else ()
    duracao = carregar_programa().estrutura_sessao.duracao_cardio_min
    return TreinoFase(
        numero=fase.numero,
        nome=fase.nome,
        foco=fase.foco_estrategico,
        esforco=(fase.esforco.min, fase.esforco.max),
        forca=tuple(forca),
        cardio_finalizador=(
            _exercicio(permitidos[cardio], q, notas_cardio, continuo) if cardio else None
        ),
        cardio_duracao_min=(duracao.min, duracao.max),
        mobilidade_equilibrio=tuple(
            _exercicio(p, q, sem_intervalos=continuo)
            for p in permitidos.values()
            if p.grupo in (Grupo.MOBILIDADE, Grupo.EQUILIBRIO)
        ),
    )


def _resolver(id_: str, permitidos: dict[str, ExercicioPermitido], usados: set[str]) -> str | None:
    """O exercício, se permitido; senão, o que o substitui; senão, o primeiro permitido na
    cadeia de regressões. Se o escolhido já estiver na fase, continua pela cadeia."""
    biblioteca = carregar_exercicios()
    candidato = id_ if id_ in permitidos else None
    if candidato is None:
        candidato = next((p.id for p in permitidos.values() if id_ in p.substitui), None)
    atual: str | None = candidato or biblioteca[id_].regressao
    vistos: set[str] = set()
    while atual is not None and atual not in vistos:
        if atual in permitidos and atual not in usados:
            return atual
        vistos.add(atual)
        atual = biblioteca[atual].regressao
    return None


def _exercicio_da_posicao(
    id_: str,
    posicao: PosicaoFase,
    fase: Fase,
    permitidos: dict[str, ExercicioPermitido],
    usados: set[str],
    e: Estrategia,
    q: Questionario,
) -> ExercicioPlano:
    rotulos = carregar_avisos().rotulos.plano
    biblioteca = carregar_exercicios()
    notas: list[str] = []
    alternativa = next(
        (
            a
            for original in posicao.alternativas
            if (a := _resolver(original, permitidos, usados | {id_})) is not None
        ),
        None,
    )
    if alternativa is not None:
        notas.append(rotulos["alternativa"].format(nome=biblioteca[alternativa].nome))
    base = _exercicio(permitidos[id_], q, tuple(notas), e.restricoes.sem_intervalos)
    substituto = id_ != posicao.id
    return base.model_copy(
        update={
            "series": posicao.series,
            "repeticoes": (
                (repeticoes_proprias(id_, fase.numero) or _sem_lado(posicao.repeticoes))
                if substituto
                else posicao.repeticoes
            ),
            "descanso_s": (posicao.descanso_s.min, posicao.descanso_s.max),
            "em_vez_de": posicao.id if substituto else None,
        }
    )


def repeticoes_proprias(id_: str, fase: int) -> str | None:
    """Repetições da posição do exercício no programa: mesma fase, anterior mais próxima,
    seguinte mais próxima. None se o exercício não tiver posição no programa."""
    por_fase = {
        f.numero: p.repeticoes
        for f in carregar_programa().fases
        for p in f.exercicios
        if p.id == id_
    }
    ordem = [fase, *range(fase - 1, 0, -1), *range(fase + 1, 5)]
    return next((por_fase[n] for n in ordem if n in por_fase), None)


def _sem_lado(repeticoes: str) -> str:
    return _LADO.sub("", repeticoes)


def _exercicio(
    p: ExercicioPermitido,
    q: Questionario,
    extra: tuple[str, ...] = (),
    sem_intervalos: bool = False,
) -> ExercicioPlano:
    ex = carregar_exercicios()[p.id]
    rotulos = carregar_avisos().rotulos.plano
    notas = list(p.notas)
    if p.esforco_max is not None:
        notas.append(rotulos["esforco_maximo"].format(max=p.esforco_max))
    if (halteres := variante_halteres(ex, q)) is not None:
        notas.append(rotulos["halteres"].format(texto=halteres))
    notas.extend(extra)
    return ExercicioPlano(
        id=ex.id,
        nome=ex.nome,
        descricao=(ex.descricao_sem_intervalos if sem_intervalos else None) or ex.descricao,
        notas=tuple(dict.fromkeys(notas)),
    )


def variante_halteres(ex: Exercicio, q: Questionario) -> str | None:
    """Variante com halteres, se a pessoa os tiver; cada peso limitado ao declarado."""
    if (
        ex.variante_halteres is None
        or EquipamentoDeclarado.HALTERES not in q.equipamento
        or not q.halteres_kg
    ):
        return None
    declarado = float(q.halteres_kg)

    def limitar(m: re.Match[str]) -> str:
        valor = min(float(m.group(1).replace(",", ".")), declarado)
        return f"{textos.numero(valor)} kg"

    texto = _KG.sub(limitar, ex.variante_halteres)
    return _KG_REPETIDO.sub(r"\1", texto)  # «2 kg ou 5 kg» com 2 kg declarados → «2 kg»
