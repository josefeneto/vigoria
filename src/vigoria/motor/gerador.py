"""Gerador (papel 3, LLM): monta o pedido, chama o provedor e monta o Plano.

Fase 4C: o treino e a semana-tipo são do motor (motor/treino.py e motor/semana.py);
os hábitos, a hidratação e o acompanhamento são texto fixo (alimentacao.yaml). A LLM só
personaliza: resumo, marcos de força, alimentação e notas. O pedido leva a estratégia,
o questionário sem identificadores nem consentimentos, os princípios alimentares, o foco
alimentar de cada fase e um resumo do treino (só contexto), em JSON compacto.
"""

import json
import re
from functools import cache
from importlib.resources import files
from importlib.resources.abc import Traversable
from typing import Any

from pydantic import BaseModel, ConfigDict

from vigoria.conteudo.carregar import carregar_alimentacao, carregar_programa
from vigoria.llm.base import ProvedorLLM
from vigoria.modelos.estrategia import Estrategia
from vigoria.modelos.plano import (
    Acompanhamento,
    Habito,
    HidratacaoPlano,
    MarcoPlano,
    OrientacaoAlimentar,
    Plano,
    PlanoGerado,
    Treino,
)
from vigoria.modelos.questionario import FrequenciaRegisto, Questionario
from vigoria.motor.semana import construir_semana
from vigoria.motor.treino import construir_treino

# Dados do pacote (vigoria/prompts/): funcionam também quando instalado sem «-e».
PROMPTS = files("vigoria.prompts")
PROMPT_SISTEMA = PROMPTS.joinpath("gerador_sistema.md")
PROMPT_CORRECAO = PROMPTS.joinpath("gerador_correcao.md")
_CABECALHO = re.compile(r"\A<!--\s*versao:\s*(\d+)\b.*?-->\s*", re.DOTALL)

# Lista explícita: um campo novo do questionário não segue para a LLM por omissão.
# Ficam de fora os consentimentos e as preferências de lembretes.
CAMPOS_QUESTIONARIO = frozenset(
    {
        "sexo",
        "idade",
        "altura_cm",
        "peso_kg",
        "sono_horas",
        "cintura_cm",
        "atividade_atual",
        "condicoes",
        "condicoes_controladas",
        "osteoporose_risco",
        "dor_articular_zonas",
        "medicacao_afeta_fc",
        "limitacoes",
        "limitacoes_gravidade",
        "equipamento",
        "halteres_kg",
        "dias_semana",
        "minutos_dia",
        "preferencias",
        "refeicoes",
        "restricoes_alimentares",
        "agua_litros",
        "bebidas_acucaradas_litros",
        "vinho_copos_dia",
        "espirituosas_dl_dia",
        "pao_por_dia",
        "doces_por_semana",
        "peso_alvo_kg",
        "cintura_alvo_cm",
        "objetivo_muscular",
        "intensidade_pedida",
        "frequencia_registo",
    }
)
# Texto livre: segue só como contexto, num bloco à parte (REGRAS_DOMINIO §1.1).
CAMPOS_TEXTO_LIVRE = (
    "condicoes_outras",
    "dor_articular_outra",
    "medicacao_notas",
    "limitacoes_outra",
    "restricoes_outra",
)
MAX_TEXTO_LIVRE = 500  # caracteres, somando todos os campos de texto livre
REMOVIDO = "[removido]"
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
# Pelo menos 9 algarismos, com espaços, pontos, hífenes ou parênteses pelo meio
# (+351 912 345 678, 00 44 20 7946 0958, 21-123-4567). Datas e tensões não chegam a 9.
_TELEFONE = re.compile(r"(?<!\w)(?:\+|00)?\d(?:[\s().-]{0,2}\d){8,}(?!\w)")
FASES = (1, 2, 3, 4)


class ErroGeracao(Exception):
    """Não é possível gerar o plano; a mensagem pode ser mostrada ao utilizador."""


class PromptSistema(BaseModel):
    model_config = ConfigDict(frozen=True)

    versao: str
    texto: str


