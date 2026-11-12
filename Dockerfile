# Imagem de produção da Vigoria (Fase 10): Streamlit em 127.0.0.1:8501 e Caddy à frente,
# na porta $PORT do Railway. Construir (PowerShell, na raiz do projeto):
#   docker build -t vigoria .
# Os segredos nunca entram na imagem: chegam como variáveis do serviço e o
# .streamlit/secrets.toml é gerado no arranque (src/vigoria/arranque.py).

FROM caddy:2.10.2 AS caddy

# ---------------------------------------------------------------- dependências
FROM python:3.14-slim AS construcao
ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /construcao
RUN python -m venv /opt/venv
ENV PATH=/opt/venv/bin:$PATH
COPY requirements.txt pyproject.toml ./
# O requirements.txt acaba em «-e .» (para o Community Cloud); aqui instala-se o pacote à parte.
RUN grep -v '^-e ' requirements.txt > requisitos.txt \
    && python -m pip install -r requisitos.txt
COPY src ./src
RUN python -m pip install --no-deps . \
    && python -m vigoria.pwa

# ---------------------------------------------------------------- imagem final
FROM python:3.14-slim
ENV PATH=/opt/venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8080
RUN useradd --create-home --uid 10001 vigoria
COPY --from=caddy /usr/bin/caddy /usr/local/bin/caddy
COPY --from=construcao /opt/venv /opt/venv

WORKDIR /app
COPY app.py ./
COPY paginas ./paginas
COPY static ./static
COPY assets ./assets
COPY .streamlit/config.toml ./.streamlit/config.toml
COPY pwa/Caddyfile /etc/caddy/Caddyfile
COPY pwa/manifest.webmanifest pwa/apple-touch-icon.png pwa/favicon.ico /srv/pwa/
COPY pwa/icones /srv/pwa/icones
COPY docker/arrancar.sh /usr/local/bin/arrancar.sh
# Fins de linha Unix no script (por precaução, se o Git os converter no Windows); a pasta
# .streamlit é do utilizador da app, porque o arranque escreve lá o secrets.toml.
RUN sed -i 's/\r$//' /usr/local/bin/arrancar.sh \
    && chmod 755 /usr/local/bin/arrancar.sh \
    && chown vigoria:vigoria /app/.streamlit

USER vigoria
EXPOSE 8080
CMD ["arrancar.sh"]
