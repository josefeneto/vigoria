"""Tarefa diária dos lembretes (tarefas/lembretes.py), com SQLite em memória e o Brevo
simulado: nenhum envio real."""

from collections.abc import Iterator
from datetime import UTC, date, datetime, timedelta

import pytest
from pydantic import SecretStr
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from vigoria.config import Configuracao
from vigoria.dados import repositorios as r
from vigoria.dados.bd import criar_motor, fabrica_sessoes, migrar
from vigoria.dados.tabelas import (
    LembreteEnviado,
    PlanoGuardado,
    QuestionarioGuardado,
    RegistoProgresso,
    Utilizador,
)
from vigoria.notificacoes import brevo
from vigoria.notificacoes.brevo import Email, ErroEnvio, TipoErroEnvio
from vigoria.notificacoes.token import token_valido
from vigoria.tarefas import lembretes

INICIO = date(2026, 1, 5)
SEGREDO = "s" * 48
# Semana 1 terminou a 11/01; 2 dias depois do prazo: primeiro lembrete.
DIA_DO_PRIMEIRO = INICIO + timedelta(days=6 + 2)
DIA_DO_SEGUNDO = INICIO + timedelta(days=6 + 5)


@pytest.fixture
def fabrica() -> Iterator[sessionmaker[Session]]:
    motor = criar_motor("sqlite://")
    migrar(motor)
    yield fabrica_sessoes(motor)
    motor.dispose()


def _config(**alteracoes: object) -> Configuracao:
    valores: dict[str, object] = {
        "_env_file": None,
        "ambiente": "local",
        "vigoria_provedor_llm": "gemini",
        "vigoria_provedor_reserva": None,
        "vigoria_utilizador_local": False,
        "brevo_api_key": "xkeysib-teste",
        "email_remetente": "geral@vigoria.pt",
        "app_url": "https://vigoria.exemplo",
        "vigoria_segredo_lembretes": SEGREDO,
        "vigoria_emails_permitidos": "",
    }
    return Configuracao(**(valores | alteracoes))  # type: ignore[arg-type]


def _pessoa(
    s: Session,
    n: int,
    *,
    ativo: bool = True,
    lembretes_email: bool = True,
    planos: int = 1,
    inicio: date = INICIO,
) -> tuple[int, int]:
    """Uma conta com planos (o último começa em `inicio`). Devolve (utilizador, último plano)."""
    u = Utilizador(
        sub=f"auth0|{n}",
        fornecedor="auth0",
        email=f"pessoa{n}@exemplo.pt",
        acompanhamento_ativo=ativo,
        lembretes_email=lembretes_email,
    )
    s.add(u)
    s.flush()
    q = QuestionarioGuardado(utilizador_id=u.id, respostas={})
    s.add(q)
    s.flush()
    plano_id = 0
    for i in range(planos):
        dia = inicio - timedelta(days=7 * (planos - 1 - i))
        p = PlanoGuardado(
            utilizador_id=u.id,
            questionario_id=q.id,
            conteudo={},
            estrategia={},
            versao_prompt="v",
            provedor="simulado",
            modelo="m",
            criado_em=datetime(dia.year, dia.month, dia.day, 12, tzinfo=UTC),
        )
        s.add(p)
        s.flush()
        plano_id = p.id
    return u.id, plano_id


class _Brevo:
    """Substitui brevo.enviar: guarda os emails, ou falha."""

    def __init__(self, falha: TipoErroEnvio | None = None) -> None:
        self.emails: list[Email] = []
        self.falha = falha

    def __call__(self, email: Email, **_opcoes: object) -> str:
        if self.falha is not None:
            raise ErroEnvio(self.falha, 503)
        self.emails.append(email)
        return f"id-{len(self.emails)}"


def _correr(
    fabrica: sessionmaker[Session],
    hoje: date,
    *,
    simular: bool = False,
    config: Configuracao | None = None,
    envio: _Brevo | None = None,
) -> tuple[lembretes.Resumo, _Brevo, list[str]]:
    envio = envio or _Brevo()
    linhas: list[str] = []
    agora = datetime(hoje.year, hoje.month, hoje.day, 9, 7, tzinfo=UTC)
    resumo = lembretes.executar(
        fabrica, config or _config(), agora, simular=simular, enviar=envio, escrever=linhas.append
    )
    return resumo, envio, linhas


def _contar(fabrica: sessionmaker[Session]) -> int:
    with fabrica.begin() as s:
        return int(s.scalar(select(func.count()).select_from(LembreteEnviado)) or 0)


# ---------------------------------------------------------------- Quem recebe


