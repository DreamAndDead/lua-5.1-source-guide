--

local u = 1

function foo()
   local v = 2
   function bar()
      local w = 3
      print(u, v, w)
   end

   bar()
end

foo()
