"""Tarefa diária dos lembretes por email (Fase 8): python -m vigoria.tarefas.lembretes.

Corre uma vez por dia como serviço cron do Railway (produção, Fase 10B; docs/GUIA_PRODUCAO.md)
e, só à mão, no GitHub Actions (.github/workflows/lembretes.yml, demo). Para cada pessoa
com acompanhamento e lembretes ligados, e na lista de convidados, decide pelas regras L1 a L5
(regras/lembretes.py) se lhe cabe um lembrete hoje. Grava o envio e só confirma a gravação
se o Brevo aceitar o email; se falhar, tenta de novo no dia seguinte.

A saída mostra só identificadores técnicos (os registos do Actions podem ser públicos):
nunca emails nem dados de saúde. Com --simular, não envia nem grava nada.

Com --testar-envio, manda já um lembrete de exemplo (o primeiro) a quem tem os lembretes
ligados e está na lista de convidados, sem olhar às regras L1 a L5 e sem o gravar. Serve
para ver o email a sério; se houver mais de uma pessoa, é preciso escolher com --utilizador.
"""

import argparse
import logging
import sys
from collections.abc import Callable, Sequence
from datetime import UTC, datetime

from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from vigoria.config import Configuracao, obter_configuracao
from vigoria.contas.entrada import AVISO_LISTA_VAZIA, email_convidado, ninguem_entra
from vigoria.dados import repositorios as r
from vigoria.dados.bd import criar_motor, fabrica_sessoes, migrar
from vigoria.notificacoes import brevo
from vigoria.notificacoes.lembrete import email_lembrete
from vigoria.notificacoes.token import gerar_token
from vigoria.regras.lembretes import lembrete_devido
from vigoria.regras.progresso import dia_em_lisboa, inicio_do_plano

registo = logging.getLogger(__name__)

Enviar = Callable[..., str]  # a assinatura de brevo.enviar


class Resumo(BaseModel):
    candidatos: int = 0
    nao_convidados: int = 0
    sem_lembrete: int = 0
    simulados: int = 0
    enviados: int = 0
    ja_enviados: int = 0  # outra execução gravou-o entretanto
    falhados: int = 0


def _um_clique(config: Configuracao) -> bool:
    """Cancelamento num clique (RFC 8058) só em produção, onde o Caddy encaminha /cancelar
    para o serviço que aceita o POST; na demo, a ligação abre a página Streamlit."""
    return config.ambiente == "producao"


def _faltas(config: Configuracao) -> list[str]:
    """As variáveis que faltam para enviar a sério."""
    faltas = []
    if config.brevo_api_key is None or not config.brevo_api_key.get_secret_value():
        faltas.append("BREVO_API_KEY")
    if not config.email_remetente:
        faltas.append("EMAIL_REMETENTE")
    if config.vigoria_segredo_lembretes is None:
        faltas.append("VIGORIA_SEGREDO_LEMBRETES")
    if config.ambiente != "local" and not config.app_url.startswith("https://"):
        faltas.append("APP_URL (endereço público https da app)")
    return faltas


def executar(
    fabrica: sessionmaker[Session],
    config: Configuracao,
    agora: datetime,
    *,
    simular: bool,
    enviar: Enviar = brevo.enviar,
    escrever: Callable[[str], None] = print,
) -> Resumo:
    """Uma execução; `agora` (com fuso) dá o dia em Lisboa e a hora gravada nos envios."""
    resumo = Resumo()
    hoje = dia_em_lisboa(agora)
    permitidos, acesso = config.vigoria_emails_permitidos, config.vigoria_acesso
    if ninguem_entra(permitidos, acesso):
        escrever(f"{AVISO_LISTA_VAZIA}: ninguém recebe lembretes.")
    with fabrica.begin() as s:
        destinatarios = r.destinatarios_de_lembretes(s)
    for d in destinatarios:
        resumo.candidatos += 1
        if not email_convidado(d.email, permitidos, acesso):
            resumo.nao_convidados += 1
            continue
        with fabrica.begin() as s:
            lembrete = lembrete_devido(
                inicio_do_plano(d.plano_criado_em),
                hoje,
                d.frequencia,
                r.semanas_com_registo(s, d.utilizador_id, d.plano_id),
                r.lembretes_enviados(s, d.utilizador_id, d.plano_id),
            )
        if lembrete is None:
            resumo.sem_lembrete += 1
            continue
        linha = (
            f"utilizador {d.utilizador_id}, plano {d.plano_id}, "
            f"semanas {lembrete.semanas[0]} a {lembrete.semanas[1]}, lembrete {lembrete.numero}"
        )
        if simular:
            resumo.simulados += 1
            escrever(f"{linha}: simulado")
            continue
        assert config.brevo_api_key is not None and config.vigoria_segredo_lembretes is not None
        email = email_lembrete(
            d.email,
            lembrete.numero,
            config.app_url,
            gerar_token(d.utilizador_id, d.sub, config.vigoria_segredo_lembretes, agora),
            um_clique=_um_clique(config),
        )
        try:
            # Grava e envia na mesma transação: se o Brevo falhar, a gravação é desfeita.
            with fabrica.begin() as s:
                r.registar_lembrete(s, d.utilizador_id, d.plano_id, lembrete, agora)
                enviar(
                    email,
                    chave=config.brevo_api_key,
                    remetente=config.email_remetente,
                    nome_remetente=config.email_nome_remetente,
                )
        except IntegrityError:
            resumo.ja_enviados += 1
            escrever(f"{linha}: já enviado por outra execução")
        except brevo.ErroEnvio as erro:
            resumo.falhados += 1
            escrever(f"{linha}: falhou ({erro.tipo})")
        else:
            resumo.enviados += 1
            escrever(f"{linha}: enviado")
    escrever(
        f"Hoje ({hoje.isoformat()}): {resumo.candidatos} com lembretes ligados, "
        f"{resumo.nao_convidados} fora da lista de convidados, "
        f"{resumo.sem_lembrete} sem lembrete devido, {resumo.simulados} simulados, "
        f"{resumo.enviados} enviados, {resumo.ja_enviados} já enviados, "
        f"{resumo.falhados} falhados."
    )
    return resumo


