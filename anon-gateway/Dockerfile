# ============================================================
# Argus — anon-gateway (pilier Snowpack)
# Égress OSINT anonymisé (Tor SOCKS) + scaffolding PQC mesh.
#
# Fournit de façon fiable :
#   - Tor SOCKS5 sur :9050 (égress anonymisé pour l'OSINT du SOC)
#   - un shim HTTP NEWNYM sur :9052 (rotation d'identité Tor)
# Optionnels (si configs montées) :
#   - WireGuard (wg0) — plan de management sans port entrant
#   - Rosenpass — couche d'échange de clés POST-QUANTIQUE (ML-KEM) sur WireGuard
# ============================================================
FROM alpine:3.20

RUN apk add --no-cache \
      tor \
      obfs4proxy \
      python3 \
      wireguard-tools \
      iptables \
      curl

# Rosenpass (PQC) est un binaire Rust optionnel : le déposer dans
# /usr/local/bin/rosenpass (build séparé) pour activer le volet post-quantique.
# Sans lui, la passerelle fonctionne en Tor-only (égress anonymisé).

COPY torrc            /etc/tor/torrc
COPY newnym.py        /usr/local/bin/newnym.py
COPY entrypoint.sh    /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh \
 && mkdir -p /var/lib/tor && chown -R tor:tor /var/lib/tor

# 9050 = SOCKS Tor ; 9052 = shim NEWNYM. Internes à soc-net (non exposés sur l'hôte).
EXPOSE 9050 9052

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
