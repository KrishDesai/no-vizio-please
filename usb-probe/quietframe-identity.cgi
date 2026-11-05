#!/bin/sh
printf 'Content-Type: text/plain; charset=utf-8\r\nCache-Control: no-store\r\n\r\n'
printf 'QUIETFRAME_IDENTITY_BEGIN\nuid='
id -u
printf 'os='
uname -s
printf 'arch='
uname -m
printf 'QUIETFRAME_IDENTITY_END\n'
