"""Verificação (motor/verificacao.py) e voz (motor/voz.py), com respostas simuladas."""

import json
from pathlib import Path
from typing import Any

import pytest

from vigoria.modelos.estrategia import Estrategia
from vigoria.modelos.plano import Plano, PlanoGerado
from vigoria.modelos.questionario import Questionario
from vigoria.motor.estrategia import gerar_estrategia
from vigoria.motor.gerador import montar_plano
from vigoria.motor.verificacao import TipoFalha, verificar
from vigoria.motor.voz import detetar_brasileirismos, inserir_avisos, textos_obrigatorios
from vigoria.regras import textos

RAIZ = Path(__file__).parent.parent
RESPOSTA = json.loads(
    (RAIZ / "tests" / "fixtures" / "resposta_gerador_persona_teste.json").read_text("utf-8")
)


def _persona() -> tuple[Questionario, Estrategia]:
    dados = json.loads((RAIZ / "exemplos" / "persona_teste.json").read_text(encoding="utf-8"))
    q = Questionario.model_validate(dados)
    return q, gerar_estrategia(q)


def _plano(resposta: dict[str, Any] | None = None, voz: bool = True) -> Plano:
    _, e = _persona()
    gerado = PlanoGerado.model_validate(RESPOSTA if resposta is None else resposta)
    plano = montar_plano(gerado, e, "2", "falso")
    return inserir_avisos(plano, e) if voz else plano


def _alterada() -> dict[str, Any]:
    """Cópia da resposta de referência."""
    return json.loads(json.dumps(RESPOSTA))


def _com_resumo(extra: str) -> dict[str, Any]:
    resposta = _alterada()
    resposta["resumo"] += f" {extra}"
    return resposta


def _falhas(plano: Plano) -> list[tuple[TipoFalha, str]]:
    q, e = _persona()
    return [(f.tipo, f.motivo) for f in verificar(plano, e, q)]


# ---------------------------------------------------------------- Plano correto


def test_resposta_de_referencia_passa() -> None:
    assert _falhas(_plano()) == []


# ---------------------------------------------------------------- Respostas «más»


def test_chumba_exercicio_inventado() -> None:
    resposta = _alterada()
    resposta["treino"]["fase_2"]["exercicios"][0]["exercicio_id"] = "burpee_turbo"
    (falha,) = _falhas(_plano(resposta))
    assert falha == (TipoFalha.EXERCICIO, "Fase 2: «burpee_turbo» não existe na biblioteca.")


def test_chumba_exercicio_de_impacto() -> None:
    resposta = _alterada()
    resposta["treino"]["fase_3"]["exercicios"][0]["exercicio_id"] = "agachamento_salto"
    (falha,) = _falhas(_plano(resposta))
    assert falha[0] is TipoFalha.EXERCICIO
    assert "Fase 3: «agachamento_salto»" in falha[1]
    # É avançado e de impacto alto: o primeiro motivo é o nível (MVP só base).
    assert "não é de nível base" in falha[1]


def test_chumba_exercicio_de_impacto_mesmo_se_fosse_base() -> None:
    from vigoria.conteudo import carregar

    biblioteca = dict(carregar.carregar_exercicios())
    salto = biblioteca["agachamento_salto"].model_copy(update={"nivel": carregar.Nivel.BASE})
    biblioteca["agachamento_salto"] = salto
    resposta = _alterada()
    resposta["treino"]["fase_1"]["exercicios"][0]["exercicio_id"] = "agachamento_salto"
    q, e = _persona()
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("vigoria.motor.verificacao.carregar_exercicios", lambda: biblioteca)
        (falha,) = verificar(_plano(resposta), e, q)
    assert "tem impacto alto e o plano é sem impacto" in falha.motivo


def test_exercicio_valido_noutra_fase_chumba() -> None:
    resposta = _alterada()
    # prancha_inclinada_toque_ombro só é permitida a partir de uma fase posterior.
    resposta["treino"]["fase_1"]["exercicios"][0]["exercicio_id"] = "prancha_inclinada_toque_ombro"
    (falha,) = _falhas(_plano(resposta))
    assert falha == (
        TipoFalha.EXERCICIO,
        "Fase 1: «prancha_inclinada_toque_ombro» não está na lista de exercícios permitidos "
        "desta fase.",
    )


def test_chumba_peso_alvo_no_texto() -> None:
    falhas = _falhas(_plano(_com_resumo("O seu peso-alvo é 80 kg.")))
    assert falhas == [
        (
            TipoFalha.NUMERO_NO_TEXTO,
            "O texto tem o valor «80 kg»: valores de peso, proteína, hidratação e calorias "
            "vêm só da estratégia (o único peso permitido é o dos halteres, 2 kg).",
        )
    ]


