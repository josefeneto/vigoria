"""Verificações do texto da LLM acrescentadas a 30/10/2026 (revisão dos planos reais).

Números com unidade só dos dados (também por extenso), cargas dos halteres, promessas
absolutas, «aeróbico», contagens do novo PlanoGerado (Fase 4C) e ortografia (só aviso).
Revisão do prompt v5: alternância de ritmos com «sem intervalos», promessas no futuro,
«protege» (só aviso) e Tai Chi na ortografia.
A semana-tipo e a prescrição passaram a ser do motor: test_semana.py e test_treino.py.
"""

import json
from pathlib import Path
from typing import Any

import pytest

from vigoria.modelos.plano import Plano, PlanoGerado
from vigoria.modelos.questionario import Questionario
from vigoria.motor import ortografia
from vigoria.motor.estrategia import gerar_estrategia
from vigoria.motor.gerador import montar_plano
from vigoria.motor.ortografia import (
    corrigir_acentuacao,
    forma_acentuada,
    palavras_desconhecidas,
)
from vigoria.motor.verificacao import (
    TIPOS_DO_MOTOR,
    TipoFalha,
    mencoes_de_intervalos,
    pesos_halteres_permitidos,
    verificar,
)
from vigoria.motor.voz import inserir_avisos, rever_estilo

RAIZ = Path(__file__).parent.parent
RESPOSTA = json.loads(
    (RAIZ / "tests" / "fixtures" / "resposta_gerador_persona_teste.json").read_text("utf-8")
)


def _q(ficheiro: str = "persona_teste.json", **alteracoes: Any) -> Questionario:
    dados = json.loads((RAIZ / "exemplos" / ficheiro).read_text(encoding="utf-8"))
    return Questionario.model_validate(dados | alteracoes)


def _resposta() -> dict[str, Any]:
    return json.loads(json.dumps(RESPOSTA))


def _plano(resposta: dict[str, Any], q: Questionario | None = None) -> Plano:
    q = _q() if q is None else q
    e = gerar_estrategia(q)
    gerado = PlanoGerado.model_validate(resposta)
    return inserir_avisos(montar_plano(gerado, e, q, "4", "falso"), e)


def _falhas(resposta: dict[str, Any], q: Questionario | None = None) -> list[tuple[str, str]]:
    q = _q() if q is None else q
    e = gerar_estrategia(q)
    return [(f.tipo.value, f.motivo) for f in verificar(_plano(resposta, q), e, q)]


def _com_texto(extra: str) -> dict[str, Any]:
    resposta = _resposta()
    resposta["resumo"] += f" {extra}"
    return resposta


def test_referencia_passa() -> None:
    assert _falhas(_resposta()) == []


# ---------------------------------------------------------------- Contagens


def test_quatro_prioridades_alimentares() -> None:
    resposta = _resposta()
    resposta["prioridades_alimentares"] = resposta["prioridades_alimentares"][:3]
    assert _falhas(resposta) == [
        ("contagem", "As prioridades alimentares têm de ser 4, uma por fase (vieram 3).")
    ]


def test_no_maximo_tres_notas() -> None:
    resposta = _resposta()
    resposta["notas_personalizadas"].append("Mais uma nota.")
    assert _falhas(resposta) == [("contagem", "No máximo 3 notas personalizadas (vieram 4).")]


# ---------------------------------------------------------------- Números com unidade


@pytest.mark.parametrize(
    "texto",
    [
        "Limitando a dois copos por dia.",
        "Beba um copo de água ao acordar.",
        "Durma 7 horas.",
        "Caminhe 20 min.",
        "Ande 3 km.",
        "Reduza 10 % do pão.",
        "Faça 20 a 25 minutos.",
    ],
)
def test_numeros_que_nao_vem_dos_dados_chumbam(texto: str) -> None:
    falhas = _falhas(_com_texto(texto))
    assert len(falhas) == 1
    tipo, motivo = falhas[0]
    assert tipo == "numero_no_texto"
    assert "não vem do questionário, da estratégia nem do programa" in motivo


@pytest.mark.parametrize(
    "texto",
    [
        "Hoje bebe 3 copos de vinho.",  # vinho_copos_dia do questionário
        "Sessões de 30 minutos.",  # minutos_dia
        "Meia hora por dia.",  # 30 min
        "Cardio finalizador de 12 min.",  # fases.yaml: 10 a 15 min
        "Aquecimento de 5 a 10 min.",  # estrutura da sessão
    ],
)
def test_numeros_dos_dados_passam(texto: str) -> None:
    assert _falhas(_com_texto(texto)) == []


