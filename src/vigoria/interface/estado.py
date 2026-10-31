"""Chaves dos widgets do questionário em st.session_state e conversão para as respostas.

Cada pergunta é um widget com a chave «q.<campo>» (e «q.<campo>.<opção>» nas perguntas por
condição, limitação ou refeição). Aqui só se converte entre essas chaves e o dicionário de
respostas de passos.py; não há Streamlit, para se poder testar.
"""

from collections.abc import Mapping
from typing import Any

from vigoria.interface.passos import (
    CAMPOS,
    PASSOS,
    REFEICOES,
    controladas_aplicaveis,
    limitacoes_com_gravidade,
)
from vigoria.modelos.questionario import CONDICOES_COM_CONTROLO, Limitacao

PREFIXO = "q."
OBJETIVO_TIPO = "objetivo_muscular_tipo"  # «aumentar_forca_tonus» ou «kg»
OBJETIVO_KG = "objetivo_muscular_kg"
FORCA_TONUS = "aumentar_forca_tonus"

_POR_OPCAO = {"condicoes_controladas", "limitacoes_gravidade", "refeicoes"}
_LISTAS = {
    "condicoes",
    "dor_articular_zonas",
    "limitacoes",
    "equipamento",
    "preferencias",
    "restricoes_alimentares",
}
_POR_OMISSAO: dict[str, Any] = {
    "acompanhamento_ativo": True,
    "frequencia_registo": "semanal",
    "lembretes_email": True,
}
_SIM_NAO = {True: "sim", False: "nao"}
# Pedidos sem casas decimais (não se exige esse rigor a quem responde); os cálculos continuam
# com decimais. As bebidas espirituosas ficam fora: escolhem-se de uma lista com 0,5 dl.
INTEIROS = {
    "peso_kg",
    "sono_horas",
    "cintura_cm",
    "halteres_kg",
    "peso_alvo_kg",
    "cintura_alvo_cm",
    OBJETIVO_KG,
}
# Caixas que começam em 0 (e não vazias) para as setas +/− funcionarem logo: o Streamlit
# desativa-as com a caixa vazia. Nestes campos 0 não é resposta possível, por isso 0 conta
# como «sem resposta». O vinho e os doces ficam vazios: aí 0 é uma resposta válida e não
# pode ficar dada sem a pessoa a escolher.
ZERO_E_VAZIO = {"idade", "altura_cm"} | INTEIROS


def _inteiro(valor: Any) -> Any:
    """Arredonda a meia unidade para cima (6,5 → 7); deixa como está o que não é número."""
    if isinstance(valor, float | int) and not isinstance(valor, bool):
        return int(valor + 0.5)
    return valor


def _sem_zero(campo: str, valor: Any) -> Any:
    """0 (ou caixa limpa) nos campos de ZERO_E_VAZIO é «sem resposta»."""
    return None if campo in ZERO_E_VAZIO and not valor else valor


def chave(campo: str, opcao: str | None = None) -> str:
    return f"{PREFIXO}{campo}" if opcao is None else f"{PREFIXO}{campo}.{opcao}"


def estado_inicial() -> dict[str, Any]:
    """Valor inicial de cada chave (vazio, salvo os três do passo 6)."""
    estado: dict[str, Any] = {}
    for passo in PASSOS:
        for campo in CAMPOS[passo]:
            if campo in _POR_OPCAO or campo == "objetivo_muscular":
                continue
            vazio: Any = [] if campo in _LISTAS else None
            if campo in {"aceita_termos", "consentimento_saude", "confirma_maior_idade"}:
                vazio = False
            estado[chave(campo)] = _POR_OMISSAO.get(campo, vazio)
    for c in CONDICOES_COM_CONTROLO:
        estado[chave("condicoes_controladas", c)] = None
    for x in Limitacao:
        if x is not Limitacao.NENHUMA:
            estado[chave("limitacoes_gravidade", x)] = None
    for x in REFEICOES:
        estado[chave("refeicoes", x)] = ""
        estado[chave("refeicoes_faz", x)] = False
    estado[chave(OBJETIVO_TIPO)] = None
    for campo in ZERO_E_VAZIO:
        estado[chave(campo)] = 0
    return estado


def para_respostas(estado: Mapping[str, Any]) -> dict[str, Any]:
    """As respostas (formato de passos.py) a partir das chaves dos widgets."""
    respostas: dict[str, Any] = {}
    for chave_estado, valor in estado.items():
        if not isinstance(chave_estado, str) or not chave_estado.startswith(PREFIXO):
            continue
        campo = chave_estado.removeprefix(PREFIXO)
        if "." not in campo and campo not in {OBJETIVO_TIPO, OBJETIVO_KG}:
            respostas[campo] = _sem_zero(campo, valor)
    respostas["condicoes_controladas"] = {
        c: estado[k] == "sim"
        for c in controladas_aplicaveis(respostas)
        if (k := chave("condicoes_controladas", c)) in estado and estado[k] in _SIM_NAO.values()
    }
    respostas["limitacoes_gravidade"] = {
        x: estado[k]
        for x in limitacoes_com_gravidade(respostas)
        if estado.get(k := chave("limitacoes_gravidade", x))
    }
    respostas["refeicoes"] = {x: estado.get(chave("refeicoes", x)) or "" for x in REFEICOES}
    respostas["refeicoes_faz"] = {x: bool(estado.get(chave("refeicoes_faz", x))) for x in REFEICOES}
    tipo = estado.get(chave(OBJETIVO_TIPO))
    if tipo == FORCA_TONUS:
        respostas["objetivo_muscular"] = FORCA_TONUS
    elif tipo == "kg":
        respostas["objetivo_muscular"] = _sem_zero(OBJETIVO_KG, estado.get(chave(OBJETIVO_KG)))
    return respostas


def para_estado(respostas: Mapping[str, Any]) -> dict[str, Any]:
    """O inverso: as chaves dos widgets a partir das respostas (persona de teste em local)."""
    estado = estado_inicial()
    for campo, valor in respostas.items():
        if campo in _POR_OPCAO or campo in {"refeicoes_faz", "objetivo_muscular"}:
            continue
        if chave(campo) in estado:
            estado[chave(campo)] = _inteiro(valor) if campo in INTEIROS else valor
            if campo in ZERO_E_VAZIO and valor is None:
                estado[chave(campo)] = 0
    for c, controlada in (respostas.get("condicoes_controladas") or {}).items():
        estado[chave("condicoes_controladas", c)] = _SIM_NAO[controlada]
    for x, gravidade in (respostas.get("limitacoes_gravidade") or {}).items():
        estado[chave("limitacoes_gravidade", x)] = gravidade
    for x in REFEICOES:
        estado[chave("refeicoes", x)] = (respostas.get("refeicoes") or {}).get(x, "")
        estado[chave("refeicoes_faz", x)] = bool((respostas.get("refeicoes_faz") or {}).get(x))
    objetivo = respostas.get("objetivo_muscular")
    if objetivo == FORCA_TONUS:
        estado[chave(OBJETIVO_TIPO)] = FORCA_TONUS
    elif objetivo is not None:
        estado[chave(OBJETIVO_TIPO)] = "kg"
        estado[chave(OBJETIVO_KG)] = _inteiro(objetivo)
    return estado
