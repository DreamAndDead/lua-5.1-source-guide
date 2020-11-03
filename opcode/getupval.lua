-- getupval A B
-- R(A) := UpValue[B]

-- upvalue list is internal to vm?

local a

function f()
   local b = a
end
