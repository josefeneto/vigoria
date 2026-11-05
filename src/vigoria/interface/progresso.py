"""Do plano e dos registos da conta para as regras do acompanhamento (sem Streamlit)."""

from collections.abc import Iterable

from vigoria.dados.repositorios import PlanoDaConta, RegistoDaConta
from vigoria.regras.progresso import ContextoPlano, Medicao, inicio_do_plano


def contexto_do_plano(p: PlanoDaConta) -> ContextoPlano:
    indicadores = p.estrategia.indicadores
    return ContextoPlano(
        inicio=inicio_do_plano(p.criado_em),
        peso_inicial_kg=p.peso_kg,
        idade=p.idade,
        peso_alvo_kg=indicadores.peso_alvo_usado_kg if indicadores else None,
        marcos=tuple((m.semana, m.peso_indicativo_kg) for m in p.plano.marcos),
        esforco_fases={f.numero: f.esforco for f in p.plano.treino.fases},
    )


def medicoes_dos_registos(registos: Iterable[RegistoDaConta]) -> list[Medicao]:
    """Só os campos que as regras leem: as observações nunca chegam ao motor."""
    return [
        Medicao(
            semana=r.semana,
            peso_kg=r.valores.peso_kg,
            cintura_cm=r.valores.cintura_cm,
            esforco=r.valores.esforco,
        )
        for r in registos
    ]
