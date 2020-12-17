
local co = coroutine.create(
   function()
      coroutine.yield(10)
   end
)


local r, v = coroutine.resume(co)

print(r, v)

