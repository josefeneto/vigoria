"""Verificação (motor/verificacao.py) e voz (motor/voz.py), com respostas simuladas.

Fase 4C: o treino e os números são do motor. As falhas aqui testadas no que o código
monta (exercícios, marcos, avisos) são de TIPOS_DO_MOTOR: o pipeline não regenera.
"""

import json
from pathlib import Path
from typing import Any

import pytest

from vigoria.modelos.estrategia import Estrategia
from vigoria.modelos.plano import Plano, PlanoGerado
from vigoria.modelos.questionario import Questionario
from vigoria.motor.estrategia import gerar_estrategia
from vigoria.motor.gerador import montar_plano
from vigoria.motor.verificacao import TIPOS_DO_MOTOR, TipoFalha, verificar
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
    q, e = _persona()
    gerado = PlanoGerado.model_validate(RESPOSTA if resposta is None else resposta)
    plano = montar_plano(gerado, e, q, "4", "falso")
    return inserir_avisos(plano, e) if voz else plano


def _com_resumo(extra: str) -> dict[str, Any]:
    resposta = json.loads(json.dumps(RESPOSTA))
    resposta["resumo"] += f" {extra}"
    return resposta


def _falhas(plano: Plano) -> list[tuple[TipoFalha, str]]:
    q, e = _persona()
    return [(f.tipo, f.motivo) for f in verificar(plano, e, q)]


def _trocar_exercicio(plano: Plano, fase: int, novo_id: str) -> Plano:
    """Simula um erro do motor: troca o primeiro exercício de força da fase."""
    fases = list(plano.treino.fases)
    forca = list(fases[fase - 1].forca)
    forca[0] = forca[0].model_copy(update={"id": novo_id})
    fases[fase - 1] = fases[fase - 1].model_copy(update={"forca": tuple(forca)})
    return plano.model_copy(
        update={"treino": plano.treino.model_copy(update={"fases": tuple(fases)})}
    )


# ---------------------------------------------------------------- Plano correto


def test_resposta_de_referencia_passa() -> None:
    assert _falhas(_plano()) == []


# ---------------------------------------------------------------- Integridade do motor


def test_chumba_exercicio_inventado() -> None:
    (falha,) = _falhas(_trocar_exercicio(_plano(), 2, "burpee_turbo"))
    assert falha == (TipoFalha.EXERCICIO, "Fase 2: «burpee_turbo» não existe na biblioteca.")
    assert falha[0] in TIPOS_DO_MOTOR


def test_chumba_exercicio_de_impacto() -> None:
    (falha,) = _falhas(_trocar_exercicio(_plano(), 3, "agachamento_salto"))
    assert falha[0] is TipoFalha.EXERCICIO
    assert "Fase 3: «agachamento_salto» não é de nível base" in falha[1]


def test_chumba_exercicio_de_impacto_mesmo_se_fosse_base() -> None:
    from vigoria.conteudo import carregar

    biblioteca = dict(carregar.carregar_exercicios())
    salto = biblioteca["agachamento_salto"].model_copy(update={"nivel": carregar.Nivel.BASE})
    biblioteca["agachamento_salto"] = salto
    q, e = _persona()
    plano = _trocar_exercicio(_plano(), 1, "agachamento_salto")
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("vigoria.motor.verificacao.carregar_exercicios", lambda: biblioteca)
        (falha,) = verificar(plano, e, q)
    assert "tem impacto alto e o plano é sem impacto" in falha.motivo


def test_chumba_marco_de_peso_alterado() -> None:
    plano = _plano()
    marcos = list(plano.marcos)
    marcos[3] = marcos[3].model_copy(update={"peso_indicativo_kg": 80.0})
    falhas = _falhas(plano.model_copy(update={"marcos": tuple(marcos)}))
    assert {t for t, _ in falhas} == {TipoFalha.NUMEROS}
    motivos = " ".join(m for _, m in falhas)
    assert "diferentes dos calculados" in motivos
    assert "Semana 16: perda acima do ritmo máximo para a idade (0,4 % por semana)" in motivos


def test_chumba_proteina_e_hidratacao_alteradas() -> None:
    plano = _plano()
    valores = plano.hidratacao.valores.model_copy(update={"central_ml": 5000})
    plano = plano.model_copy(
        update={
            "proteina": plano.proteina.model_copy(update={"minimo_g": 200}),
            "hidratacao": plano.hidratacao.model_copy(update={"valores": valores}),
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


def test_chumba_avisos_em_falta() -> None:
    falhas = _falhas(_plano(voz=False).model_copy(update={"avisos": ()}))
    assert [m for _, m in falhas] == [
        "Falta o texto obrigatório «aviso_geral».",
        "Falta o texto obrigatório «sinais_interromper».",
    ]


# ---------------------------------------------------------------- Texto da LLM


def test_chumba_peso_alvo_no_texto() -> None:
    falhas = _falhas(_plano(_com_resumo("O seu peso-alvo é 80 kg.")))
    assert falhas == [
        (
            TipoFalha.NUMERO_NO_TEXTO,
            "O texto tem o valor «80 kg»: valores de peso, proteína, hidratação e calorias "
            "vêm só da estratégia (pesos de halteres permitidos: 2 kg).",
        )
    ]
    assert TipoFalha.NUMERO_NO_TEXTO not in TIPOS_DO_MOTOR


def test_chumba_termo_da_lista_negra() -> None:
    falhas = _falhas(_plano(_com_resumo("Ao jantar, um chá detox ajuda.")))
    assert falhas == [(TipoFalha.LISTA_NEGRA, "O texto tem o termo proibido «detox».")]


def test_chumba_brasileirismo() -> None:
    falhas = _falhas(_plano(_com_resumo("Registe tudo no celular.")))
    assert falhas == [
        (TipoFalha.BRASILEIRISMO, "O texto tem o brasileirismo «celular»: use português europeu.")
    ]


def test_motivos_sem_dados_de_saude() -> None:
    plano = _trocar_exercicio(_plano(_com_resumo("Peso-alvo de 80 kg, chá detox.")), 1, "x")
    texto = " ".join(m for _, m in _falhas(plano))
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
