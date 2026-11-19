"""Tai Chi (opcional): o bloco do plano e as ligações a mostrar (REGRAS §5.2, T1 a T7).

`construir_taichi` corre ao montar o plano; `ligacoes_taichi` corre ao mostrar (app e PDF),
a partir de taichi.yaml.
"""

from vigoria.conteudo.carregar import carregar_taichi
from vigoria.modelos.estrategia import Estrategia
from vigoria.modelos.plano import TaiChi
from vigoria.modelos.questionario import Questionario
from vigoria.motor.atividades import LigacoesAtividade, escolher_ligacoes
from vigoria.regras import taichi as regras
from vigoria.regras.atividades import minutos_atividade


def construir_taichi(e: Estrategia, q: Questionario) -> TaiChi | None:
    """None sem «Tai Chi» nas preferências (T1) ou sem intensidade efetiva."""
    if not regras.tem_taichi(q) or e.intensidade_efetiva is None:
        return None
    intensidade = e.intensidade_efetiva
    return TaiChi(
        minutos=tuple(  # type: ignore[arg-type]
            minutos_atividade(f, intensidade, q.minutos_dia) for f in range(1, 5)
        ),
        intensidade=intensidade,
        so_ligeira=regras.so_nivel_ligeira(q),
    )


def ligacoes_taichi(t: TaiChi) -> LigacoesAtividade:
    """T6: o nível da pessoa (ou ligeira, na cadeira) e um do nível abaixo; sem «Mais aulas»."""
    return escolher_ligacoes(carregar_taichi(), t.intensidade, t.so_ligeira)
