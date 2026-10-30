"""Verificação (papel 4, determinístico): o que o plano tem de cumprir antes de ser mostrado.

Verificações obrigatórias (.claude/rules/regras-e-motor.md e REGRAS_DOMINIO §5 a §8):
avisos fixos presentes; exercícios da biblioteca, de nível base e permitidos para esta
pessoa em cada fase (motor/selecao.py); números iguais aos da Estrategia e dentro dos
limites (ritmo de perda de peso por idade, 0,5 kg de músculo por cada 4 semanas);
texto da LLM sem números com unidades (só o peso dos halteres declarado), sem termos
da lista negra e sem brasileirismos.

Os motivos são técnicos (ids, termos, valores) e nunca citam respostas de saúde: seguem
no pedido de regeneração e aparecem na linha de comando.
"""

import re
from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from vigoria.conteudo.carregar import Impacto, Nivel, carregar_avisos, carregar_exercicios
from vigoria.modelos.estrategia import Estrategia
from vigoria.modelos.plano import Plano
from vigoria.modelos.questionario import Equipamento as EquipamentoDeclarado
from vigoria.modelos.questionario import Questionario
from vigoria.motor.selecao import selecionar_exercicios
from vigoria.motor.voz import (
    detetar_brasileirismos,
    encontrar_termos,
    textos_da_llm,
    textos_obrigatorios,
)
from vigoria.regras.calculos import (
    ganho_muscular_maximo_kg,
    marcos_peso_kg,
    ritmo_maximo_perda_pct,
)
from vigoria.regras.textos import numero

FASES = (1, 2, 3, 4)
SEMANAS_POR_MARCO = 4
TOLERANCIA_KG = 0.1  # arredondamento dos marcos a 0,1 kg
# Valor numérico com unidade de peso, proteína, hidratação ou energia («80 kg», «1,5 litros»).
_NUMERO_COM_UNIDADE = re.compile(
    r"(?<![\w,.])(\d+(?:[.,]\d+)?)\s*"
    r"(kg|quilos?|g|gramas?|ml|mililitros?|l|litros?|kcal|calorias?)(?!\w)",
    re.IGNORECASE,
)


class TipoFalha(StrEnum):
    AVISO_EM_FALTA = "aviso_em_falta"
    EXERCICIO = "exercicio"
    NUMEROS = "numeros"
    NUMERO_NO_TEXTO = "numero_no_texto"
    LISTA_NEGRA = "lista_negra"
    BRASILEIRISMO = "brasileirismo"


class Falha(BaseModel):
    model_config = ConfigDict(frozen=True)

    tipo: TipoFalha
    motivo: str


def verificar(plano: Plano, e: Estrategia, q: Questionario) -> list[Falha]:
    """Todas as verificações obrigatórias; lista vazia se o plano estiver em condições."""
    return [
        *_avisos(plano),
        *_exercicios(plano, e),
        *_numeros(plano, e, q),
        *_texto(plano, q),
    ]


# ---------------------------------------------------------------- Avisos


def _avisos(plano: Plano) -> list[Falha]:
    avisos = carregar_avisos()
    return [
        Falha(tipo=TipoFalha.AVISO_EM_FALTA, motivo=f"Falta o texto obrigatório «{id_}».")
        for id_, texto in zip(avisos.obrigatorios, textos_obrigatorios(), strict=True)
        if texto not in plano.avisos
    ]


# ---------------------------------------------------------------- Exercícios


def _exercicios(plano: Plano, e: Estrategia) -> list[Falha]:
    biblioteca = carregar_exercicios()
    falhas = []
    for fase in FASES:
        permitidos = {p.id for p in selecionar_exercicios(e, fase)}
        for prescrito in getattr(plano.treino, f"fase_{fase}").exercicios:
            id_ = prescrito.exercicio_id
            if id_ in permitidos:
                continue
            ex = biblioteca.get(id_)
            if ex is None:
                razao = "não existe na biblioteca"
            elif ex.nivel is not Nivel.BASE:
                razao = "não é de nível base (no MVP, só nível base)"
            elif e.restricoes.sem_impacto and ex.impacto is not Impacto.BAIXO:
                razao = f"tem impacto {ex.impacto} e o plano é sem impacto"
            else:
                razao = "não está na lista de exercícios permitidos desta fase"
            falhas.append(Falha(tipo=TipoFalha.EXERCICIO, motivo=f"Fase {fase}: «{id_}» {razao}."))
    return falhas


