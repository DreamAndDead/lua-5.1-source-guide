-- tforloop A C
--[[
R(A+3), ..., R(A+2+C) := R(A)( R(A+1), R(A+2) )
if R(A+3) ~= nil then {
  R(A+2) = R(A+3)
} else {
  PC++  
}
--]]

for i, v in pairs(t) do
   print(i, v)
end
