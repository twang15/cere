#!/bin/bash

ROOT="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

TSTATUS=0

echo "Run memory dump tests"
# memory dump tests
$ROOT/src/memory_dump/test.sh
GOTSTATUS="$?"
if [ "$GOTSTATUS" != "0" ] ; then
    TSTATUS=1
fi

echo "Run loop instrumentation tests"
# memory dump and load tests
cd $ROOT/tests/test_03/
./test.sh
cd $ROOT
GOTSTATUS="$?"
if [ "$GOTSTATUS" != "0" ] ; then
    TSTATUS=1
fi

exit $TSTATUS

