
local co = coroutine.create(
   function()
      function a()
	 function b()
	    coroutine.yield(10)
	 end
	 b()
      end
      a()
   end
)


local r, v = coroutine.resume(co)

print(r, v)