# ---------------------------------------------------------------- Cargas


def test_halteres_o_menor_entre_programa_e_declarado() -> None:
    assert pesos_halteres_permitidos(_q()) == {2.0}  # programa 2 e 5 kg; declarado 2 kg
    assert pesos_halteres_permitidos(_q(halteres_kg=5)) == {2.0, 5.0}
    assert pesos_halteres_permitidos(_q(halteres_kg=10)) == {2.0, 5.0}
    sem_halteres = _q(equipamento=["cadeira_firme"], halteres_kg=None)
    assert pesos_halteres_permitidos(sem_halteres) == frozenset()


def test_remada_com_5_kg_chumba_com_halteres_de_2_kg() -> None:
    falhas = _falhas(_com_texto("Remada com halteres de 5 kg."))
    assert falhas == [
        (
            "numero_no_texto",
            "O texto tem o valor «5 kg»: valores de peso, proteína, hidratação e calorias vêm "
            "só da estratégia (pesos de halteres permitidos: 2 kg).",
        )
    ]
    assert _falhas(_com_texto("Remada com halteres de 5 kg."), _q(halteres_kg=5)) == []


# ---------------------------------------------------------------- Promessas e brasileirismos


@pytest.mark.parametrize(
    ("texto", "termo"),
    [
        ("Garantimos resultados.", "garantimos"),
        ("Tem resultados garantidos.", "resultados garantidos"),
        ("Vai perder peso depressa.", "vai perder"),
        ("Exercícios sem risco.", "sem risco"),
        ("É risco zero.", "risco zero"),
        ("Sucesso a 100 %.", "100 %"),
        ("É totalmente seguro.", "totalmente seguro"),
        ("Alcançará o seu objetivo.", "alcançará"),
        ("Vai conseguir subir escadas.", "vai conseguir"),
        ("Irá perder cintura.", "irá perder"),
        ("Vai notar mais energia.", "vai notar"),
        ("Verá resultados cedo.", "verá resultados"),
        ("São exercícios seguros.", "exercícios seguros"),
        ("Conseguirá fazer o circuito.", "conseguirá"),
        ("Notará a diferença.", "notará"),
    ],
)
def test_promessas_de_resultados_ou_seguranca_bloqueiam(texto: str, termo: str) -> None:
    falhas = _falhas(_com_texto(texto))
    promessas = [m for t, m in falhas if t == TipoFalha.PROMESSA.value]
    assert any(f"«{termo}»" in m for m in promessas), falhas


def test_palavras_parecidas_nao_sao_promessas() -> None:
    assert _falhas(_com_texto("A totalidade do treino é feita em casa.")) == []
    # Os marcos de força no presente (prompt v6) não são promessas.
    assert _falhas(_com_texto("Consegue fazer o circuito completo sem dor.")) == []


@pytest.mark.parametrize(
    "texto",
    [
        "Vai garantir a regularidade.",
        "Recuperação total ao domingo.",
        "Executa perfeitamente.",
        "Um plano rigoroso.",
        "Exercício aeróbico ligeiro.",
        "A acção conta.",
    ],
)
def test_estilo_nao_bloqueia(texto: str) -> None:
    assert _falhas(_com_texto(texto)) == []


@pytest.mark.parametrize(
    ("texto", "corrigido"),
    [
        ("Vai garantir a regularidade.", "Vai assegurar a regularidade."),
        ("Garanta a técnica.", "Assegure a técnica."),
        ("Isto garante energia.", "Isto assegura energia."),
        ("Garantindo o descanso.", "Assegurando o descanso."),
        ("Veja na tela do celular.", "Veja no ecrã do telemóvel."),
        ("Vá à academia com o time.", "Vá ao ginásio com a equipa."),
        ("Exercício aeróbico.", "Exercício aeróbio."),
        ("A percepção da acção é óptima.", "A perceção da ação é ótima."),
        ("O objectivo actual.", "O objetivo atual."),
    ],
)
def test_estilo_corrigido_pelo_motor(texto: str, corrigido: str) -> None:
    revisao = rever_estilo(_plano(_com_texto(texto)))
    assert revisao.plano.resumo.endswith(corrigido)
    assert revisao.correcoes