class Pedido(BaseModel):
    """O que segue para a LLM: prompt de sistema e conteúdo do pedido (JSON em texto)."""

    model_config = ConfigDict(frozen=True)

    versao_prompt: str
    sistema: str
    conteudo: str


def _carregar_prompt(ficheiro: Traversable) -> PromptSistema:
    """Lê um prompt de vigoria/prompts/ e separa a versão do cabeçalho do texto."""
    texto = ficheiro.read_text(encoding="utf-8")
    cabecalho = _CABECALHO.match(texto)
    if cabecalho is None:
        raise ErroGeracao(f"{ficheiro.name}: falta o cabeçalho com a versão")
    return PromptSistema(versao=cabecalho.group(1), texto=texto[cabecalho.end() :].strip())


@cache
def carregar_prompt_sistema() -> PromptSistema:
    """vigoria/prompts/gerador_sistema.md."""
    return _carregar_prompt(PROMPT_SISTEMA)


@cache
def carregar_prompt_correcao() -> PromptSistema:
    """vigoria/prompts/gerador_correcao.md: acrescentado ao pedido na regeneração."""
    return _carregar_prompt(PROMPT_CORRECAO)


# ---------------------------------------------------------------- Pedido


def dados_questionario(q: Questionario) -> dict[str, Any]:
    """Respostas necessárias ao plano, sem consentimentos; texto livre à parte."""
    dados = q.model_dump(mode="json", include=set(CAMPOS_QUESTIONARIO))
    livre: dict[str, str] = {}
    restante = MAX_TEXTO_LIVRE
    for campo in CAMPOS_TEXTO_LIVRE:
        texto = limpar_texto_livre(getattr(q, campo))[:restante]
        if texto:
            livre[campo] = texto
            restante -= len(texto)
    if livre:
        dados["contexto_texto_livre"] = livre
    return dados


def limpar_texto_livre(texto: str) -> str:
    """Substitui emails e números de telefone por «[removido]» (nunca seguem para a LLM)."""
    texto = _EMAIL.sub(REMOVIDO, texto)
    return _TELEFONE.sub(REMOVIDO, texto).strip()


def resumo_treino(treino: Treino) -> dict[str, Any]:
    """Nomes dos exercícios por fase: só contexto para a LLM (o treino é do motor)."""
    return {
        f"fase_{f.numero}": {
            "nome": f.nome,
            "forca": [x.nome for x in f.forca],
            "cardio_finalizador": f.cardio_finalizador.nome if f.cardio_finalizador else None,
        }
        for f in treino.fases
    }


def conteudo_pedido(q: Questionario, e: Estrategia, treino: Treino | None = None) -> dict[str, Any]:
    """O pedido em estrutura Python (útil para testes e para o mostrar na CLI)."""
    if not e.pode_gerar_plano:
        raise ErroGeracao("A estratégia não permite gerar plano: " + " ".join(e.motivos))
    treino = construir_treino(e, q) if treino is None else treino
    return {
        "estrategia": e.model_dump(mode="json", exclude={"pode_gerar_plano"}),
        "questionario": dados_questionario(q),
        "alimentacao": {
            "principios": carregar_alimentacao().principios.model_dump(mode="json"),
            "foco_por_fase": [
                {"fase": f.numero, "nome": f.nome, **f.foco_alimentar.model_dump(mode="json")}
                for f in carregar_programa().fases
            ],
        },
        "treino_resumo": resumo_treino(treino),
    }


def montar_pedido(q: Questionario, e: Estrategia, treino: Treino | None = None) -> Pedido:
    """Prompt de sistema e pedido em JSON compacto (sem indentação), prontos a enviar."""
    prompt = carregar_prompt_sistema()
    conteudo = json.dumps(conteudo_pedido(q, e, treino), ensure_ascii=False, separators=(",", ":"))
    return Pedido(
        versao_prompt=prompt.versao,
        sistema=prompt.texto,
        conteudo=f"Pedido de plano (JSON):\n{conteudo}",
    )


# ---------------------------------------------------------------- Plano


