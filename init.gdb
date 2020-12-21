set script-extension soft
set pagination off
set print pretty on
set print array on


source tool/lua-gdb-helper/luagdb.txt
source helper.py

tb chunk

r