def test_estilo_corrige_todos_os_campos_da_llm() -> None:
    resposta = _resposta()
    resposta["marcos_forca"]["semana_4"] = "Garantir a técnica."
    resposta["ajustes_refeicoes"][0]["sugestao"] = "Ao café da manhã, fruta."
    resposta["bebidas_e_alcool"] = "Água como bebida, sem registro."
    resposta["prioridades_alimentares"][0] = "Fase 1: a acção."
    resposta["notas_personalizadas"][0] = "Use o celular."
    plano = rever_estilo(_plano(resposta)).plano
    assert plano.marcos[0].forca_resistencia == "Assegurar a técnica."
    assert plano.alimentacao.ajustes_refeicoes[0].sugestao == "Ao pequeno-almoço, fruta."
    assert plano.alimentacao.bebidas_e_alcool == "Água como bebida, sem registo."
    assert plano.alimentacao.prioridades_por_fase[0] == "Fase 1: a ação."
    assert plano.notas_personalizadas[0] == "Use o telemóvel."


def test_estilo_sem_correcao_fica_como_aviso() -> None:
    revisao = rever_estilo(_plano(_com_texto("Recuperação total, execução perfeitamente lenta.")))
    assert revisao.avisos == ("total", "perfeitamente")
    assert revisao.plano.resumo.endswith("Recuperação total, execução perfeitamente lenta.")


def test_protege_fica_como_aviso_sem_bloquear() -> None:
    texto = "O plano protege os joelhos e ajuda a proteger a tensão."
    assert _falhas(_com_texto(texto)) == []
    assert rever_estilo(_plano(_com_texto(texto))).avisos == ("protege", "proteger")


def test_promessas_nos_outros_campos_da_llm() -> None:
    resposta = _resposta()
    resposta["prioridades_alimentares"][0] = "Fase 1: resultados garantidos."
    assert "promessa" in [t for t, _ in _falhas(resposta)]


# ---------------------------------------------------------------- Tai Chi (REGRAS §3)


def test_tai_chi_so_se_a_pessoa_o_pratica() -> None:
    texto = "Pode manter o seu Tai Chi aos sábados."
    assert _falhas(_com_texto(texto)) == []  # a persona tem «tai_chi» nas preferências
    sem = _q(preferencias=["caminhada", "forca"])
    falhas = _falhas(_com_texto(texto), sem)
    assert falhas == [
        (
            "tai_chi",
            "O texto menciona o Tai Chi, que não está no programa: só pode ser referido se a "
            "pessoa já o praticar (indicado nas preferências).",
        )
    ]
    assert [t for t, _ in _falhas(_com_texto("Faça tai-chi."), sem)] == ["tai_chi"]


# ---------------------------------------------------------------- Sem intervalos (30/10/2026)


def _imc36() -> Questionario:
    return _q("persona_imc36.json")


def test_imc36_plano_de_referencia_passa_sem_intervalos() -> None:
    q = _imc36()
    assert gerar_estrategia(q).restricoes.sem_intervalos
    assert _falhas(_resposta(), q) == []


@pytest.mark.parametrize(
    ("texto", "termo"),
    [
        ("Na marcha, alternando 30 s mais vivos com 30 s calmos.", "alternando 30 s"),
        ("Faça 30 s mais vivos.", "30 s mais vivos"),
        ("Caminhe em ritmo vivo.", "ritmo vivo"),
        ("Um treino intervalado leve.", "intervalado"),
        ("Pode alternar ritmos na passadeira.", "alternar ritmos"),
        ("Alternando 1 minuto rápido e 1 minuto lento.", "Alternando 1 minuto"),
    ],
)
def test_alternancia_de_ritmos_bloqueia_com_sem_intervalos(texto: str, termo: str) -> None:
    falhas = _falhas(_com_texto(texto), _imc36())
    motivos = [m for t, m in falhas if t == TipoFalha.INTERVALOS.value]
    assert any(f"«{termo}»" in m for m in motivos), falhas
    assert TipoFalha.INTERVALOS not in TIPOS_DO_MOTOR  # leva a regenerar
    # Sem a restrição, a mesma frase não é falha de intervalos.
    assert TipoFalha.INTERVALOS.value not in [t for t, _ in _falhas(_com_texto(texto))]


