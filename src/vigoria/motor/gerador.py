"""Gerador (papel 3, LLM): monta o pedido, chama o provedor e monta o Plano.

O pedido leva só o necessário: a estratégia, o questionário sem identificadores nem
consentimentos, o catálogo dos exercícios permitidos (cada um uma só vez), os ids
permitidos por fase (motor/selecao.py) e o excerto relevante de fases.yaml e
alimentacao.yaml, em JSON compacto. Os números do plano vêm da Estrategia.
"""

import json
import re
from functools import cache
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict

from vigoria.conteudo.carregar import (
    carregar_alimentacao,
    carregar_exercicios,
    carregar_programa,
)
from vigoria.llm.base import ProvedorLLM
from vigoria.modelos.estrategia import Estrategia
from vigoria.modelos.plano import HidratacaoPlano, MarcoPlano, Plano, PlanoGerado
from vigoria.modelos.questionario import Equipamento as EquipamentoDeclarado
from vigoria.modelos.questionario import Questionario
from vigoria.motor.selecao import ExercicioPermitido, selecionar_exercicios

PROMPTS = Path(__file__).resolve().parents[3] / "prompts"
PROMPT_SISTEMA = PROMPTS / "gerador_sistema.md"
PROMPT_CORRECAO = PROMPTS / "gerador_correcao.md"
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


def _carregar_prompt(ficheiro: Path) -> PromptSistema:
    """Lê um prompt de prompts/ e separa a versão do cabeçalho do texto."""
    texto = ficheiro.read_text(encoding="utf-8")
    cabecalho = _CABECALHO.match(texto)
    if cabecalho is None:
        raise ErroGeracao(f"{ficheiro.name}: falta o cabeçalho com a versão")
    return PromptSistema(versao=cabecalho.group(1), texto=texto[cabecalho.end() :].strip())


@cache
def carregar_prompt_sistema() -> PromptSistema:
    """prompts/gerador_sistema.md."""
    return _carregar_prompt(PROMPT_SISTEMA)


@cache
def carregar_prompt_correcao() -> PromptSistema:
    """prompts/gerador_correcao.md: acrescentado ao pedido na regeneração."""
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


def _catalogo_exercicios(
    permitidos: dict[int, tuple[ExercicioPermitido, ...]], tem_halteres: bool
) -> dict[str, dict[str, Any]]:
    """Descrição de cada exercício permitido, uma só vez (pela ordem em que aparece)."""
    catalogo: dict[str, dict[str, Any]] = {}
    for lista in permitidos.values():
        for p in lista:
            if p.id in catalogo:
                continue
            ex = carregar_exercicios()[p.id]
            item: dict[str, Any] = {
                "nome": ex.nome,
                "descricao": ex.descricao,
                "grupo": str(ex.grupo),
            }
            if ex.equipamento:
                item["equipamento"] = [str(e) for e in ex.equipamento]
            if ex.variante_halteres and tem_halteres:
                item["variante_halteres"] = ex.variante_halteres
            catalogo[p.id] = item
    return catalogo


def _permitido_na_fase(p: ExercicioPermitido) -> dict[str, Any]:
    """O id e o que muda de fase para fase (substituições, esforço máximo, notas)."""
    item: dict[str, Any] = {"id": p.id}
    if p.substitui:
        item["substitui"] = list(p.substitui)
    if p.esforco_max is not None:
        item["esforco_max"] = p.esforco_max
    if p.notas:
        item["notas"] = list(p.notas)
    return item


def _id_permitido(id_: str, permitidos: tuple[ExercicioPermitido, ...]) -> str | None:
    """O próprio exercício, se permitido; senão, o que o substitui ou, para um exercício
    retirado (por exemplo, contraindicado), o primeiro permitido na cadeia de regressões."""
    ids_permitidos = {p.id for p in permitidos}
    if id_ in ids_permitidos:
        return id_
    for p in permitidos:
        if id_ in p.substitui:
            return p.id
    biblioteca = carregar_exercicios()
    atual = biblioteca[id_].regressao
    vistos = {id_}
    while atual is not None and atual not in vistos:
        if atual in ids_permitidos:
            return atual
        vistos.add(atual)
        atual = biblioteca[atual].regressao
    return None


