# ============================================================
# Nginx — Reverse Proxy SOC Platform (TLS hybride post-quantique)
# ------------------------------------------------------------
# Base épinglée sur nginx:1.29-alpine, qui embarque OpenSSL >= 3.5.
# OpenSSL 3.5 supporte nativement le groupe d'échange de clés hybride
# X25519MLKEM768 (X25519 + ML-KEM-768 / FIPS 203), activé dans nginx.conf
# via `ssl_ecdh_curve`. Aucune compilation d'oqs-provider requise.
#
# Fallback : sur une base avec OpenSSL < 3.5, retirer la directive
# `ssl_ecdh_curve X25519MLKEM768:...` de nginx.conf (le reste fonctionne).
# ============================================================
FROM nginx:1.29-alpine
RUN apk add --no-cache openssl
COPY nginx.conf /etc/nginx/nginx.conf
COPY docker-entrypoint-certs.sh /docker-entrypoint-certs.sh
# Les certificats sont montés depuis le volume ; l'entrypoint en génère un
# auto-signé au démarrage s'il est absent (cf. docker-entrypoint-certs.sh).
RUN mkdir -p /etc/nginx/certs && chmod +x /docker-entrypoint-certs.sh
EXPOSE 80 443
ENTRYPOINT ["/docker-entrypoint-certs.sh"]
