"""Verificação (papel 4, determinístico): o que o plano tem de cumprir antes de ser mostrado.

Verificações obrigatórias (.claude/rules/regras-e-motor.md e REGRAS_DOMINIO §5 a §8):
avisos fixos presentes; exercícios da biblioteca, de nível base e permitidos para esta
pessoa em cada fase (motor/selecao.py); números iguais aos da Estrategia e dentro dos
limites (ritmo de perda de peso por idade, 0,5 kg de músculo por cada 4 semanas);
semana-tipo dentro de dias_semana e minutos_dia; séries, repetições e descanso iguais
aos do programa (fases.yaml); texto da LLM sem valores de peso, proteína, hidratação ou
calorias (só o peso dos halteres: o menor entre o do programa e o declarado), sem outros
números com unidade que não venham dos dados, sem termos da lista negra, sem promessas
absolutas e sem brasileirismos.

Os motivos são técnicos (ids, termos, valores) e nunca citam respostas de saúde: seguem
no pedido de regeneração e aparecem na linha de comando.
"""

import re
from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from vigoria.conteudo.carregar import (
    Impacto,
    Nivel,
    carregar_alimentacao,
    carregar_avisos,
    carregar_exercicios,
    carregar_programa,
)
from vigoria.modelos.estrategia import Estrategia
from vigoria.modelos.plano import Plano
from vigoria.modelos.questionario import Equipamento as EquipamentoDeclarado
from vigoria.modelos.questionario import Questionario
from vigoria.motor.gerador import fases_para_pedido
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


# Outros números com unidade (copos, tempo, distância, percentagem): só se vierem dos dados.
_NUMEROS_POR_EXTENSO = {
    "um": 1, "uma": 1, "dois": 2, "duas": 2, "três": 3, "quatro": 4, "cinco": 5, "seis": 6,
    "sete": 7, "oito": 8, "nove": 9, "dez": 10, "onze": 11, "doze": 12, "treze": 13,
    "catorze": 14, "quinze": 15, "dezasseis": 16, "dezassete": 17, "dezoito": 18,
    "dezanove": 19, "vinte": 20, "trinta": 30, "quarenta": 40, "cinquenta": 50,
    "sessenta": 60, "meia": 0.5, "meio": 0.5,
}  # fmt: skip
# Unidade normalizada: o tempo fica sempre em minutos.
_UNIDADES = {
    "copo": "copos", "copos": "copos",
    "h": "min", "hora": "min", "horas": "min",
    "min": "min", "mins": "min", "minuto": "min", "minutos": "min",
    "km": "km", "quilómetro": "km", "quilómetros": "km",
    "%": "%", "por cento": "%",
}  # fmt: skip
_POR_MINUTOS = {"h": 60, "hora": 60, "horas": 60}
_NUM = r"\d+(?:[.,]\d+)?|" + "|".join(sorted(_NUMEROS_POR_EXTENSO, key=len, reverse=True))
_NUMERO_COM_OUTRA_UNIDADE = re.compile(
    rf"(?<![\w,.])({_NUM})(?:\s*(?:a|-|–|ou)\s*({_NUM}))?\s*"
    r"(por cento|quilómetros|quilómetro|minutos|minuto|horas|hora|copos|copo|mins|min|km|h|%)"
    r"(?!\w)",
    re.IGNORECASE,
)


class TipoFalha(StrEnum):
    AVISO_EM_FALTA = "aviso_em_falta"
    EXERCICIO = "exercicio"
    PRESCRICAO = "prescricao"
    SEMANA = "semana"
    NUMEROS = "numeros"
    NUMERO_NO_TEXTO = "numero_no_texto"
    LISTA_NEGRA = "lista_negra"
    PROMESSA = "promessa"
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
        *_prescricao(plano, e),
        *_semana(plano, q),
        *_numeros(plano, e, q),
        *_texto(plano, e, q),
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


