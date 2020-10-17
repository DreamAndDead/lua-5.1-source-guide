-- tokenize lua code and output token

local lex = require './lexer'

local function read_file(path)
    local file = io.open(path, "r")
    if not file then return nil end
    local content = file:read "*a" -- *a or *all reads the whole file
    file:close()
    return content
end

local code = read_file(arg[1])

local lines = lex(code)

function print_token(token)
   local f = "{%s %s} "

   local s = string.format(f,
			   token['type'],
			   token['data'])

   io.write(s)
end


for i, line in ipairs(lines) do
   io.write(string.format("%d: ", i))
   
   for _, token in ipairs(line) do
      print_token(token)
   end

   print()
end


