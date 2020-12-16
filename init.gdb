set script-extension soft
set pagination off
set print pretty on
set print array on


source luagdb.gdb

source helper.py

tb luaV_execute

r

