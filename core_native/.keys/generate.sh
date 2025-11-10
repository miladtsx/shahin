#!/bin/sh
set -e

# --- integrity keys (PKCS8 private + SPKI DER public) ---
openssl genpkey -algorithm EC -pkeyopt ec_paramgen_curve:P-256 \
  -out integrity_private_pkcs8.pem

openssl pkey -in integrity_private_pkcs8.pem -pubout -outform DER \
  -out integrity_public.der

# --- licensing keys (PKCS8 private + SPKI DER public) ---
openssl genpkey -algorithm EC -pkeyopt ec_paramgen_curve:P-256 \
  -out licensing_private_pkcs8.pem

openssl pkey -in licensing_private_pkcs8.pem -pubout -outform DER \
  -out licensing_public.der
