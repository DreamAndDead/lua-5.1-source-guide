-- function upval

local a = 0

local function f()
   local b = 1

   local function g()
      local c = a + b
   end
end
