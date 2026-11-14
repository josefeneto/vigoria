"""Texto da página de Ajuda (Fase 8B), com os números preenchidos a partir do código.

O YAML (conteudo/ajuda.yaml) nunca tem números escritos à mão: tem marcadores {assim}, que
vêm das constantes das regras. Assim, se uma regra mudar, a Ajuda muda com ela.
"""

from string import Formatter

from vigoria.conteudo.carregar import ErroConteudo, PerguntaAjuda, TemaAjuda, carregar_ajuda
from vigoria.interface.passos import MINUTOS_QUESTIONARIO, PASSOS
from vigoria.modelos.registo import ESCALA_MAXIMA, ESCALA_MINIMA
from vigoria.regras.calculos import SEMANAS_MARCOS, SEMANAS_PROGRAMA
from vigoria.regras.lembretes import (
    DIAS_MAXIMO,
    DIAS_PRIMEIRO,
    DIAS_SEGUNDO,
    MAXIMO_POR_PERIODO,
    PERIODOS_PARA_SUSPENDER,
)
from vigoria.regras.progresso import SEMANAS_POR_FASE

VALORES: dict[str, int] = {
    "semanas_programa": SEMANAS_PROGRAMA,
    "fases": len(SEMANAS_MARCOS),
    "semanas_por_fase": SEMANAS_POR_FASE,
    "semana_manutencao": SEMANAS_PROGRAMA + 1,
    "passos": len(PASSOS),
    "minutos_questionario": MINUTOS_QUESTIONARIO,
    "escala_minima": ESCALA_MINIMA,
    "escala_maxima": ESCALA_MAXIMA,
    "dias_primeiro": DIAS_PRIMEIRO,
    "dias_segundo": DIAS_SEGUNDO,
    "dias_maximo": DIAS_MAXIMO,
    "maximo_por_periodo": MAXIMO_POR_PERIODO,
    "periodos_suspender": PERIODOS_PARA_SUSPENDER,
}


def marcadores(texto: str) -> set[str]:
    """Os marcadores {assim} de um texto."""
    return {nome for _, nome, _, _ in Formatter().parse(texto) if nome is not None}


def preencher(texto: str) -> str:
    """Substitui os marcadores pelos valores; um marcador desconhecido dá ErroConteudo."""
    desconhecidos = marcadores(texto) - VALORES.keys()
    if desconhecidos:
        raise ErroConteudo(
            f"conteudo/ajuda.yaml: marcador desconhecido: {', '.join(sorted(desconhecidos))}"
        )
    return texto.format_map(VALORES)


def _preenchida(p: PerguntaAjuda) -> PerguntaAjuda:
    return p.model_copy(
        update={"pergunta": preencher(p.pergunta), "resposta": preencher(p.resposta)}
    )


def ajuda(
    ambiente: str | None, primeiro: str | None = None, acesso: str | None = None
) -> tuple[TemaAjuda, ...]:
    """Os temas a mostrar neste ambiente e modo de acesso (VIGORIA_ACESSO), já preenchidos.

    Só ficam as perguntas sem `ambientes` ou com este ambiente, e sem `acesso` ou com este
    modo (com None, sem filtro: para os testes); um tema sem perguntas sai. Com `primeiro`
    (id de um tema), esse tema passa para o início e os outros mantêm a ordem; um id
    desconhecido não muda nada.
    """
    temas: list[TemaAjuda] = []
    for tema in carregar_ajuda().temas:
        perguntas = tuple(
            _preenchida(p)
            for p in tema.perguntas
            if (ambiente is None or not p.ambientes or ambiente in p.ambientes)
            and (acesso is None or not p.acesso or acesso in p.acesso)
        )
        if perguntas:
            temas.append(
                tema.model_copy(update={"titulo": preencher(tema.titulo), "perguntas": perguntas})
            )
    temas.sort(key=lambda tema: tema.id != primeiro)
    return tuple(temas)
