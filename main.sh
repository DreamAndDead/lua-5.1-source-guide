#!/usr/bin/env bash

g++ -g -I$(pwd)/install/include -I$(pwd)/install/lib -llua -ldl -lm -o test.out test/test.cpp $(pwd)/install/lib/liblua.a