@pytest.mark.parametrize(
    "texto",
    [
        "Ritmo contínuo e confortável, sem alternar ritmos.",
        "Suba o degrau alternando a perna.",
        "Toque alternadamente no ombro oposto.",
        "Sem alternância de ritmos.",
    ],
)
def test_ritmo_continuo_e_alternar_pernas_passam(texto: str) -> None:
    assert mencoes_de_intervalos(texto) == ()
    assert _falhas(_com_texto(texto), _imc36()) == []


def test_alternancia_no_texto_do_motor_e_erro_do_codigo() -> None:
    q = _imc36()
    e = gerar_estrategia(q)
    plano = _plano(_resposta(), q)
    v2 = plano.treino.estrutura_sessao.model_copy(
        update={
            "cardio_finalizador": "Marcha no lugar, alternando 30 s mais vivos com 30 s calmos."
        }
    )
    plano = plano.model_copy(
        update={"treino": plano.treino.model_copy(update={"estrutura_sessao": v2})}
    )
    falhas = verificar(plano, e, q)
    assert {f.tipo for f in falhas} == {TipoFalha.INTERVALOS_NO_TREINO}
    assert TipoFalha.INTERVALOS_NO_TREINO in TIPOS_DO_MOTOR
    assert falhas[0].motivo.startswith("Estrutura da sessão: o texto do treino tem «")


# ---------------------------------------------------------------- Ortografia (só aviso)


def test_ortografia_apanha_palavra_inventada() -> None:
    plano = _plano(_com_texto("Mantenha a durquetura e a acção."))
    assert palavras_desconhecidas(plano) == ("durquetura", "acção")  # «acção» é pré-AO90


def test_ortografia_aceita_referencia_e_vocabulario_do_programa() -> None:
    assert palavras_desconhecidas(_plano(_resposta())) == ()
    texto = "Exercício aeróbio; bird-dog; ultraprocessados; Pequeno-almoço; unipodal; tónus."
    assert palavras_desconhecidas(_plano(_com_texto(texto))) == ()


def test_ortografia_aceita_tai_chi() -> None:
    assert "tai_chi" in _q().preferencias  # a persona já pratica Tai Chi
    texto = "Mantenha o seu Tai Chi; o tai-chi complementa o plano."
    assert palavras_desconhecidas(_plano(_com_texto(texto))) == ()


def test_ortografia_nao_chumba_o_plano() -> None:
    assert _falhas(_com_texto("Mantenha a durquetura.")) == []


# ---------------------------------------------------------------- Acentos (correção automática)


def test_acento_em_falta_e_corrigido() -> None:
    plano, correcoes = corrigir_acentuacao(_plano(_com_texto("Faça os exercicios com calma.")))
    assert "Faça os exercícios com calma." in plano.resumo
    assert correcoes == ("exercicios → exercícios",)
    assert palavras_desconhecidas(plano) == ()


def test_acento_mantem_maiuscula_e_corrige_em_todos_os_campos() -> None:
    resposta = _com_texto("Sessoes curtas.")
    resposta["notas_personalizadas"][0] += " Sessoes curtas."
    plano, correcoes = corrigir_acentuacao(_plano(resposta))
    assert "Sessões curtas." in plano.resumo
    assert plano.notas_personalizadas[0].endswith("Sessões curtas.")
    assert correcoes == ("Sessoes → Sessões",)


def test_sem_forma_acentuada_fica_so_como_aviso() -> None:
    plano, correcoes = corrigir_acentuacao(_plano(_com_texto("Mantenha a durquetura e a acção.")))
    assert correcoes == ()  # «acção» difere de «ação» numa letra, não só no acento
    assert palavras_desconhecidas(plano) == ("durquetura", "acção")


def test_mais_de_uma_forma_acentuada_nao_corrige(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Dicionario:
        def suggest(self, palavra: str) -> list[str]:
            return ["pêlo", "pélo", "pelos"]

        def lookup(self, palavra: str) -> bool:
            return True

    monkeypatch.setattr(ortografia, "_dicionario", lambda: _Dicionario())
    assert forma_acentuada("pelo") is None


def test_sem_palavras_desconhecidas_nao_muda_o_plano() -> None:
    plano = _plano(_resposta())
    assert corrigir_acentuacao(plano) == (plano, ())
