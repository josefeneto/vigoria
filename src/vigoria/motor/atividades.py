"""Ligações a mostrar das atividades opcionais (dança e Tai Chi; D6 e T6).

Correm ao mostrar (app e PDF), a partir do YAML, para as ligações estarem sempre
atualizadas também nos planos guardados.
"""

from dataclasses import dataclass

from vigoria.conteudo.carregar import ConteudoDanca, ConteudoTaiChi, LigacaoAtividade, NivelLigacao
from vigoria.modelos.questionario import Intensidade
from vigoria.regras import atividades as regras


@dataclass(frozen=True)
class LigacoesAtividade:
    """O que mostrar: o nível da pessoa, um do nível abaixo e as «Mais aulas» (só dança)."""

    principais: tuple[LigacaoAtividade, ...]
    mais_calmo: LigacaoAtividade | None
    mais_aulas: tuple[LigacaoAtividade, ...]
    ajuste: str  # o texto de ajuste (vazio no Tai Chi)

    def grupos(
        self, principais: str, mais_calmo: str, mais_aulas: str = ""
    ) -> list[tuple[str, list[tuple[str, str, str]]]]:
        """Para mostrar (app e PDF): (rótulo, [(título, url, canal)]), sem grupos vazios."""
        grupos = [(principais, [(x.titulo, x.url, x.canal) for x in self.principais])]
        if self.mais_calmo is not None:
            x = self.mais_calmo
            grupos.append((mais_calmo, [(x.titulo, x.url, x.canal)]))
        if self.mais_aulas:
            grupos.append((mais_aulas, [(x.titulo, x.url, x.canal) for x in self.mais_aulas]))
        return grupos


def escolher_ligacoes(
    conteudo: ConteudoDanca | ConteudoTaiChi,
    intensidade: Intensidade,
    so_ligeira: bool,
    *,
    mais_aulas: bool = False,
    ajuste: str = "",
) -> LigacoesAtividade:
    nivel = regras.nivel_das_ligacoes(intensidade, so_ligeira)
    abaixo = regras.nivel_mais_calmo(intensidade, so_ligeira)
    return LigacoesAtividade(
        principais=conteudo.do_nivel(NivelLigacao(nivel)),
        mais_calmo=conteudo.do_nivel(NivelLigacao(abaixo))[0] if abaixo is not None else None,
        mais_aulas=conteudo.do_nivel(NivelLigacao.MAIS_AULAS) if mais_aulas else (),
        ajuste=ajuste,
    )
