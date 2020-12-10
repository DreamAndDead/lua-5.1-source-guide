-- upvalue

local a = 0

function outer()
   local b = 1

   local function inner()
      a = a + 1
      b = b + 1
      return a + b
   end

   return inner
end

f = outer()