def _fases_para_pedido(
    permitidos: dict[int, tuple[ExercicioPermitido, ...]],
) -> list[dict[str, Any]]:
    """As 4 fases de fases.yaml, com os exercícios de referência já trocados pelos permitidos."""
    fases = []
    for fase in carregar_programa().fases:
        referencia = []
        for posicao in fase.exercicios:
            ids = [
                id_
                for original in (posicao.id, *posicao.alternativas)
                if (id_ := _id_permitido(original, permitidos[fase.numero])) is not None
            ]
            if not ids:
                continue  # nem o exercício nem uma regressão são permitidos
            item: dict[str, Any] = {
                "id": ids[0],
                "series": posicao.series,
                "repeticoes": posicao.repeticoes,
                "descanso_s": f"{posicao.descanso_s.min}-{posicao.descanso_s.max}"
                if posicao.descanso_s.min != posicao.descanso_s.max
                else str(posicao.descanso_s.min),
            }
            if ids[0] != posicao.id:
                item["em_vez_de"] = posicao.id
            if alternativas := [i for i in dict.fromkeys(ids[1:]) if i != ids[0]]:
                item["alternativas"] = alternativas
            referencia.append(item)
        fases.append(
            {
                "numero": fase.numero,
                "nome": fase.nome,
                "semanas": f"{fase.semanas.min}-{fase.semanas.max}",
                "foco_treino": fase.foco_treino,
                "foco_estrategico": fase.foco_estrategico,
                "foco_alimentar": fase.foco_alimentar.model_dump(mode="json"),
                "esforco": f"{fase.esforco.min}-{fase.esforco.max}",
                "exercicios_referencia": referencia,
            }
        )
    return fases


def conteudo_pedido(q: Questionario, e: Estrategia) -> dict[str, Any]:
    """O pedido em estrutura Python (útil para testes e para o mostrar na CLI)."""
    if not e.pode_gerar_plano:
        raise ErroGeracao("A estratégia não permite gerar plano: " + " ".join(e.motivos))
    tem_halteres = EquipamentoDeclarado.HALTERES in e.restricoes.equipamento
    permitidos = {fase: selecionar_exercicios(e, fase) for fase in FASES}
    alimentacao = carregar_alimentacao()
    return {
        "estrategia": e.model_dump(mode="json", exclude={"pode_gerar_plano"}),
        "questionario": dados_questionario(q),
        "catalogo_exercicios": _catalogo_exercicios(permitidos, tem_halteres),
        "exercicios_permitidos": {
            f"fase_{fase}": [_permitido_na_fase(p) for p in lista]
            for fase, lista in permitidos.items()
        },
        "fases": _fases_para_pedido(permitidos),
        "estrutura_sessao": carregar_programa().estrutura_sessao.model_dump(mode="json"),
        "alimentacao": {
            "principios": alimentacao.principios.model_dump(mode="json"),
            "refeicao_simples": alimentacao.refeicao_simples.model_dump(mode="json"),
        },
    }


def montar_pedido(q: Questionario, e: Estrategia) -> Pedido:
    """Prompt de sistema e pedido em JSON compacto (sem indentação), prontos a enviar."""
    prompt = carregar_prompt_sistema()
    conteudo = json.dumps(conteudo_pedido(q, e), ensure_ascii=False, separators=(",", ":"))
    return Pedido(
        versao_prompt=prompt.versao,
        sistema=prompt.texto,
        conteudo=f"Pedido de plano (JSON):\n{conteudo}",
    )


# ---------------------------------------------------------------- Plano


def montar_plano(gerado: PlanoGerado, e: Estrategia, versao_prompt: str, provedor: str) -> Plano:
    """Junta à resposta da LLM os números da Estrategia e os avisos fixos."""
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
    return Plano(
        versao_prompt=versao_prompt,
        provedor=provedor,
        resumo=gerado.resumo,
        marcos=marcos,
        semana_tipo=gerado.semana_tipo,
        treino=gerado.treino,
        alimentacao=gerado.alimentacao,
        proteina=e.indicadores.proteina,
        hidratacao=HidratacaoPlano(valores=e.indicadores.hidratacao, dicas=gerado.hidratacao_dicas),
        habitos=gerado.habitos,
        indicadores_acompanhamento=gerado.indicadores_acompanhamento,
        notas_personalizadas=gerado.notas_personalizadas,
        avisos=e.avisos,
    )


def montar_pedido_correcao(pedido: Pedido, motivos: tuple[str, ...]) -> Pedido:
    """O mesmo pedido, com os motivos da rejeição anterior (prompts/gerador_correcao.md)."""
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
    pedido = montar_pedido(q, e)
    if motivos:
        pedido = montar_pedido_correcao(pedido, motivos)
    gerado = provedor.gerar_json(pedido.sistema, pedido.conteudo, PlanoGerado)
    usado = provedor.ultimo_provedor or provedor.nome
    return montar_plano(gerado, e, pedido.versao_prompt, usado)
