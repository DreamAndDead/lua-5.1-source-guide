set script-extension soft
set pagination off
set print pretty on
set print array on



source helper.py

break ifstat

run statement/ifelseif.lua