def test_recebe_quem_tem_tudo_ligado(fabrica: sessionmaker[Session]) -> None:
    with fabrica.begin() as s:
        uid, plano_id = _pessoa(s, 1)
    resumo, envio, linhas = _correr(fabrica, DIA_DO_PRIMEIRO)
    assert resumo.enviados == 1
    (email,) = envio.emails
    assert email.para == "pessoa1@exemplo.pt"
    token = email.cabecalhos["List-Unsubscribe"].split("?t=")[1].rstrip(">")
    assert token_valido(token, "auth0|1", SecretStr(SEGREDO))
    with fabrica.begin() as s:
        assert r.lembretes_enviados(s, uid, plano_id)[0].semanas == (1, 1)
    assert f"utilizador {uid}, plano {plano_id}, semanas 1 a 1, lembrete 1: enviado" in linhas


def test_nao_recebe_com_acompanhamento_ou_lembretes_desligados(
    fabrica: sessionmaker[Session],
) -> None:
    with fabrica.begin() as s:
        _pessoa(s, 1, ativo=False)
        _pessoa(s, 2, lembretes_email=False)
    resumo, envio, _ = _correr(fabrica, DIA_DO_PRIMEIRO)
    assert resumo.candidatos == 0
    assert envio.emails == []


def test_nao_recebe_sem_plano(fabrica: sessionmaker[Session]) -> None:
    with fabrica.begin() as s:
        s.add(Utilizador(sub="auth0|9", fornecedor="auth0", email="semplano@exemplo.pt"))
    resumo, envio, _ = _correr(fabrica, DIA_DO_PRIMEIRO)
    assert resumo.candidatos == 0 and envio.emails == []


def test_nao_recebe_com_o_registo_feito(fabrica: sessionmaker[Session]) -> None:
    with fabrica.begin() as s:
        uid, plano_id = _pessoa(s, 1)
        s.add(
            RegistoProgresso(
                utilizador_id=uid, plano_id=plano_id, semana=1, data=INICIO, valores={}
            )
        )
    resumo, envio, _ = _correr(fabrica, DIA_DO_PRIMEIRO)
    assert resumo.sem_lembrete == 1 and envio.emails == []


def test_so_o_plano_mais_recente(fabrica: sessionmaker[Session]) -> None:
    """O plano antigo (iniciado 3 semanas antes) teria lembretes; o novo ainda não."""
    with fabrica.begin() as s:
        _pessoa(s, 1, planos=2, inicio=DIA_DO_PRIMEIRO - timedelta(days=3))
    resumo, envio, _ = _correr(fabrica, DIA_DO_PRIMEIRO)
    assert resumo.sem_lembrete == 1 and envio.emails == []


def test_na_demonstracao_so_os_convidados(fabrica: sessionmaker[Session]) -> None:
    with fabrica.begin() as s:
        _pessoa(s, 1)
        _pessoa(s, 2)
    config = _config(ambiente="demo", vigoria_emails_permitidos=" Pessoa2@Exemplo.pt ")
    resumo, envio, _ = _correr(fabrica, DIA_DO_PRIMEIRO, config=config)
    assert [e.para for e in envio.emails] == ["pessoa2@exemplo.pt"]
    assert resumo.nao_convidados == 1


def test_na_demonstracao_sem_lista_ninguem_recebe(fabrica: sessionmaker[Session]) -> None:
    with fabrica.begin() as s:
        _pessoa(s, 1)
    resumo, envio, linhas = _correr(fabrica, DIA_DO_PRIMEIRO, config=_config(ambiente="demo"))
    assert envio.emails == [] and resumo.nao_convidados == 1
    assert any("ninguém recebe" in linha for linha in linhas)


def test_em_producao_sem_lista_todos_recebem(fabrica: sessionmaker[Session]) -> None:
    with fabrica.begin() as s:
        _pessoa(s, 1)
    resumo, _, _ = _correr(fabrica, DIA_DO_PRIMEIRO, config=_config(ambiente="producao"))
    assert resumo.enviados == 1


# ---------------------------------------------------------------- Sem repetir


def test_duas_execucoes_no_mesmo_dia_nao_repetem(fabrica: sessionmaker[Session]) -> None:
    with fabrica.begin() as s:
        _pessoa(s, 1)
    _correr(fabrica, DIA_DO_PRIMEIRO)
    resumo, envio, _ = _correr(fabrica, DIA_DO_PRIMEIRO)
    assert resumo.sem_lembrete == 1 and envio.emails == []
    assert _contar(fabrica) == 1


def test_maximo_de_2_por_periodo(fabrica: sessionmaker[Session]) -> None:
    with fabrica.begin() as s:
        _pessoa(s, 1)
    enviados = 0
    for dias in range(6):  # do 2.º ao 7.º dia depois do prazo (L3)
        resumo, envio, _ = _correr(fabrica, DIA_DO_PRIMEIRO + timedelta(days=dias))
        enviados += resumo.enviados
        if dias == 3:  # o quinto dia depois do prazo
            assert "último lembrete" in envio.emails[0].texto
    assert enviados == 2
    assert _contar(fabrica) == 2


