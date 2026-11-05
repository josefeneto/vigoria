"""Capturas da interface a 390 px (telemóvel) e a 1280 px (computador), só em desenvolvimento.

Arranca o Streamlit com o fornecedor simulado (nunca chama uma LLM real) e o utilizador local
fictício (sem Auth0), numa base SQLite própria em saidas/capturas/, percorre os passos do
questionário, as secções do plano, a conta e o progresso (com os cenários de
scripts/registos_ficticios.py) e guarda PNG em saidas/capturas/.
Usa o Google Chrome instalado (channel="chrome"): não é preciso «playwright install».

    python scripts/capturas.py            # em saidas/capturas/
    python scripts/capturas.py antes      # em saidas/capturas/antes/ (para comparar)
"""

import os
import socket
import subprocess
import sys
import time
from pathlib import Path

from playwright.sync_api import Error, Page, sync_playwright

RAIZ = Path(__file__).resolve().parents[1]
SAIDA = RAIZ / "saidas" / "capturas"
PORTA = 8599
URL = f"http://localhost:{PORTA}"
# Altura grande: o Streamlit desloca o conteúdo dentro da página, não no documento.
LARGURAS = {"telemovel": (390, 2600), "computador": (1280, 2200)}
PASSOS = ("1", "2a", "2b", "3", "4a", "4b", "5", "6")
SECCOES = ("Resumo", "Treino", "Alimentação", "Hábitos", "Acompanhamento", "Manutenção")
CENARIOS = ("normal", "lenta", "rapida", "manutencao")


def _ambiente() -> dict[str, str]:
    return os.environ | {
        "VIGORIA_PROVEDOR_LLM": "simulado",
        "VIGORIA_PROVEDOR_RESERVA": "",
        "AMBIENTE": "local",
        "VIGORIA_UTILIZADOR_LOCAL": "1",
        "DATABASE_URL": f"sqlite:///{(SAIDA / 'capturas.db').as_posix()}",  # nunca a do José
    }


def _arrancar() -> subprocess.Popen[bytes]:
    env = _ambiente()
    comando = [sys.executable, "-m", "streamlit", "run", "app.py", "--server.headless=true"]
    comando += [f"--server.port={PORTA}", "--browser.gatherUsageStats=false"]
    processo = subprocess.Popen(comando, cwd=RAIZ, env=env, stdout=subprocess.DEVNULL)
    for _ in range(60):
        with socket.socket() as s:
            if s.connect_ex(("localhost", PORTA)) == 0:
                return processo
        time.sleep(0.5)
    processo.terminate()
    sys.exit("O Streamlit não arrancou em 30 s.")


def _esperar(page: Page) -> None:
    """Espera que o Streamlit acabe de correr o script."""
    page.wait_for_timeout(400)
    # Ao abrir uma página, o Streamlit demora cerca de 2 s a desenhar; todas têm um título h1.
    page.wait_for_selector('[data-testid="stMain"] h1')
    page.wait_for_selector('[data-testid="stStatusWidget"]', state="detached", timeout=60_000)
    page.wait_for_timeout(600)


def _clicar(page: Page, nome: str) -> None:
    page.get_by_role("button", name=nome, exact=False).first.click()
    _esperar(page)


def _capturar(page: Page, largura: str, nome: str) -> None:
    caminho = SAIDA / f"{largura}_{nome}.png"
    page.screenshot(path=str(caminho))
    print(f"  {caminho.relative_to(RAIZ)}")