def montar_plano(
    gerado: PlanoGerado,
    e: Estrategia,
    q: Questionario,
    versao_prompt: str,
    provedor: str,
    treino: Treino | None = None,
) -> Plano:
    """Junta ao texto da LLM o treino e a semana do motor, os números da Estrategia e os
    textos fixos (alimentacao.yaml e avisos)."""
    if e.indicadores is None:
        raise ErroGeracao("A estratégia não tem indicadores: não é possível montar o plano.")
    forca = {
        4: gerado.marcos_forca.semana_4,
        8: gerado.marcos_forca.semana_8,
        12: gerado.marcos_forca.semana_12,
        16: gerado.marcos_forca.semana_16,
    }
    marcos = tuple(
        MarcoPlano(
            semana=m.semana,
            fase=m.fase,
            peso_indicativo_kg=m.peso_indicativo_kg,
            cintura=m.cintura,
            forca_resistencia=forca[m.semana],
        )
        for m in e.marcos
    )
    alimentacao = carregar_alimentacao()
    hidratacao = e.indicadores.hidratacao
    # Com doença renal não há valores: nem dicas genéricas sobre beber mais (§2).
    dicas = alimentacao.hidratacao_dicas if hidratacao.central_ml is not None else ()
    a = alimentacao.acompanhamento
    if q.frequencia_registo is FrequenciaRegisto.SEMANAL:
        acompanhamento = Acompanhamento(frequencia=q.frequencia_registo, indicadores=a.semanal)
    else:
        acompanhamento = Acompanhamento(
            frequencia=q.frequencia_registo,
            indicadores=a.quatro_semanas,
            perguntas_revisao=a.perguntas_revisao,
        )
    return Plano(
        versao_prompt=versao_prompt,
        provedor=provedor,
        resumo=gerado.resumo,
        marcos=marcos,
        semana_tipo=construir_semana(e, q),
        treino=construir_treino(e, q) if treino is None else treino,
        alimentacao=OrientacaoAlimentar(
            ajustes_refeicoes=tuple(gerado.ajustes_refeicoes),
            bebidas_e_alcool=gerado.bebidas_e_alcool,
            prioridades_por_fase=tuple(gerado.prioridades_alimentares),
        ),
        proteina=e.indicadores.proteina,
        hidratacao=HidratacaoPlano(valores=hidratacao, dicas=dicas),
        habitos=tuple(Habito(titulo=h.titulo, descricao=h.descricao) for h in alimentacao.habitos),
        acompanhamento=acompanhamento,
        notas_personalizadas=tuple(gerado.notas_personalizadas),
        avisos=e.avisos,
    )


def montar_pedido_correcao(pedido: Pedido, motivos: tuple[str, ...]) -> Pedido:
    """O mesmo pedido, com os motivos da rejeição anterior (vigoria/prompts/gerador_correcao.md)."""
    correcao = carregar_prompt_correcao()
    lista = "\n".join(f"- {m}" for m in motivos)
    texto = correcao.texto.replace("{motivos}", lista)
    return Pedido(
        versao_prompt=f"{pedido.versao_prompt} (correção {correcao.versao})",
        sistema=pedido.sistema,
        conteudo=f"{pedido.conteudo}\n\n{texto}",
    )


def gerar_plano(
    q: Questionario, e: Estrategia, provedor: ProvedorLLM, motivos: tuple[str, ...] = ()
) -> Plano:
    """Uma chamada à LLM; com `motivos`, é a regeneração depois de uma verificação falhada.

    A verificação e a decisão de regenerar são do pipeline (motor/pipeline.py).
    """
    if not e.pode_gerar_plano:
        raise ErroGeracao("A estratégia não permite gerar plano: " + " ".join(e.motivos))
    treino = construir_treino(e, q)
    pedido = montar_pedido(q, e, treino)
    if motivos:
        pedido = montar_pedido_correcao(pedido, motivos)
    gerado = provedor.gerar_json(pedido.sistema, pedido.conteudo, PlanoGerado)
    usado = provedor.ultimo_provedor or provedor.nome
    return montar_plano(gerado, e, q, pedido.versao_prompt, usado, treino)
