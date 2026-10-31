"""Passos do questionário (docs/dominio/QUESTIONARIO.md) e validação de cada um.

As respostas vivem num dicionário com as chaves do Questionario (valores como no JSON:
enumerações pelo valor) e uma chave só da interface, `refeicoes_faz` ({refeição: bool}).
Os limites vêm dos próprios campos do Questionario: aqui só se acrescentam as regras de
quando um campo condicional se aplica. As mensagens ficam em paginas/textos.py.
"""

from collections.abc import Callable, Mapping
from enum import StrEnum
from functools import cache
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, TypeAdapter, ValidationError

from vigoria.modelos.questionario import (
    CONDICOES_COM_CONTROLO,
    REFEICAO_SEM_DESCRICAO,
    Articulacao,
    Condicao,
    Equipamento,
    Limitacao,
    Questionario,
    Refeicoes,
    RestricaoAlimentar,
)

PASSOS: tuple[str, ...] = ("0", "1", "2a", "2b", "3", "4a", "4b", "5", "6", "7")

CAMPOS: dict[str, tuple[str, ...]] = {
    "0": ("aceita_termos", "consentimento_saude", "confirma_maior_idade"),
    "1": (
        "sexo",
        "idade",
        "altura_cm",
        "peso_kg",
        "sono_horas",
        "cintura_cm",
        "atividade_atual",
    ),
    "2a": (
        "condicoes",
        "condicoes_controladas",
        "osteoporose_risco",
        "dor_articular_zonas",
        "dor_articular_outra",
        "condicoes_outras",
        "medicacao_afeta_fc",
        "medicacao_notas",
    ),
    "2b": ("limitacoes", "limitacoes_gravidade", "limitacoes_outra"),
    "3": ("equipamento", "halteres_kg", "dias_semana", "minutos_dia", "preferencias"),
    "4a": ("refeicoes", "restricoes_alimentares", "restricoes_outra"),
    "4b": (
        "agua_litros",
        "bebidas_acucaradas_litros",
        "vinho_copos_dia",
        "espirituosas_dl_dia",
        "pao_por_dia",
        "doces_por_semana",
    ),
    "5": ("peso_alvo_kg", "cintura_alvo_cm", "objetivo_muscular", "intensidade_pedida"),
    "6": ("acompanhamento_ativo", "frequencia_registo", "lembretes_email"),
    "7": (),
}

REFEICOES: tuple[str, ...] = tuple(Refeicoes.model_fields)

# Escolhas que não se podem combinar com outras.
_NENHUMA = {
    "condicoes": Condicao.NENHUMA.value,
    "limitacoes": Limitacao.NENHUMA.value,
    "equipamento": Equipamento.NENHUM.value,
}


def _tem(respostas: Mapping[str, Any], campo: str, valor: str) -> bool:
    return valor in (respostas.get(campo) or [])


# Campos condicionais: só se aplicam (e então são obrigatórios) se a opção foi escolhida.
# A ordem conta: a outra articulação depende das zonas, que dependem da dor articular.
CONDICIONAIS: dict[str, Callable[[Mapping[str, Any]], bool]] = {
    "osteoporose_risco": lambda r: _tem(r, "condicoes", Condicao.OSTEOPOROSE),
    "dor_articular_zonas": lambda r: _tem(r, "condicoes", Condicao.DOR_ARTICULAR_PERSISTENTE),
    "dor_articular_outra": lambda r: _tem(r, "dor_articular_zonas", Articulacao.OUTRA),
    "condicoes_outras": lambda r: _tem(r, "condicoes", Condicao.OUTRA),
    "limitacoes_outra": lambda r: _tem(r, "limitacoes", Limitacao.OUTRA),
    "halteres_kg": lambda r: _tem(r, "equipamento", Equipamento.HALTERES),
    "restricoes_outra": lambda r: _tem(r, "restricoes_alimentares", RestricaoAlimentar.OUTRA),
}


class CodigoErro(StrEnum):
    OBRIGATORIO = "obrigatorio"
    INTERVALO = "intervalo"  # fora de [minimo, maximo]
    MULTIPLO = "multiplo"  # sono: de meia em meia hora
    DEMASIADO_LONGO = "demasiado_longo"  # texto acima de `maximo` caracteres
    NENHUMA_EXCLUSIVA = "nenhuma_exclusiva"  # «nenhuma» com outras escolhas
    INVALIDO = "invalido"


