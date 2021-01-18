function foo(...)
   local sum = 0
   local n = 0
   
   for _, v in ipairs({...}) do
      sum = sum + v
      n = n + 1
   end

   return sum / n, sum
end