def _percorrer(page: Page, largura: str) -> None:
    page.goto(URL)
    _esperar(page)
    _capturar(page, largura, "00_inicio")

    page.goto(f"{URL}/questionario")
    _esperar(page)
    _capturar(page, largura, "01_passo_0")
    _clicar(page, "Seguinte")
    _capturar(page, largura, "02_passo_0_erros")

    # Preenche com a persona de teste (barra lateral, só em AMBIENTE=local) e volta ao passo 1.
    if largura == "telemovel":
        page.locator('[data-testid="stExpandSidebarButton"]').click()
        page.wait_for_timeout(500)
    _clicar(page, "Preencher com a persona de teste")
    if largura == "telemovel":
        page.locator('[data-testid="stSidebarCollapseButton"] button').click()
        page.wait_for_timeout(500)
    _clicar(page, "Alterar")
    for i, passo in enumerate(PASSOS, start=3):
        _capturar(page, largura, f"{i:02d}_passo_{passo}")
        _clicar(page, "Seguinte")
    _capturar(page, largura, "11_passo_7")
    tamanho = page.viewport_size or {"width": 390, "height": 2600}
    page.set_viewport_size({"width": tamanho["width"], "height": 5200})  # o passo 7 é longo
    page.wait_for_timeout(500)
    _capturar(page, largura, "11b_passo_7_completo")
    page.set_viewport_size(tamanho)

    _clicar(page, "Gerar o meu plano")
    page.wait_for_url("**/plano", timeout=60_000)
    _esperar(page)
    for i, separador in enumerate(SECCOES, start=12):
        page.locator(".st-key-plano_seccao").get_by_role("radio", name=separador).click()
        _esperar(page)
        _capturar(page, largura, f"{i:02d}_plano_{separador.lower()}")
        if separador in ("Treino", "Manutenção"):  # secções longas: também inteiras
            tamanho = page.viewport_size or {"width": 390, "height": 2600}
            page.set_viewport_size({"width": tamanho["width"], "height": 7000})
            page.wait_for_timeout(500)
            _capturar(page, largura, f"{i:02d}b_plano_{separador.lower()}_completo")
            page.set_viewport_size(tamanho)

    page.goto(f"{URL}/privacidade")
    _esperar(page)
    _capturar(page, largura, "18_privacidade")

    page.goto(f"{URL}/conta")
    _esperar(page)
    page.get_by_role("button", name="Apagar a conta e os dados").wait_for()
    page.wait_for_timeout(600)
    _capturar(page, largura, "19_conta")

    # Cada cenário cria um plano novo, com a data recuada; abrir a página de novo carrega-o.
    tamanho = page.viewport_size or {"width": 390, "height": 2600}
    for i, cenario in enumerate(CENARIOS, start=20):
        script = RAIZ / "scripts" / "registos_ficticios.py"
        subprocess.run([sys.executable, str(script), cenario], env=_ambiente(), check=True)
        page.set_viewport_size({"width": tamanho["width"], "height": 9000})
        page.goto(f"{URL}/progresso")
        _esperar(page)
        page.wait_for_timeout(2000)  # os gráficos desenham-se depois do resto
        _capturar(page, largura, f"{i}_progresso_{cenario}")
        page.set_viewport_size(tamanho)
    page.goto(f"{URL}/plano")  # o último cenário está na manutenção: com o convite no Resumo
    _esperar(page)
    page.get_by_role("link", name="Voltar ao questionário").wait_for()  # o fim da página
    page.wait_for_timeout(600)
    _capturar(page, largura, "24_plano_na_manutencao")


def main() -> None:
    global SAIDA
    if len(sys.argv) > 1:
        SAIDA = SAIDA / sys.argv[1]
    SAIDA.mkdir(parents=True, exist_ok=True)
    (SAIDA / "capturas.db").unlink(missing_ok=True)
    processo = _arrancar()
    try:
        with sync_playwright() as p:
            try:
                browser = p.chromium.launch(channel="chrome", headless=True)
            except Error as erro:
                sys.exit(f"Não foi possível abrir o Google Chrome instalado: {erro}")
            for largura, (x, y) in LARGURAS.items():
                print(f"{largura} ({x} px):")
                contexto = browser.new_context(viewport={"width": x, "height": y})
                _percorrer(contexto.new_page(), largura)
                contexto.close()
            browser.close()
    finally:
        processo.terminate()


if __name__ == "__main__":
    main()