def _prescricao(plano: Plano, e: Estrategia) -> list[Falha]:
    """Exercícios de referência: séries, repetições e descanso iguais aos de fases.yaml."""
    permitidos = {fase: selecionar_exercicios(e, fase) for fase in FASES}
    falhas = []
    for fase in fases_para_pedido(permitidos):
        referencia: dict[str, list[tuple[int, str, str]]] = {}
        for item in fase["exercicios_referencia"]:
            valores = (item["series"], item["repeticoes"], item["descanso_s"])
            for id_ in (item["id"], *item.get("alternativas", [])):
                referencia.setdefault(id_, []).append(valores)
        numero_fase = fase["numero"]
        for x in getattr(plano.treino, f"fase_{numero_fase}").exercicios:
            certos = referencia.get(x.exercicio_id)
            if not certos or any(
                x.series == series
                and _normalizar(x.repeticoes) == _normalizar(repeticoes)
                and _algarismos(x.descanso) == _algarismos(descanso)
                for series, repeticoes, descanso in certos
            ):
                continue
            series, repeticoes, descanso = certos[0]
            falhas.append(
                Falha(
                    tipo=TipoFalha.PRESCRICAO,
                    motivo=f"Fase {numero_fase}: «{x.exercicio_id}» tem de seguir o programa: "
                    f"{series} séries de {repeticoes}, descanso de {descanso} s.",
                )
            )
    return falhas


def _normalizar(texto: str) -> str:
    return re.sub(r"\s+", "", texto).lower()


def _algarismos(texto: str) -> list[int]:
    return [int(n) for n in re.findall(r"\d+", texto)]


# ---------------------------------------------------------------- Semana-tipo


def _semana(plano: Plano, q: Questionario) -> list[Falha]:
    """Dias com sessão (duração > 0) até dias_semana; cada sessão até minutos_dia."""
    dias = carregar_avisos().rotulos.dias
    ativos = [s for s in plano.semana_tipo if s.duracao_min > 0]
    falhas = []
    if len(ativos) > q.dias_semana:
        falhas.append(
            f"A semana-tipo tem {len(ativos)} dias com sessão, mas a disponibilidade é de "
            f"{q.dias_semana} dias (os outros dias ficam com duração 0)."
        )
    falhas += [
        f"{dias[s.dia]}: sessão de {s.duracao_min} min, acima dos {q.minutos_dia} min disponíveis."
        for s in ativos
        if s.duracao_min > q.minutos_dia
    ]
    return [Falha(tipo=TipoFalha.SEMANA, motivo=m) for m in falhas]


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


def pesos_halteres_permitidos(q: Questionario) -> frozenset[float]:
    """Cargas do programa (biblioteca e fases.yaml), cada uma limitada ao peso declarado."""
    if EquipamentoDeclarado.HALTERES not in q.equipamento or not q.halteres_kg:
        return frozenset()
    return frozenset(min(v, float(q.halteres_kg)) for v in _kg_do_programa())


def _kg_do_programa() -> frozenset[float]:
    textos = [x.variante_halteres or "" for x in carregar_exercicios().values()]
    textos += [p.com_halteres for f in carregar_programa().fases for p in f.exercicios]
    return frozenset(
        float(v.replace(",", "."))
        for texto in textos
        for v, u in _NUMERO_COM_UNIDADE.findall(texto)
        if u.lower() == "kg"
    )


def _valor(texto: str) -> float:
    texto = texto.lower()
    if texto in _NUMEROS_POR_EXTENSO:
        return float(_NUMEROS_POR_EXTENSO[texto])
    return float(texto.replace(",", "."))


def _numeros_com_unidade(texto: str) -> list[tuple[str, str, list[float]]]:
    """(trecho, unidade normalizada, valores nessa unidade) de cada ocorrência."""
    resultado = []
    for m in _NUMERO_COM_OUTRA_UNIDADE.finditer(texto):
        primeiro, segundo, unidade = m.groups()
        fator = _POR_MINUTOS.get(unidade.lower(), 1)
        valores = [_valor(v) * fator for v in (primeiro, segundo) if v]
        resultado.append((m.group(0), _UNIDADES[unidade.lower()], valores))
    return resultado


