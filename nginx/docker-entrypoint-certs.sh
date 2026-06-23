#!/bin/sh
# Génère un certificat TLS auto-signé au démarrage s'il est absent, afin que
# `docker compose up` fonctionne sans étape préalable. En production, fournir
# un vrai certificat dans nginx/certs/ (monté en volume).
set -e
CERT=/etc/nginx/certs/soc.crt
KEY=/etc/nginx/certs/soc.key

if [ ! -s "$CERT" ] || [ ! -s "$KEY" ]; then
    echo "[nginx] Certificat absent — génération d'un auto-signé (CN=${SOC_DOMAIN:-soc.lan})"
    mkdir -p /etc/nginx/certs
    if openssl req -x509 -newkey rsa:4096 -nodes -days 825 \
        -keyout "$KEY" -out "$CERT" \
        -subj "/C=FR/O=Argus/CN=${SOC_DOMAIN:-soc.lan}" \
        -addext "subjectAltName=DNS:${SOC_DOMAIN:-soc.lan},DNS:localhost,IP:127.0.0.1" 2>/dev/null; then
        echo "[nginx] Certificat auto-signé généré."
    else
        echo "[nginx] Échec OpenSSL — fournir nginx/certs/soc.crt et soc.key manuellement."
    fi
fi

exec nginx -g 'daemon off;'