# ---------------------------------------------------------------- Números


def _numeros(plano: Plano, e: Estrategia, q: Questionario) -> list[Falha]:
    ind = e.indicadores
    if ind is None:
        return [Falha(tipo=TipoFalha.NUMEROS, motivo="A estratégia não tem indicadores.")]
    falhas: list[str] = []

    # Iguais aos da Estrategia.
    calculados = [(m.semana, m.fase, m.peso_indicativo_kg, m.cintura) for m in e.marcos]
    no_plano = [(m.semana, m.fase, m.peso_indicativo_kg, m.cintura) for m in plano.marcos]
    if no_plano != calculados:
        falhas.append("Os marcos do plano são diferentes dos calculados pela estratégia.")
    if plano.proteina != ind.proteina:
        falhas.append("A proteína do plano é diferente da calculada.")
    if plano.hidratacao.valores != ind.hidratacao:
        falhas.append("A hidratação do plano é diferente da calculada.")

    # Calculados de novo pelas regras (defesa em profundidade).
    pesos = [m.peso_indicativo_kg for m in plano.marcos]
    if tuple(pesos) != marcos_peso_kg(q.peso_kg, ind.peso_alvo_usado_kg, q.idade):
        falhas.append("Os pesos indicativos não correspondem às regras de perda de peso.")
    maximo_4_semanas = q.peso_kg * ritmo_maximo_perda_pct(q.idade) / 100 * SEMANAS_POR_MARCO
    anterior = q.peso_kg
    for marco, peso in zip(plano.marcos, pesos, strict=True):
        if anterior - peso > maximo_4_semanas + TOLERANCIA_KG:
            falhas.append(
                f"Semana {marco.semana}: perda acima do ritmo máximo para a idade "
                f"({numero(ritmo_maximo_perda_pct(q.idade))} % por semana)."
            )
        anterior = peso
    ganho = ind.ganho_muscular
    if ganho.maximo_kg > ganho_muscular_maximo_kg() or (
        ganho.alvo_semana_16_kg is not None and ganho.alvo_semana_16_kg > ganho_muscular_maximo_kg()
    ):
        falhas.append("Ganho muscular acima de 0,5 kg por cada 4 semanas.")
    return [Falha(tipo=TipoFalha.NUMEROS, motivo=m) for m in falhas]


# ---------------------------------------------------------------- Texto da LLM


def _texto(plano: Plano, q: Questionario) -> list[Falha]:
    tudo = "\n".join(textos_da_llm(plano))
    falhas = []
    halteres = q.halteres_kg if EquipamentoDeclarado.HALTERES in q.equipamento else None
    for valor, unidade in dict.fromkeys(_NUMERO_COM_UNIDADE.findall(tudo)):
        numero = float(valor.replace(",", "."))
        e_halteres = unidade.lower() in ("kg", "quilo", "quilos") and numero == halteres
        if not e_halteres:
            falhas.append(
                Falha(
                    tipo=TipoFalha.NUMERO_NO_TEXTO,
                    motivo=f"O texto tem o valor «{valor} {unidade}»: valores de peso, "
                    "proteína, hidratação e calorias vêm só da estratégia"
                    + (
                        f" (o único peso permitido é o dos halteres, {halteres:g} kg)."
                        if halteres
                        else "."
                    ),
                )
            )
    for termo in encontrar_termos(carregar_avisos().lista_negra.termos, tudo):
        falhas.append(
            Falha(tipo=TipoFalha.LISTA_NEGRA, motivo=f"O texto tem o termo proibido «{termo}».")
        )
    for termo in detetar_brasileirismos(plano):
        falhas.append(
            Falha(
                tipo=TipoFalha.BRASILEIRISMO,
                motivo=f"O texto tem o brasileirismo «{termo}»: use português europeu.",
            )
        )
    return falhas
