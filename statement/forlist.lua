-- for list stat

local a, t = 0, {1, 2, 3}
local g, s = pairs(t)

for k, v in g, s, nil do
   a = a + 1
end

