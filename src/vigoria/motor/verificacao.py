"""Verificação (papel 4, determinístico): o que o plano tem de cumprir antes de ser mostrado.

Fase 4C (30/10/2026): o treino, a semana-tipo, os hábitos e o acompanhamento são do motor
e dos YAML; as regras de prescrição e de dias são testadas no motor (test_treino.py,
test_semana.py). Aqui ficam dois grupos:
- integridade do que o código monta (avisos obrigatórios, exercícios permitidos e de nível
  base, números iguais aos da Estrategia e dentro das regras). Uma falha aqui é um erro do
  código: o pipeline não regenera (TIPOS_DO_MOTOR);
- segurança do texto da LLM (decisão de 30/10/2026): contagens pedidas, valores de peso,
  proteína, hidratação ou calorias (só o peso dos halteres), outros números com unidade que
  não venham dos dados, lista negra, promessas de resultados ou de segurança e o Tai Chi
  sem a pessoa o praticar (REGRAS §3) e, com «sem intervalos», a alternância de
  ritmos. Uma falha aqui leva a uma regeneração.
A alternância de ritmos no texto do motor (estrutura da sessão, exercícios) é também
verificada, como erro do código.
O estilo (brasileirismos, grafia anterior ao AO90, «garantir») é corrigido em voz.py e
não bloqueia.

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
from vigoria.modelos.questionario import Preferencia, Questionario
from vigoria.motor.selecao import selecionar_exercicios
from vigoria.motor.voz import (
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
    NUMEROS = "numeros"
    CONTAGEM = "contagem"
    NUMERO_NO_TEXTO = "numero_no_texto"
    LISTA_NEGRA = "lista_negra"
    PROMESSA = "promessa"
    TAI_CHI = "tai_chi"
    INTERVALOS = "intervalos"
    INTERVALOS_NO_TREINO = "intervalos_no_treino"


# Falhas do que o código monta: não se corrigem a regenerar o texto da LLM.
_TAI_CHI = re.compile(r"(?<!\w)tai[\s-]?chi(?!\w)", re.IGNORECASE)
TIPOS_DO_MOTOR = frozenset(
    {
        TipoFalha.AVISO_EM_FALTA,
        TipoFalha.EXERCICIO,
        TipoFalha.NUMEROS,
        TipoFalha.INTERVALOS_NO_TREINO,
    }
)
PRIORIDADES_ALIMENTARES = 4  # uma por fase
MAX_NOTAS = 3


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
        *_intervalos_no_treino(plano, e),
        *_contagens(plano),
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
    for treino_fase in plano.treino.fases:
        fase = treino_fase.numero
        permitidos = {p.id for p in selecionar_exercicios(e, fase)}
        cardio = (treino_fase.cardio_finalizador,) if treino_fase.cardio_finalizador else ()
        for x in (*treino_fase.forca, *cardio, *treino_fase.mobilidade_equilibrio):
            id_ = x.id
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


# ---------------------------------------------------------------- Intervalos

_ALTERNANDO_TEMPO = re.compile(
    r"(?<!\w)altern\w*\s+(?:\d+|um|uma|dois|duas|trinta)\s*(?:s|seg|segundos?|min|minutos?)(?!\w)",
    re.IGNORECASE,
)


def mencoes_de_intervalos(texto: str) -> tuple[str, ...]:
    """Menções à alternância de ritmos (avisos.yaml), sem contar as negações."""
    lista_negra = carregar_avisos().lista_negra
    for excecao in lista_negra.intervalos_excecoes:
        texto = re.sub(rf"(?<!\w){re.escape(excecao)}(?!\w)", " ", texto, flags=re.I)
    tempos = tuple(m.group(0) for m in _ALTERNANDO_TEMPO.finditer(texto))
    return tuple(dict.fromkeys((*tempos, *encontrar_termos(lista_negra.intervalos, texto))))


def _intervalos_no_treino(plano: Plano, e: Estrategia) -> list[Falha]:
    """Com «sem intervalos», o texto do treino montado pelo motor não alterna ritmos."""
    if not e.restricoes.sem_intervalos:
        return []
    s = plano.treino.estrutura_sessao
    textos = [
        ("Estrutura da sessão", t)
        for t in (s.aquecimento, s.bloco_principal, s.cardio_finalizador, s.retorno_calma)
    ]
    for f in plano.treino.fases:
        cardio = (f.cardio_finalizador,) if f.cardio_finalizador else ()
        for x in (*f.forca, *cardio, *f.mobilidade_equilibrio):
            textos += [(f"Fase {f.numero}: «{x.id}»", t) for t in (x.descricao, *x.notas)]
    return [
        Falha(
            tipo=TipoFalha.INTERVALOS_NO_TREINO,
            motivo=f"{onde}: o texto do treino tem «{termo}» (alternância de ritmos), mas o "
            "plano é sem intervalos.",
        )
        for onde, texto in textos
        for termo in mencoes_de_intervalos(texto)
    ]


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


def _contagens(plano: Plano) -> list[Falha]:
    falhas = []
    prioridades = len(plano.alimentacao.prioridades_por_fase)
    if prioridades != PRIORIDADES_ALIMENTARES:
        falhas.append(
            f"As prioridades alimentares têm de ser {PRIORIDADES_ALIMENTARES}, uma por fase "
            f"(vieram {prioridades})."
        )
    notas = len(plano.notas_personalizadas)
    if notas > MAX_NOTAS:
        falhas.append(f"No máximo {MAX_NOTAS} notas personalizadas (vieram {notas}).")
    return [Falha(tipo=TipoFalha.CONTAGEM, motivo=m) for m in falhas]


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
                motivo=f"O texto tem a promessa «{termo}»: não prometa resultados nem "
                "segurança; use linguagem prudente.",
            )
        )
    if e.restricoes.sem_intervalos:
        for termo in mencoes_de_intervalos(tudo):
            falhas.append(
                Falha(
                    tipo=TipoFalha.INTERVALOS,
                    motivo=f"O texto tem «{termo}» (alternância de ritmos), mas o plano é "
                    "sem intervalos: use só ritmo contínuo e confortável.",
                )
            )
    if _TAI_CHI.search(tudo) and Preferencia.TAI_CHI not in q.preferencias:
        falhas.append(
            Falha(
                tipo=TipoFalha.TAI_CHI,
                motivo="O texto menciona o Tai Chi, que não está no programa: só pode ser "
                "referido se a pessoa já o praticar (indicado nas preferências).",
            )
        )
    return falhas