class ErroCampo(BaseModel):
    """Um erro num campo. Em dicionários, `campo` indica a chave: «limitacoes_gravidade.joelhos»."""

    model_config = ConfigDict(frozen=True)

    campo: str
    codigo: CodigoErro
    minimo: float | None = None
    maximo: float | None = None


def controladas_aplicaveis(respostas: Mapping[str, Any]) -> list[str]:
    """Condições escolhidas para as quais se pergunta se estão controladas."""
    return [c for c in respostas.get("condicoes") or [] if c in CONDICOES_COM_CONTROLO]


def limitacoes_com_gravidade(respostas: Mapping[str, Any]) -> list[str]:
    return [x for x in respostas.get("limitacoes") or [] if x != Limitacao.NENHUMA]


def tem_gravidez(respostas: Mapping[str, Any]) -> bool:
    return _tem(respostas, "condicoes", Condicao.GRAVIDEZ)


def _vazio(valor: Any) -> bool:
    return valor is None or valor == "" or valor == [] or valor == {}


def limpar_condicionais(respostas: Mapping[str, Any]) -> dict[str, Any]:
    """Cópia sem as respostas que deixaram de se aplicar (senão o Questionario recusa-as)."""
    limpas = dict(respostas)
    for campo, aplica in CONDICIONAIS.items():
        if campo in limpas and not aplica(limpas):
            del limpas[campo]
    if "condicoes_controladas" in limpas:
        escolhidas = controladas_aplicaveis(limpas)
        limpas["condicoes_controladas"] = {
            c: v for c, v in limpas["condicoes_controladas"].items() if c in escolhidas
        }
    if "limitacoes_gravidade" in limpas:
        escolhidas = limitacoes_com_gravidade(limpas)
        limpas["limitacoes_gravidade"] = {
            x: v for x, v in limpas["limitacoes_gravidade"].items() if x in escolhidas
        }
    return limpas


@cache
def _adaptador(campo: str) -> TypeAdapter[Any]:
    info = Questionario.model_fields[campo]
    return TypeAdapter(Annotated[info.annotation, info])


def _limites(campo: str, contexto: Mapping[str, Any]) -> tuple[float | None, float | None]:
    """Mínimo e máximo declarados no campo (ge/gt, le/lt, max_length) ou, num campo com
    várias formas (objetivo_muscular), os do erro."""
    limites: dict[str, Any] = dict(contexto)
    for m in Questionario.model_fields[campo].metadata:
        for nome in ("ge", "gt", "le", "lt", "max_length"):
            if getattr(m, nome, None) is not None:
                limites[nome] = getattr(m, nome)

    def primeiro(*nomes: str) -> float | None:
        return next((limites[n] for n in nomes if limites.get(n) is not None), None)

    return primeiro("ge", "gt"), primeiro("le", "lt", "max_length")


def _erro_de_validacao(campo: str, erro: ValidationError) -> ErroCampo:
    # Numa união (texto fixo ou número), o erro útil é o do número, não o da opção fixa.
    detalhes = [d for d in erro.errors() if d["type"] != "literal_error"] or erro.errors()
    tipo = detalhes[0]["type"]
    minimo, maximo = _limites(campo, detalhes[0].get("ctx") or {})
    if tipo in {"greater_than", "greater_than_equal", "less_than", "less_than_equal"}:
        return ErroCampo(campo=campo, codigo=CodigoErro.INTERVALO, minimo=minimo, maximo=maximo)
    if tipo == "multiple_of":
        return ErroCampo(campo=campo, codigo=CodigoErro.MULTIPLO)
    if tipo == "string_too_long":
        return ErroCampo(campo=campo, codigo=CodigoErro.DEMASIADO_LONGO, maximo=maximo)
    return ErroCampo(campo=campo, codigo=CodigoErro.INVALIDO)


def _validar_campo(campo: str, valor: Any) -> ErroCampo | None:
    if campo in {"condicoes_controladas", "limitacoes_gravidade"}:
        return None  # validados chave a chave em validar_passo
    try:
        _adaptador(campo).validate_python(valor)
    except ValidationError as erro:
        return _erro_de_validacao(campo, erro)
    return None


