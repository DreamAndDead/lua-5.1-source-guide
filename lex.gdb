set pagination off

b luaX_next
commands
  silent
  printf "%-4d%-10s", ls->linenumber, luaX_token2str(ls, ls->t.token)

  if ls->t.token == TK_NAME
    printf "%s", getstr(ls->t.seminfo.ts)
  end

  if ls->t.token == TK_NUMBER
    printf "%g", ls->t.seminfo.r
  end
  
  printf "\n"

  continue
end

r
