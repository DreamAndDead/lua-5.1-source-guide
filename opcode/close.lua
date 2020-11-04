-- close A
-- close all var in stack up to (>=) R(A)

do
   local a, b
   f = function()
      return a, b
   end
end
