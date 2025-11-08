#!/bin/sh

openssl ecparam -name prime256v1 -genkey -noout -out integrity_private.pem
openssl ec -in integrity_private.pem -pubout -out integrity_public.pem
openssl ec -in integrity_private.pem -pubout -outform DER -out integrity_public.der


openssl ecparam -name prime256v1 -genkey -noout -out licensing_private.pem
openssl ec -in licensing_private.pem -pubout -out licensing_public.pem
openssl ec -in licensing_private.pem -pubout -outform DER -out licensing_public.der