#!/usr/bin/env bash
# Arranque do serviço web no Railway (Fase 10): secrets.toml e migrações, depois o Streamlit
# e o cancelamento dos lembretes (só em 127.0.0.1) e o Caddy na porta $PORT. Se um parar, o
# contentor termina e o Railway reinicia-o. O serviço cron dos lembretes NÃO usa este script (docs/GUIA_PRODUCAO.md).
set -euo pipefail

cd /app
python -m vigoria.arranque

python -m streamlit run app.py \
	--server.headless true \
	--server.address 127.0.0.1 \
	--server.port 8501 \
	--server.fileWatcherType none &

# Cancelamento dos lembretes num clique (Fase 10B). Sem registo de acessos: o endereço leva
# o token.
python -m uvicorn --factory vigoria.web.cancelar:criar_app \
	--host 127.0.0.1 \
	--port 8001 \
	--no-access-log \
	--no-server-header &

caddy run --config /etc/caddy/Caddyfile --adapter caddyfile &

# Ao receber o sinal de paragem do Railway, passa-o aos três processos.
trap 'kill -TERM $(jobs -p) 2>/dev/null || true' TERM INT
set +e
wait -n
estado=$?
echo "arrancar: um dos processos terminou (código $estado); a parar o contentor" >&2
kill -TERM $(jobs -p) 2>/dev/null || true
# Nenhum devia terminar sozinho: mesmo com código 0, sai com erro para reiniciar.
if [ "$estado" -eq 0 ]; then estado=1; fi
exit "$estado"
