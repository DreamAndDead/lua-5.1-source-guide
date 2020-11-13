-- upvalue

local a = 0

function outer()
   local b = 1

   function inner()
      local c = a + b
   end
end