def testar_envio(
    fabrica: sessionmaker[Session],
    config: Configuracao,
    *,
    utilizador_id: int | None,
    simular: bool,
    agora: datetime | None = None,
    enviar: Enviar = brevo.enviar,
    escrever: Callable[[str], None] = print,
) -> int:
    """Envia um lembrete de exemplo, sem regras nem gravação. Devolve o código de saída."""
    permitidos, acesso = config.vigoria_emails_permitidos, config.vigoria_acesso
    with fabrica.begin() as s:
        destinatarios = [
            d
            for d in r.destinatarios_de_lembretes(s)
            if email_convidado(d.email, permitidos, acesso)
        ]
    if utilizador_id is not None:
        destinatarios = [d for d in destinatarios if d.utilizador_id == utilizador_id]
    if not destinatarios:
        escrever(
            "Teste: ninguém com lembretes ligados e na lista de convidados"
            + (f" com o utilizador {utilizador_id}." if utilizador_id is not None else ".")
        )
        return 1
    if len(destinatarios) > 1:
        ids = ", ".join(str(d.utilizador_id) for d in destinatarios)
        escrever(f"Teste: há {len(destinatarios)} pessoas ({ids}); escolha uma com --utilizador.")
        return 2
    (d,) = destinatarios
    agora = datetime.now(UTC) if agora is None else agora
    if simular:
        escrever(f"Teste: utilizador {d.utilizador_id}, lembrete de exemplo: simulado")
        return 0
    assert config.brevo_api_key is not None and config.vigoria_segredo_lembretes is not None
    email = email_lembrete(
        d.email,
        1,
        config.app_url,
        gerar_token(d.utilizador_id, d.sub, config.vigoria_segredo_lembretes, agora),
        um_clique=_um_clique(config),
    )
    try:
        enviar(
            email,
            chave=config.brevo_api_key,
            remetente=config.email_remetente,
            nome_remetente=config.email_nome_remetente,
        )
    except brevo.ErroEnvio as erro:
        escrever(f"Teste: utilizador {d.utilizador_id}, lembrete de exemplo: falhou ({erro.tipo})")
        return 1
    escrever(f"Teste: utilizador {d.utilizador_id}, lembrete de exemplo: enviado")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m vigoria.tarefas.lembretes",
        description="Envia os lembretes de registo em falta (REGRAS_DOMINIO §9).",
    )
    parser.add_argument(
        "--simular",
        action="store_true",
        help="mostra quem receberia que lembrete, sem enviar nem gravar",
    )
    parser.add_argument(
        "--testar-envio",
        action="store_true",
        help="manda já um lembrete de exemplo, sem regras e sem gravar",
    )
    parser.add_argument(
        "--utilizador",
        type=int,
        help="com --testar-envio: o id do utilizador, se houver mais de um",
    )
    args = parser.parse_args(argv)
    if args.utilizador is not None and not args.testar_envio:
        parser.error("--utilizador só serve com --testar-envio")
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    config = obter_configuracao()
    faltas = _faltas(config)
    if faltas and not args.simular:
        print(f"Faltam variáveis para enviar: {', '.join(faltas)}.", file=sys.stderr)
        return 2
    motor = criar_motor(config.database_url)
    try:
        # Fora do ambiente local, as migrações são do serviço web (arranque); o cron não as
        # corre, para não haver duas a mexer na mesma base ao mesmo tempo (Fase 10B).
        if config.ambiente == "local":
            migrar(motor)
        if args.testar_envio:
            return testar_envio(
                fabrica_sessoes(motor),
                config,
                utilizador_id=args.utilizador,
                simular=args.simular,
            )
        resumo = executar(fabrica_sessoes(motor), config, datetime.now(UTC), simular=args.simular)
    finally:
        motor.dispose()
    return 1 if resumo.falhados else 0


if __name__ == "__main__":
    sys.exit(main())
