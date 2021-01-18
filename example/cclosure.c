#include <stdio.h>                        

#include <lua.h>
#include <lualib.h>
#include <lauxlib.h>

static int foo (lua_State *L) {
  int n = lua_gettop(L);    /* number of arguments */
  lua_Number sum = 0;
  int i;
  for (i = 1; i <= n; i++) {
    if (!lua_isnumber(L, i)) {
      lua_pushstring(L, "incorrect argument");
      lua_error(L);
    }
    sum += lua_tonumber(L, i);
  }
  lua_pushnumber(L, sum/n);        /* first result */
  lua_pushnumber(L, sum);         /* second result */
  return 2;                   /* number of results */
}

int main(int argc, char* argv[])
{
    char* file = NULL;
    file = argv[1];

    lua_State* L = luaL_newstate();

    luaL_openlibs(L);

    lua_pushcfunction(L, foo);

    lua_setfield(L, LUA_GLOBALSINDEX, "foo");
    
    luaL_dofile(L, file);

    return 0;
}

