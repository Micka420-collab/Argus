#!/bin/sh
# ============================================================
# anon-gateway — point d'entrée
# Démarre : (option) WireGuard + Rosenpass PQC, le shim NEWNYM, puis Tor.
# ============================================================
set -e

# --- Optionnel : WireGuard (plan de management sans port entrant) -----------
if [ -f /etc/wireguard/wg0.conf ]; then
    echo "[anon-gateway] WireGuard : montée de wg0"
    wg-quick up wg0 || echo "[anon-gateway] wg-quick a échoué (NET_ADMIN / module wireguard ?)"
fi

# --- Optionnel : Rosenpass (échange de clés POST-QUANTIQUE ML-KEM) ----------
# Renforce chaque tunnel WireGuard d'une couche post-quantique.
if command -v rosenpass >/dev/null 2>&1 && [ -f /etc/rosenpass/rp.toml ]; then
    echo "[anon-gateway] Rosenpass : échange PQC actif"
    rosenpass exchange-config /etc/rosenpass/rp.toml &
elif [ -f /etc/rosenpass/rp.toml ]; then
    echo "[anon-gateway] Rosenpass configuré mais binaire absent — tunnel WireGuard classique"
fi

# --- Shim HTTP NEWNYM (rotation d'identité Tor) -----------------------------
python3 /usr/local/bin/newnym.py &
echo "[anon-gateway] shim NEWNYM : http://anon-gateway:9052/newnym"

# --- Tor (premier plan) -----------------------------------------------------
echo "[anon-gateway] Tor SOCKS : socks5://anon-gateway:9050"
exec tor -f /etc/tor/torrc