def validar_passo(passo: str, respostas: Mapping[str, Any]) -> list[ErroCampo]:
    """Erros das respostas de um passo; lista vazia = pode avançar."""
    r = limpar_condicionais(respostas)
    erros: list[ErroCampo] = []
    for campo in CAMPOS[passo]:
        info = Questionario.model_fields[campo]
        valor = r.get(campo)
        if campo in CONDICIONAIS and not CONDICIONAIS[campo](r):
            continue
        obrigatorio = info.is_required() or campo in CONDICIONAIS
        if campo == "refeicoes":
            erros += _erros_refeicoes(r)
        elif campo in {"aceita_termos", "consentimento_saude", "confirma_maior_idade"}:
            if valor is not True:
                erros.append(ErroCampo(campo=campo, codigo=CodigoErro.OBRIGATORIO))
        elif _vazio(valor):
            if obrigatorio:
                erros.append(ErroCampo(campo=campo, codigo=CodigoErro.OBRIGATORIO))
        elif campo in _NENHUMA and _NENHUMA[campo] in valor and len(valor) > 1:
            erros.append(ErroCampo(campo=campo, codigo=CodigoErro.NENHUMA_EXCLUSIVA))
        elif (erro := _validar_campo(campo, valor)) is not None:
            erros.append(erro)

    if passo == "2a":
        controladas = r.get("condicoes_controladas") or {}
        erros += [
            ErroCampo(campo=f"condicoes_controladas.{c}", codigo=CodigoErro.OBRIGATORIO)
            for c in controladas_aplicaveis(r)
            if not isinstance(controladas.get(c), bool)
        ]
    if passo == "2b":
        gravidade = r.get("limitacoes_gravidade") or {}
        erros += [
            ErroCampo(campo=f"limitacoes_gravidade.{x}", codigo=CodigoErro.OBRIGATORIO)
            for x in limitacoes_com_gravidade(r)
            if not gravidade.get(x)
        ]
    return erros


def _erros_refeicoes(r: Mapping[str, Any]) -> list[ErroCampo]:
    escritos = r.get("refeicoes") or {}
    maximo = Refeicoes.model_fields["pequeno_almoco"].metadata[0].max_length
    return [
        ErroCampo(campo=f"refeicoes.{x}", codigo=CodigoErro.DEMASIADO_LONGO, maximo=maximo)
        for x in REFEICOES
        if len(escritos.get(x, "").strip()) > maximo
    ]


def textos_refeicoes(respostas: Mapping[str, Any]) -> dict[str, str]:
    """Texto de cada refeição para o Questionario: vazio = não faz; feita sem descrição =
    REFEICAO_SEM_DESCRICAO (decisão de 31/10/2026)."""
    faz = respostas.get("refeicoes_faz") or {}
    escritos = respostas.get("refeicoes") or {}
    resultado = {}
    for x in REFEICOES:
        texto = (escritos.get(x) or "").strip()
        resultado[x] = (texto or REFEICAO_SEM_DESCRICAO) if faz.get(x) else ""
    return resultado


def montar_questionario(respostas: Mapping[str, Any]) -> Questionario:
    """O Questionario completo a partir das respostas (levanta ValidationError se faltar algo)."""
    r = limpar_condicionais(respostas)
    dados = {c: r[c] for c in Questionario.model_fields if c in r and not _vazio(r[c])}
    for campo in ("condicoes_controladas", "limitacoes_gravidade"):
        dados[campo] = r.get(campo) or {}
    dados["refeicoes"] = textos_refeicoes(r)
    return Questionario.model_validate(dados)


def respostas_de_questionario(q: Questionario) -> dict[str, Any]:
    """O inverso de montar_questionario (preencher com a persona de teste em local)."""
    dados = q.model_dump(mode="json")
    refeicoes = dados["refeicoes"]
    dados["refeicoes_faz"] = {x: bool(refeicoes[x]) for x in REFEICOES}
    dados["refeicoes"] = {
        x: "" if refeicoes[x] == REFEICAO_SEM_DESCRICAO else refeicoes[x] for x in REFEICOES
    }
    return dados
