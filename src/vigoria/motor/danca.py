"""Dança (opcional): o bloco do plano e as ligações a mostrar (REGRAS §5.1, D1 a D7).

`construir_danca` corre ao montar o plano; `ligacoes_danca` corre ao mostrar (app e PDF),
a partir de danca.yaml, para as ligações estarem sempre atualizadas.
"""

from vigoria.conteudo.carregar import carregar_danca
from vigoria.modelos.estrategia import Estrategia
from vigoria.modelos.plano import Danca, DiasDanca
from vigoria.modelos.questionario import Questionario
from vigoria.motor.atividades import LigacoesAtividade, escolher_ligacoes
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


def ligacoes_danca(d: Danca) -> LigacoesAtividade:
    c = carregar_danca()
    ajuste = c.textos.ajuste
    if regras.sugere_subir(d.intensidade, d.so_ligeira):
        ajuste = f"{ajuste} {c.textos.ajuste_subir}"
    return escolher_ligacoes(
        c,
        d.intensidade,
        d.so_ligeira,
        mais_aulas=regras.mostra_mais_aulas(d.intensidade, d.so_ligeira),
        ajuste=ajuste,
    )
