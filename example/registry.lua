local ins = dofile "../tool/inspect.lua"

local t = debug.getregistry()

print(ins(t))

