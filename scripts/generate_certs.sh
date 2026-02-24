#!/bin/bash
# ============================================================
# Génération certificats TLS self-signed pour Nginx
# Utilise openssl — valide 10 ans, SAN pour IP locale
#
# Usage: ./scripts/generate_certs.sh [IP_OU_DOMAINE]
# Ex:    ./scripts/generate_certs.sh 192.168.1.100
#        ./scripts/generate_certs.sh soc.monreseau.local
# ============================================================

set -euo pipefail

HOST="${1:-$(hostname -I | awk '{print $1}')}"
CERTS_DIR="$(dirname "$0")/../nginx/certs"
mkdir -p "$CERTS_DIR"

echo "[+] Génération certificat TLS pour : $HOST"

# Configuration SAN (Subject Alternative Names) pour Chrome/Firefox
cat > /tmp/soc_openssl.cnf << EOF
[req]
default_bits       = 4096
prompt             = no
default_md         = sha256
distinguished_name = dn
x509_extensions    = v3_req

[dn]
C  = FR
ST = France
L  = Paris
O  = SOC Platform
OU = Security Operations
CN = $HOST

[v3_req]
subjectAltName = @alt_names
keyUsage = critical, digitalSignature, keyEncipherment
extendedKeyUsage = serverAuth
basicConstraints = critical, CA:false

[alt_names]
DNS.1 = $HOST
DNS.2 = localhost
DNS.3 = soc-platform
IP.1  = $HOST
IP.2  = 127.0.0.1
EOF

# Générer clé privée + certificat auto-signé
openssl req -x509 -newkey rsa:4096 \
    -keyout "$CERTS_DIR/soc.key" \
    -out    "$CERTS_DIR/soc.crt" \
    -days   3650 \
    -nodes \
    -config /tmp/soc_openssl.cnf

# Sécuriser la clé privée
chmod 600 "$CERTS_DIR/soc.key"
chmod 644 "$CERTS_DIR/soc.crt"

rm -f /tmp/soc_openssl.cnf

echo ""
echo "[✓] Certificat généré :"
echo "    Clé     : $CERTS_DIR/soc.key"
echo "    Certificat : $CERTS_DIR/soc.crt"
echo ""
echo "[i] Pour éviter l'avertissement navigateur :"
echo "    Importer $CERTS_DIR/soc.crt comme Autorité de Certification"
echo "    Dans Chrome : Paramètres > Sécurité > Certificats > Autorités"
echo ""
echo "[i] Sur les machines du réseau (Linux) :"
echo "    sudo cp $CERTS_DIR/soc.crt /usr/local/share/ca-certificates/soc-platform.crt"
echo "    sudo update-ca-certificates"

# Afficher les infos du certificat
echo ""
echo "[i] Informations certificat :"
openssl x509 -in "$CERTS_DIR/soc.crt" -noout -text | grep -E "(Subject:|DNS:|IP Address:|Not After)"
