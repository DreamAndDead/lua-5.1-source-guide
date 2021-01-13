-- upvalue

local a

local function f()
   local b

   local function g()
      b = 20
      a = 10
   end
end

