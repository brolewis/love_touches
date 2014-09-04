#!/usr/bin/env bash
if [ "x" = "x$VIRTUAL_ENV" ]
then
    uwsgi -s /tmp/love_touches.sock -w wsgi:app --chmod-socket --master --process 4 --threads 2
else
    uwsgi -s /tmp/love_touches.sock -w wsgi:app --chmod-socket --master --process 4 --threads 2 --venv $VIRTUAL_ENV
fi
