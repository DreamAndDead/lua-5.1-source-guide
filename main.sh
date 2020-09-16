#!/usr/bin/env bash


usage() {
    echo "$0"
}

usage

pushd lua-5.1.5/

make linux

popd