def test_envio_falhado_nao_grava_e_tenta_amanha(fabrica: sessionmaker[Session]) -> None:
    with fabrica.begin() as s:
        _pessoa(s, 1)
    resumo, _, linhas = _correr(fabrica, DIA_DO_PRIMEIRO, envio=_Brevo(TipoErroEnvio.INDISPONIVEL))
    assert resumo.falhados == 1 and _contar(fabrica) == 0
    assert any("falhou (indisponivel)" in linha for linha in linhas)
    resumo, envio, _ = _correr(fabrica, DIA_DO_PRIMEIRO + timedelta(days=1))
    assert resumo.enviados == 1 and len(envio.emails) == 1


# ---------------------------------------------------------------- Simular


def test_simular_nao_envia_nem_grava_nem_mostra_emails(fabrica: sessionmaker[Session]) -> None:
    with fabrica.begin() as s:
        uid, plano_id = _pessoa(s, 1)
    resumo, envio, linhas = _correr(fabrica, DIA_DO_PRIMEIRO, simular=True)
    assert resumo.simulados == 1 and envio.emails == [] and _contar(fabrica) == 0
    assert f"utilizador {uid}, plano {plano_id}, semanas 1 a 1, lembrete 1: simulado" in linhas
    assert not any("@" in linha or "auth0|" in linha for linha in linhas)


def test_saida_sem_emails_ao_enviar(fabrica: sessionmaker[Session]) -> None:
    with fabrica.begin() as s:
        _pessoa(s, 1)
    _, _, linhas = _correr(fabrica, DIA_DO_PRIMEIRO)
    assert not any("@" in linha or "auth0|" in linha for linha in linhas)


# ---------------------------------------------------------------- Linha de comandos


@pytest.fixture
def ambiente(monkeypatch: pytest.MonkeyPatch, tmp_path: object) -> Iterator[None]:
    from vigoria.config import obter_configuracao

    for nome, valor in {
        "AMBIENTE": "local",
        "VIGORIA_PROVEDOR_LLM": "gemini",
        "VIGORIA_PROVEDOR_RESERVA": "",
        "VIGORIA_UTILIZADOR_LOCAL": "0",
        "DATABASE_URL": f"sqlite:///{tmp_path}/l.db",
        "BREVO_API_KEY": "",
        "EMAIL_REMETENTE": "",
        "VIGORIA_SEGREDO_LEMBRETES": "",
        "VIGORIA_EMAILS_PERMITIDOS": "",
    }.items():
        monkeypatch.setenv(nome, valor)
    obter_configuracao.cache_clear()
    yield
    obter_configuracao.cache_clear()


def test_sem_configuracao_so_simula(
    ambiente: None, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(brevo, "enviar", _Brevo())
    assert lembretes.main([]) == 2
    erro = capsys.readouterr().err
    assert "BREVO_API_KEY" in erro and "VIGORIA_SEGREDO_LEMBRETES" in erro
    assert lembretes.main(["--simular"]) == 0
    assert "0 com lembretes ligados" in capsys.readouterr().out


def test_o_dia_e_o_de_lisboa(fabrica: sessionmaker[Session]) -> None:
    """No verão, 23h30 UTC já é o dia seguinte em Lisboa (00h30)."""
    inicio = date(2026, 7, 6)
    with fabrica.begin() as s:
        _pessoa(s, 1, inicio=inicio)
    vespera = inicio + timedelta(days=6 + 1)  # 1 dia depois do prazo da semana 1
    for hora, enviados in ((22, 0), (23, 1)):
        agora = datetime(vespera.year, vespera.month, vespera.day, hora, 30, tzinfo=UTC)
        resumo = lembretes.executar(
            fabrica, _config(), agora, simular=False, enviar=_Brevo(), escrever=lambda _: None
        )
        assert resumo.enviados == enviados, hora


def test_segredo_curto_e_recusado() -> None:
    from pydantic import ValidationError

    with pytest.raises(ValidationError, match="32 caracteres"):
        _config(vigoria_segredo_lembretes="curto")
    assert _config(vigoria_segredo_lembretes="").vigoria_segredo_lembretes is None
    assert _config(app_url="https://vigoria.exemplo/").app_url == "https://vigoria.exemplo"


def test_fora_do_local_exige_o_endereco_publico() -> None:
    assert lembretes._faltas(_config(ambiente="demo")) == []
    assert lembretes._faltas(_config(ambiente="demo", app_url="")) == [
        "APP_URL (endereço público https da app)"
    ]
    assert lembretes._faltas(_config(app_url="http://localhost:8501")) == []
