-- vararg A B
-- R(A), R(A+1), ..., R(A+B-1) = vararg

local a, b, c = ...

--[[
function f(...)
   local a, b, c = ...
end
--]]


--[[
local a
a(...)
--]]


--[[
local a = {...}
--]]

--[[
return ...
--]]
