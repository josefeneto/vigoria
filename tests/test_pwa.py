"""Camada PWA e contentor (Fase 10A): injeção no index.html, manifesto, Caddyfile, Docker."""

import json
import re
from pathlib import Path

import pytest

from paginas.estilos import CORES
from vigoria import pwa
from vigoria.pwa import MARCA_INJECAO, PONTO_INSERCAO, ErroInjecao, injetar

RAIZ = Path(__file__).resolve().parents[1]
PASTA_PWA = RAIZ / "pwa"
CADDYFILE = (PASTA_PWA / "Caddyfile").read_text(encoding="utf-8")
DOCKERFILE = (RAIZ / "Dockerfile").read_text(encoding="utf-8")
DOCKERIGNORE = (RAIZ / ".dockerignore").read_text(encoding="utf-8").splitlines()
HTML = '<!DOCTYPE html>\n<html lang="en">\n<head>\n<title>Streamlit</title>\n</head></html>'


# ---------------------------------------------------------------- injeção


def test_injeta_manifesto_e_etiquetas_do_iphone_antes_do_titulo() -> None:
    novo = injetar(HTML)
    cabeca = novo.split(PONTO_INSERCAO)[0]
    assert '<link rel="manifest" href="/manifest.webmanifest" />' in cabeca
    assert '<link rel="apple-touch-icon" href="/apple-touch-icon.png" />' in cabeca
    assert 'name="apple-mobile-web-app-capable" content="yes"' in cabeca
    assert '<html lang="pt-PT">' in novo


def test_injetar_duas_vezes_nao_repete() -> None:
    uma = injetar(HTML)
    assert injetar(uma) == uma
    assert uma.count(MARCA_INJECAO) == 1


@pytest.mark.parametrize("html", ["<html><head></head></html>", HTML + HTML])
def test_sem_ponto_de_insercao_unico_falha_com_mensagem_clara(html: str) -> None:
    with pytest.raises(ErroInjecao, match="PONTO_INSERCAO"):
        injetar(html)


def test_principal_falha_a_construcao(tmp_path: Path) -> None:
    ficheiro = tmp_path / "index.html"
    ficheiro.write_text("<html></html>", encoding="utf-8")
    assert pwa.principal(ficheiro) == 1
    ficheiro.write_text(HTML, encoding="utf-8")
    assert pwa.principal(ficheiro) == 0
    assert MARCA_INJECAO in ficheiro.read_text(encoding="utf-8")


def test_o_streamlit_instalado_tem_o_ponto_de_insercao() -> None:
    """Falha aqui, antes do Docker, se uma atualização do Streamlit mudar o index.html."""
    html = pwa.index_streamlit().read_text(encoding="utf-8")
    assert MARCA_INJECAO in html or html.count(PONTO_INSERCAO) == 1


# ---------------------------------------------------------------- manifesto e ícones


def test_manifesto_aponta_para_icones_que_existem() -> None:
    dados = json.loads((PASTA_PWA / "manifest.webmanifest").read_text(encoding="utf-8"))
    assert dados["display"] == "standalone" and dados["lang"] == "pt-PT"
    assert dados["start_url"] == "/" and dados["scope"] == "/"
    assert dados["theme_color"] == CORES["principal_profundo"] == pwa.COR_TEMA
    assert dados["background_color"] == CORES["fundo"]
    tamanhos = {(i["sizes"], i["purpose"]) for i in dados["icons"]}
    assert {("192x192", "any"), ("512x512", "any"), ("512x512", "maskable")} <= tamanhos
    for icone in dados["icons"]:
        assert (PASTA_PWA / icone["src"].lstrip("/")).is_file(), icone["src"]


def test_icones_da_raiz_existem() -> None:
    for nome in ("apple-touch-icon.png", "favicon.ico"):
        assert (PASTA_PWA / nome).is_file()


# ---------------------------------------------------------------- Caddyfile


def test_caddy_serve_a_pwa_e_encaminha_o_resto_para_o_streamlit() -> None:
    assert ":{$PORT:8080}" in CADDYFILE
    assert "@pwa path /manifest.webmanifest /apple-touch-icon.png /favicon.ico /icones/*" in (
        CADDYFILE
    )
    assert "root * /srv/pwa" in CADDYFILE
    assert "reverse_proxy 127.0.0.1:8501" in CADDYFILE
    assert 'Content-Type "application/manifest+json"' in CADDYFILE


def test_cabecalhos_de_seguranca_hsts_so_deste_dominio() -> None:
    hsts = [linha.strip() for linha in CADDYFILE.splitlines() if "Strict-Transport" in linha]
    assert hsts == ['Strict-Transport-Security "max-age=31536000"']  # sem subdomínios nem preload
    for cabecalho in ('X-Content-Type-Options "nosniff"', "Referrer-Policy", "X-Frame-Options"):
        assert cabecalho in CADDYFILE
    assert re.search(r"^\s*log\b", CADDYFILE, re.MULTILINE) is None  # sem registo de acessos


# ---------------------------------------------------------------- Docker


def test_imagem_corre_sem_privilegios_e_sem_segredos() -> None:
    assert "FROM python:3.14-slim" in DOCKERFILE
    assert re.search(r"^USER vigoria$", DOCKERFILE, re.MULTILINE)
    assert "python -m vigoria.pwa" in DOCKERFILE
    copias = " ".join(re.findall(r"^COPY .*$", DOCKERFILE, re.MULTILINE))
    assert "secrets.toml" not in copias and ".env" not in copias
    assert "COPY . " not in DOCKERFILE  # só pastas escolhidas


@pytest.mark.parametrize(
    "padrao", [".env", ".env.*", ".streamlit/secrets.toml", "docs/", "tests/", "saidas/", ".git/"]
)
def test_dockerignore_exclui(padrao: str) -> None:
    assert padrao in DOCKERIGNORE


def test_script_de_arranque_so_escuta_em_localhost() -> None:
    script = (RAIZ / "docker" / "arrancar.sh").read_text(encoding="utf-8")
    assert "\r" not in script
    assert "python -m vigoria.arranque" in script
    assert "--server.address 127.0.0.1" in script and "--server.port 8501" in script
    assert "wait -n" in script


def test_cancelar_vai_para_o_servico_starlette_sem_registo_de_acessos() -> None:
    """Fase 10B: /cancelar (RFC 8058) para o uvicorn; o endereço leva o token."""
    assert "handle /cancelar {\n\t\treverse_proxy 127.0.0.1:8001" in CADDYFILE
    script = (RAIZ / "docker" / "arrancar.sh").read_text(encoding="utf-8")
    assert "vigoria.web.cancelar:criar_app" in script
    assert "--host 127.0.0.1" in script and "--port 8001" in script
    assert "--no-access-log" in script
