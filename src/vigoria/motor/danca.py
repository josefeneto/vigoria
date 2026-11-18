"""Dança (opcional): o bloco do plano e as ligações a mostrar (REGRAS §5.1, D1 a D7).

`construir_danca` corre ao montar o plano; `ligacoes_danca` corre ao mostrar (app e PDF),
a partir de danca.yaml, para as ligações estarem sempre atualizadas.
"""

from dataclasses import dataclass

from vigoria.conteudo.carregar import LigacaoDanca, NivelDanca, carregar_danca
from vigoria.modelos.estrategia import Estrategia
from vigoria.modelos.plano import Danca, DiasDanca
from vigoria.modelos.questionario import Questionario
from vigoria.motor.semana import TIPOS_FORCA, sessoes
from vigoria.regras import danca as regras


def construir_danca(e: Estrategia, q: Questionario) -> Danca | None:
    """None sem «dança» nas preferências (D1) ou sem intensidade efetiva."""
    if not regras.tem_danca(q) or e.intensidade_efetiva is None:
        return None
    intensidade = e.intensidade_efetiva
    # D4: com dias de cardio na semana-tipo, nesses; senão, nos de caminhada leve.
    com_cardio = any(tipo not in TIPOS_FORCA for tipo in sessoes(q).values())
    return Danca(
        minutos=tuple(  # type: ignore[arg-type]
            regras.minutos_danca(f, intensidade, q.minutos_dia) for f in range(1, 5)
        ),
        intensidade=intensidade,
        so_ligeira=regras.so_nivel_ligeira(q),
        dias=DiasDanca.CARDIO if com_cardio else DiasDanca.CAMINHADA,
    )


@dataclass(frozen=True)
class LigacoesDanca:
    """O que mostrar (D6): o nível da pessoa, um do nível abaixo e as «Mais aulas»."""

    principais: tuple[LigacaoDanca, ...]
    mais_calmo: LigacaoDanca | None
    mais_aulas: tuple[LigacaoDanca, ...]
    ajuste: str  # o texto de ajuste, com ou sem «experimente o nível acima»


def ligacoes_danca(d: Danca) -> LigacoesDanca:
    c = carregar_danca()
    nivel = regras.nivel_das_ligacoes(d.intensidade, d.so_ligeira)
    abaixo = regras.nivel_mais_calmo(d.intensidade, d.so_ligeira)
    ajuste = c.textos.ajuste
    if regras.sugere_subir(d.intensidade, d.so_ligeira):
        ajuste = f"{ajuste} {c.textos.ajuste_subir}"
    return LigacoesDanca(
        principais=c.do_nivel(NivelDanca(nivel)),
        mais_calmo=c.do_nivel(NivelDanca(abaixo))[0] if abaixo is not None else None,
        mais_aulas=(
            c.do_nivel(NivelDanca.MAIS_AULAS)
            if regras.mostra_mais_aulas(d.intensidade, d.so_ligeira)
            else ()
        ),
        ajuste=ajuste,
    )
