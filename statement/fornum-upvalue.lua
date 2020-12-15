-- upval in for num

local a = 0

for i = 1, 10, 2 do
   local function f()
      return i
   end
end

