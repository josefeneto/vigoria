"""Tai Chi (opcional): quem o vê e com que nível (REGRAS_DOMINIO §5.2, T1 a T7).

Os minutos (T3) e os níveis das ligações (T6) são os da dança: regras/atividades.py.
Funções puras, sem I/O.
"""

from vigoria.modelos.questionario import Condicao, Limitacao, Preferencia, Questionario


def tem_taichi(q: Questionario) -> bool:
    """T1: o bloco só aparece a quem marcou «Tai Chi» nas preferências."""
    return Preferencia.TAI_CHI in q.preferencias


def so_nivel_ligeira(q: Questionario) -> bool:
    """T6: com a limitação «equilíbrio» (qualquer gravidade) ou com osteoporose, só o nível
    ligeira (Tai Chi na cadeira)."""
    return Limitacao.EQUILIBRIO in q.limitacoes or Condicao.OSTEOPOROSE in q.condicoes
