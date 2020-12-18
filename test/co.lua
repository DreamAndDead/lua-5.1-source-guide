
local co = coroutine.create(
   function()
      -- coroutine.yield(9)
      return 9
   end
)


local r, v = coroutine.resume(co)

print(r, v)

local r, v = coroutine.resume(co)

print(r, v)

