"""Registos fictícios da persona de teste, para ver o progresso em local (nunca em produção).

Só corre com AMBIENTE=local e numa base SQLite. Usa o utilizador local fictício e o fornecedor
simulado (sem LLM): cria um plano novo, com a data recuada, e os registos do cenário. Não apaga
nada: o plano novo fica o mais recente.

    python scripts/registos_ficticios.py normal       # evolução normal (nenhum alerta)
    python scripts/registos_ficticios.py lenta        # evolução lenta
    python scripts/registos_ficticios.py rapida       # perda demasiado rápida
    python scripts/registos_ficticios.py manutencao   # subida depois da semana 16

Depois: $env:VIGORIA_UTILIZADOR_LOCAL="1" ; python -m streamlit run app.py (PowerShell).
"""

import sys
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from vigoria.config import obter_configuracao
from vigoria.contas.entrada import Identidade
from vigoria.dados import repositorios as r
from vigoria.dados.bd import criar_motor, fabrica_sessoes, migrar
from vigoria.dados.tabelas import PlanoGuardado, Utilizador
from vigoria.llm.simulado import ProvedorSimulado
from vigoria.modelos.questionario import Questionario
from vigoria.modelos.registo import Comparacao, ValoresRegisto
from vigoria.motor.pipeline import gerar_plano_verificado

RAIZ = Path(__file__).resolve().parents[1]
PERSONA = RAIZ / "exemplos" / "persona_teste.json"
UTILIZADOR_LOCAL = Identidade(
    sub="local|desenvolvimento", email="local@vigoria.invalid", email_verificado=True
)
PESO_INICIAL = 94.0  # persona de teste: 68 anos, 94 → 85 kg, cerca de 0,375 kg/semana
RITMO_LINHA = 0.375
CINTURA_INICIAL = 108.0


def _treino(semana: int) -> dict[str, object]:
    """O resto do registo, igual em todos os cenários: não dispara alertas."""
    return {
        "sessoes": 4 if semana % 3 else 3,
        "cardio_min": 60 + 5 * (semana % 4),
        "energia": 6 + semana % 2,
        "esforco": 5,
        "sono_h": 7.0,
        "forca": Comparacao.IGUAL if semana % 2 else Comparacao.MAIS_FACIL,
        "mobilidade_equilibrio": Comparacao.IGUAL,
    }


def _normal() -> dict[int, ValoresRegisto]:
    return {
        s: ValoresRegisto(
            peso_kg=round(PESO_INICIAL - RITMO_LINHA * s + (0.3 if s % 2 else -0.3), 1),
            cintura_cm=round(CINTURA_INICIAL - 0.4 * s, 1),
            **_treino(s),
        )
        for s in range(1, 7)
    }


def _lenta() -> dict[int, ValoresRegisto]:
    return {
        s: ValoresRegisto(
            peso_kg=round(PESO_INICIAL - 0.1 * s, 1),
            cintura_cm=CINTURA_INICIAL - 0.5,
            **_treino(s),
        )
        for s in range(1, 7)
    }


def _rapida() -> dict[int, ValoresRegisto]:
    return {
        s: ValoresRegisto(
            peso_kg=PESO_INICIAL - 1.0 * s,
            cintura_cm=round(CINTURA_INICIAL - 0.8 * s, 1),
            **_treino(s),
        )
        for s in range(1, 7)
    }


def _manutencao() -> dict[int, ValoresRegisto]:
    registos = {
        s: ValoresRegisto(
            peso_kg=round(PESO_INICIAL - RITMO_LINHA * s, 1),
            cintura_cm=round(CINTURA_INICIAL - 0.5 * s, 1),
            **_treino(s),
        )
        for s in range(1, 17)
    }
    registos[20] = ValoresRegisto(peso_kg=90.5, cintura_cm=103.5, **_treino(20))
    registos[23] = ValoresRegisto(peso_kg=91.0, cintura_cm=104.0, **_treino(23))
    return registos


# (semanas já passadas desde a criação do plano, registos)
CENARIOS = {
    "normal": (6, _normal),
    "lenta": (6, _lenta),
    "rapida": (6, _rapida),
    "manutencao": (22, _manutencao),
}


def _dia(inicio: date, semana: int) -> date:
    """O primeiro dia da semana: a semana atual do cenário começa hoje, nunca no futuro."""
    return inicio + timedelta(days=7 * (semana - 1))


def criar(nome: str, hoje: date) -> tuple[int, int]:
    """Cria o plano e os registos do cenário; devolve (utilizador, plano)."""
    config = obter_configuracao()
    if config.ambiente != "local" or not config.database_url.startswith("sqlite"):
        sys.exit("Só corre com AMBIENTE=local e numa base SQLite: nunca com dados reais.")
    semanas, registos = CENARIOS[nome]
    inicio = hoje - timedelta(days=7 * semanas)
    q = Questionario.model_validate_json(PERSONA.read_text("utf-8"))
    res = gerar_plano_verificado(q, ProvedorSimulado(), progresso=lambda _: None)
    motor = criar_motor(config.database_url)
    migrar(motor)
    with fabrica_sessoes(motor).begin() as s:
        utilizador = r.entrar(s, UTILIZADOR_LOCAL)
        assert isinstance(utilizador, Utilizador)
        uid = utilizador.id
        r.guardar_consentimentos(s, uid, "ficticio")
        qid = r.guardar_questionario(s, uid, q)
        plano = r.guardar_plano(s, uid, qid, res.plano, res.estrategia, res.modelo)
        linha = s.get(PlanoGuardado, plano.id)
        assert linha is not None
        meio_dia = datetime.combine(inicio, time(12), tzinfo=ZoneInfo("Europe/Lisbon"))
        linha.criado_em = meio_dia.astimezone(UTC)
        s.flush()
        for semana, valores in registos().items():
            r.guardar_registo(s, uid, plano.id, _dia(inicio, semana), valores, hoje)
    motor.dispose()
    return uid, plano.id


def main() -> None:
    if len(sys.argv) != 2 or sys.argv[1] not in CENARIOS:
        sys.exit(f"Indique um cenário: {', '.join(CENARIOS)}")
    criar(sys.argv[1], datetime.now(ZoneInfo("Europe/Lisbon")).date())
    print(f"Cenário «{sys.argv[1]}» criado para o utilizador local fictício.")


if __name__ == "__main__":
    main()
