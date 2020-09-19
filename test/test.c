#include <stdio.h>                        

#include <lua.h>
#include <lualib.h>
#include <lauxlib.h>

int main(int argc, char* argv[])
{
    char* file = NULL;
    file = argv[1];
    printf("loaded file=%s\n", argv[1]);

    lua_State* L = luaL_newstate();

    luaL_openlibs(L);
    luaL_dofile(L, file);

    return 0;
}

