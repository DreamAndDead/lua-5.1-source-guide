-- getupval A B
-- R(A) := UpValue[B]

local a

local function f()
   local b = a
end

f()
