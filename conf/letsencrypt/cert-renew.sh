#!/bin/bash

config_file=/opt/letsencrypt/%(renew_conf)s
domain=%(domain)s
exp_limit=30;

if [ ! -f $config_file ]; then
    echo "[ERROR] config file does not exist: $config_file"
    exit 1;
fi

cert_file="/etc/letsencrypt/live/$domain/fullchain.pem"
if [ ! -f $cert_file ]; then
    echo "[ERROR] certificate file not found for domain $domain."
fi
exp=$(date -d "`openssl x509 -in $cert_file -text -noout|grep "Not After"|cut -c 25-`" +%s)
datenow=$(date -d "now" +%s)
days_exp=$(echo \( $exp - $datenow \) / 86400 |bc)
if [ "$days_exp" -lt "$exp_limit" ] ; then
    /opt/letsencrypt/letsencrypt-auto certonly -a webroot --agree-tos --renew-by-default --config $config_file
    /usr/sbin/service nginx reload
fi
