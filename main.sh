#!/usr/bin/env bash

set -ex

gcc -g -I$(pwd)/install/include -I$(pwd)/install/lib -llua -ldl -lm -o test.out test.c $(pwd)/install/lib/liblua.a
