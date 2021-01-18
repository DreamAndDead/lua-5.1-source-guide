#include <stdio.h>                        

#include <lua.h>
#include <lualib.h>
#include <lauxlib.h>

int main(int argc, char* argv[])
{
    char* file = NULL;
    file = argv[1];

    lua_State* L = luaL_newstate();

    luaL_openlibs(L);

    int res = luaL_dofile(L, file);

    lua_getfield(L, LUA_GLOBALSINDEX, "foo");

    lua_pushinteger(L, 1);
    lua_pushinteger(L, 2);
    lua_pushinteger(L, 3);

    lua_call(L, 3, 2);

    lua_Number avg = lua_tonumber(L, -2);
    lua_Number sum = lua_tonumber(L, -1);
    
    printf("%d %d\n", (int)avg, (int)sum);

    return 0;
}