def test_chumba_marco_de_peso_alterado() -> None:
    plano = _plano()
    marcos = list(plano.marcos)
    marcos[3] = marcos[3].model_copy(update={"peso_indicativo_kg": 80.0})
    falhas = _falhas(plano.model_copy(update={"marcos": tuple(marcos)}))
    tipos = {t for t, _ in falhas}
    assert tipos == {TipoFalha.NUMEROS}
    motivos = " ".join(m for _, m in falhas)
    assert "diferentes dos calculados" in motivos
    assert (
        "Semana 16: perda acima do ritmo máximo para a idade (0,4 % por semana)" in motivos
    )  # persona com 61+ anos


def test_chumba_proteina_e_hidratacao_alteradas() -> None:
    plano = _plano()
    plano = plano.model_copy(
        update={
            "proteina": plano.proteina.model_copy(update={"minimo_g": 200}),
            "hidratacao": plano.hidratacao.model_copy(
                update={"valores": plano.hidratacao.valores.model_copy(update={"central_ml": 5000})}
            ),
        }
    )
    motivos = [m for _, m in _falhas(plano)]
    assert "A proteína do plano é diferente da calculada." in motivos
    assert "A hidratação do plano é diferente da calculada." in motivos


def test_chumba_ganho_muscular_acima_do_limite() -> None:
    q, e = _persona()
    assert e.indicadores is not None
    ganho = e.indicadores.ganho_muscular.model_copy(update={"maximo_kg": 3.0})
    e = e.model_copy(
        update={"indicadores": e.indicadores.model_copy(update={"ganho_muscular": ganho})}
    )
    falhas = [f.motivo for f in verificar(_plano(), e, q)]
    assert falhas == ["Ganho muscular acima de 0,5 kg por cada 4 semanas."]


def test_chumba_termo_da_lista_negra() -> None:
    falhas = _falhas(_plano(_com_resumo("Ao jantar, um chá detox ajuda.")))
    assert falhas == [(TipoFalha.LISTA_NEGRA, "O texto tem o termo proibido «detox».")]


def test_chumba_brasileirismo() -> None:
    falhas = _falhas(_plano(_com_resumo("Registe tudo no celular.")))
    assert falhas == [
        (TipoFalha.BRASILEIRISMO, "O texto tem o brasileirismo «celular»: use português europeu.")
    ]


def test_chumba_avisos_em_falta() -> None:
    falhas = _falhas(_plano(voz=False).model_copy(update={"avisos": ()}))
    assert [m for _, m in falhas] == [
        "Falta o texto obrigatório «aviso_geral».",
        "Falta o texto obrigatório «sinais_interromper».",
    ]


@pytest.mark.parametrize(
    ("texto", "chumba"),
    [
        ("Use halteres de 2 kg.", False),  # o peso declarado (halteres_kg)
        ("Use halteres de 5 kg.", True),
        ("Beba 1,5 litros de água.", True),
        ("Coma 30 g de proteína ao almoço.", True),
        ("Menos de 1200 kcal por dia.", True),
        ("Beba 500 ml ao acordar.", True),
        ("Caminhe 15 min e descanse 60 s.", False),
        ("3 séries de 12 repetições, 2 vezes por semana.", False),
    ],
)
def test_numeros_com_unidades_no_texto(texto: str, chumba: bool) -> None:
    falhas = _falhas(_plano(_com_resumo(texto)))
    assert bool(falhas) is chumba
    assert all(t is TipoFalha.NUMERO_NO_TEXTO for t, _ in falhas)


def test_motivos_sem_dados_de_saude() -> None:
    resposta = _com_resumo("Peso-alvo de 80 kg, chá detox, no celular.")
    resposta["treino"]["fase_1"]["exercicios"][0]["exercicio_id"] = "inventado"
    texto = " ".join(m for _, m in _falhas(_plano(resposta)))
    for dado in ("hipertensão", "joelho", "94", "persona"):
        assert dado not in texto


# ---------------------------------------------------------------- Voz


def test_avisos_obrigatorios_primeiro_sem_repeticoes() -> None:
    _, e = _persona()
    plano = _plano(voz=False).model_copy(update={"avisos": ()})
    avisos = inserir_avisos(plano, e).avisos
    assert avisos[:2] == textos_obrigatorios() == (textos.AVISO_GERAL, textos.SINAIS_INTERROMPER)
    assert len(avisos) == len(set(avisos))
    assert set(e.avisos) <= set(avisos)


def test_brasileirismos_como_palavra_inteira() -> None:
    assert detetar_brasileirismos(_plano(_com_resumo("Baixar a app no celular."))) == (
        "celular",
        "baixar a app",
    )
    # «baixar a frequência cardíaca» é português europeu correto (REGRAS §8).
    assert detetar_brasileirismos(_plano(_com_resumo("Ajuda a baixar a frequência."))) == ()
    assert detetar_brasileirismos(_plano(_com_resumo("Uma telaria antiga."))) == ()