def valores_dos_dados(e: Estrategia, q: Questionario) -> dict[str, list[tuple[float, float]]]:
    """Intervalos (mínimo, máximo) aceites por unidade: YAML, Estrategia e questionário."""
    intervalos: dict[str, list[tuple[float, float]]] = {}
    for texto in (*_textos_dos_yaml(), *_textos(e.model_dump(mode="json"))):
        for _, unidade, valores in _numeros_com_unidade(texto):
            intervalos.setdefault(unidade, []).append((min(valores), max(valores)))
    do_questionario = {
        "min": [q.minutos_dia, q.sono_horas * 60 if q.sono_horas else None],
        "copos": [q.vinho_copos_dia],
    }
    for unidade, valores in do_questionario.items():
        for v in valores:
            if v is not None:
                intervalos.setdefault(unidade, []).append((float(v), float(v)))
    return intervalos


def _textos_dos_yaml() -> list[str]:
    return _textos(
        [
            [x.model_dump(mode="json") for x in carregar_exercicios().values()],
            carregar_programa().model_dump(mode="json"),
            carregar_alimentacao().model_dump(mode="json"),
            carregar_avisos().textos,
        ]
    )


def _textos(valor: object) -> list[str]:
    if isinstance(valor, str):
        return [valor]
    if isinstance(valor, dict):
        return [t for v in valor.values() for t in _textos(v)]
    if isinstance(valor, list | tuple):
        return [t for v in valor for t in _textos(v)]
    return []


def _texto(plano: Plano, e: Estrategia, q: Questionario) -> list[Falha]:
    tudo = "\n".join(textos_da_llm(plano))
    falhas = []
    halteres = pesos_halteres_permitidos(q)
    lista_halteres = ", ".join(f"{h:g} kg" for h in sorted(halteres))
    for valor, unidade in dict.fromkeys(_NUMERO_COM_UNIDADE.findall(tudo)):
        e_halteres = (
            unidade.lower() in ("kg", "quilo", "quilos")
            and float(valor.replace(",", ".")) in halteres
        )
        if not e_halteres:
            permitido = f" (pesos de halteres permitidos: {lista_halteres})." if halteres else "."
            falhas.append(
                Falha(
                    tipo=TipoFalha.NUMERO_NO_TEXTO,
                    motivo=f"O texto tem o valor «{valor} {unidade}»: valores de peso, "
                    f"proteína, hidratação e calorias vêm só da estratégia{permitido}",
                )
            )
    aceites = valores_dos_dados(e, q)
    vistos: set[str] = set()
    for trecho, unidade, valores in _numeros_com_unidade(tudo):
        dentro = all(
            any(lo - 1e-9 <= v <= hi + 1e-9 for lo, hi in aceites.get(unidade, [])) for v in valores
        )
        if not dentro and trecho.lower() not in vistos:
            vistos.add(trecho.lower())
            falhas.append(
                Falha(
                    tipo=TipoFalha.NUMERO_NO_TEXTO,
                    motivo=f"O texto tem «{trecho}», um valor que não vem do questionário, da "
                    "estratégia nem do programa: use só os valores do pedido ou escreva sem "
                    "números.",
                )
            )
    lista_negra = carregar_avisos().lista_negra
    for termo in encontrar_termos(lista_negra.termos, tudo):
        falhas.append(
            Falha(tipo=TipoFalha.LISTA_NEGRA, motivo=f"O texto tem o termo proibido «{termo}».")
        )
    for termo in encontrar_termos(lista_negra.promessas, tudo):
        falhas.append(
            Falha(
                tipo=TipoFalha.PROMESSA,
                motivo=f"O texto tem a promessa absoluta «{termo}»: não prometa resultados nem "
                "segurança total; use linguagem prudente.",
            )
        )
    for termo in detetar_brasileirismos(plano):
        falhas.append(
            Falha(
                tipo=TipoFalha.BRASILEIRISMO,
                motivo=f"O texto tem o brasileirismo «{termo}»: use português europeu.",
            )
        )
    return falhas
