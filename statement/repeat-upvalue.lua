-- upval in repeat

repeat
   local i = 0

   local function f()
      i = 10
   end
until i

