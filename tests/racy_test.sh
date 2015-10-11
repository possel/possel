#!/bin/bash
set -eu -o pipefail

DATABASE_FILE="possel_racy_test.db"
DATABASE="sqlite:///$DATABASE_FILE"
COOKIE_FILE="./possel_racy_test.cookies"

POSSEL_HOST=localhost
POSSEL_PORT=8080
BASE_URL="http://$POSSEL_HOST:$POSSEL_PORT"

USERNAME="racy_test_u"
PASSWORD="racy_test_p"

function post {
    curl -c $COOKIE_FILE -b $COOKIE_FILE -H "Content-Type: application/json" -X POST -d "$@"
}

function get {
    curl -b $COOKIE_FILE "$@"
}

function setUp {
    rm -f $DATABASE_FILE $COOKIE_FILE
    python -m possel.auth -d $DATABASE $USERNAME $PASSWORD;
    possel -D -p $POSSEL_PORT -d $DATABASE --log-database &  # Fork here
    until nc -z $POSSEL_HOST $POSSEL_PORT
    do
        sleep 0.1;
    done
    POSSEL_PROCESS=$!
}

function tearDown {
    rm -f $DATABASE_FILE $COOKIE_FILE
    kill -9 $POSSEL_PROCESS
}

setUp

echo "================================================"
echo "POST /session"
post "{\"username\":\"$USERNAME\", \"password\":\"$PASSWORD\"}" $BASE_URL/session;
sleep 1
post "{\"username\":\"$USERNAME\", \"password\":\"$PASSWORD\"}" $BASE_URL/session;
get $BASE_URL/server/all;
get $BASE_URL/buffer/all;
get $BASE_URL/user/all;

tearDown
