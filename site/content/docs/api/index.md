---
title: "c api"
author: ["DreamAndDead"]
date: 2021-01-15T17:48:00+08:00
lastmod: 2021-02-23T13:22:03+08:00
draft: false
---

Lua 的一个杰出的特性是，非常易于与 C 程序集成。

一个原因是 Lua 本身是用 C 语言实现的，
另一个原因则是 Lua 内部在 vm 层面设计提供了相应的 api。


## design {#design}

从之前的视角来看，代码编译为 Proto，vm 开启线程，封装为 Closure 并按指令执行。

从另一个角度来看 Lua 代码的运行过程。

如果反过来看，vm 本身是静态不动的，程序的运行由输入的 Proto 而驱动。
之所以产生这样的视角，是因为 vm 必须有指令输入，告诉其应该执行什么，
否则 vm 本身也只是空转而已。

api 层提供的功能就是如此，控制 vm 应该如何执行。

如此来看，Lua 代码和 api 都是在操作 `lua_State` ，vm 的运行时状态。
只不过一个是编译为 opcode 由 vm 主动执行，一个是通过 c 函数接口来直接控制。

{{< figure src="api-design.png" >}}

值得注意的时，api 不仅提供与语言外部使用，也在内部发挥着重要作用。

api 在外部使用，可以将 Lua 作为 C lib 来使用；
同时 api 在内部，实现了诸多 Lua 语言标准库的功能。


## stack {#stack}

说到 vm 运行时状态，最重要的部分就是栈。

实际上，几乎全部 api 都是对栈的操作。

{{< highlight C "linenos=table, linenostart=107" >}}
/*
** state manipulation
*/
LUA_API lua_State *(lua_newstate) (lua_Alloc f, void *ud);
LUA_API void       (lua_close) (lua_State *L);
LUA_API lua_State *(lua_newthread) (lua_State *L);

LUA_API lua_CFunction (lua_atpanic) (lua_State *L, lua_CFunction panicf);


/*
** basic stack manipulation
*/
LUA_API int   (lua_gettop) (lua_State *L);
LUA_API void  (lua_settop) (lua_State *L, int idx);
LUA_API void  (lua_pushvalue) (lua_State *L, int idx);
LUA_API void  (lua_remove) (lua_State *L, int idx);
LUA_API void  (lua_insert) (lua_State *L, int idx);
LUA_API void  (lua_replace) (lua_State *L, int idx);
LUA_API int   (lua_checkstack) (lua_State *L, int sz);

LUA_API void  (lua_xmove) (lua_State *from, lua_State *to, int n);


/*
** access functions (stack -> C)
*/

LUA_API int             (lua_isnumber) (lua_State *L, int idx);
LUA_API int             (lua_isstring) (lua_State *L, int idx);
LUA_API int             (lua_iscfunction) (lua_State *L, int idx);
LUA_API int             (lua_isuserdata) (lua_State *L, int idx);
LUA_API int             (lua_type) (lua_State *L, int idx);
LUA_API const char     *(lua_typename) (lua_State *L, int tp);

LUA_API int            (lua_equal) (lua_State *L, int idx1, int idx2);
LUA_API int            (lua_rawequal) (lua_State *L, int idx1, int idx2);
LUA_API int            (lua_lessthan) (lua_State *L, int idx1, int idx2);

LUA_API lua_Number      (lua_tonumber) (lua_State *L, int idx);
LUA_API lua_Integer     (lua_tointeger) (lua_State *L, int idx);
LUA_API int             (lua_toboolean) (lua_State *L, int idx);
LUA_API const char     *(lua_tolstring) (lua_State *L, int idx, size_t *len);
LUA_API size_t          (lua_objlen) (lua_State *L, int idx);
LUA_API lua_CFunction   (lua_tocfunction) (lua_State *L, int idx);
LUA_API void	       *(lua_touserdata) (lua_State *L, int idx);
LUA_API lua_State      *(lua_tothread) (lua_State *L, int idx);
LUA_API const void     *(lua_topointer) (lua_State *L, int idx);


/*
** push functions (C -> stack)
*/
LUA_API void  (lua_pushnil) (lua_State *L);
LUA_API void  (lua_pushnumber) (lua_State *L, lua_Number n);
LUA_API void  (lua_pushinteger) (lua_State *L, lua_Integer n);
LUA_API void  (lua_pushlstring) (lua_State *L, const char *s, size_t l);
LUA_API void  (lua_pushstring) (lua_State *L, const char *s);
LUA_API const char *(lua_pushvfstring) (lua_State *L, const char *fmt,
						      va_list argp);
LUA_API const char *(lua_pushfstring) (lua_State *L, const char *fmt, ...);
LUA_API void  (lua_pushcclosure) (lua_State *L, lua_CFunction fn, int n);
LUA_API void  (lua_pushboolean) (lua_State *L, int b);
LUA_API void  (lua_pushlightuserdata) (lua_State *L, void *p);
LUA_API int   (lua_pushthread) (lua_State *L);


/*
** get functions (Lua -> stack)
*/
LUA_API void  (lua_gettable) (lua_State *L, int idx);
LUA_API void  (lua_getfield) (lua_State *L, int idx, const char *k);
LUA_API void  (lua_rawget) (lua_State *L, int idx);
LUA_API void  (lua_rawgeti) (lua_State *L, int idx, int n);
LUA_API void  (lua_createtable) (lua_State *L, int narr, int nrec);
LUA_API void *(lua_newuserdata) (lua_State *L, size_t sz);
LUA_API int   (lua_getmetatable) (lua_State *L, int objindex);
LUA_API void  (lua_getfenv) (lua_State *L, int idx);


/*
** set functions (stack -> Lua)
*/
LUA_API void  (lua_settable) (lua_State *L, int idx);
LUA_API void  (lua_setfield) (lua_State *L, int idx, const char *k);
LUA_API void  (lua_rawset) (lua_State *L, int idx);
LUA_API void  (lua_rawseti) (lua_State *L, int idx, int n);
LUA_API int   (lua_setmetatable) (lua_State *L, int objindex);
LUA_API int   (lua_setfenv) (lua_State *L, int idx);


/*
** `load' and `call' functions (load and run Lua code)
*/
LUA_API void  (lua_call) (lua_State *L, int nargs, int nresults);
LUA_API int   (lua_pcall) (lua_State *L, int nargs, int nresults, int errfunc);
LUA_API int   (lua_cpcall) (lua_State *L, lua_CFunction func, void *ud);
LUA_API int   (lua_load) (lua_State *L, lua_Reader reader, void *dt,
					const char *chunkname);

LUA_API int (lua_dump) (lua_State *L, lua_Writer writer, void *data);


/*
** coroutine functions
*/
LUA_API int  (lua_yield) (lua_State *L, int nresults);
LUA_API int  (lua_resume) (lua_State *L, int narg);
LUA_API int  (lua_status) (lua_State *L);
{{< /highlight >}}


<div class="src-block-caption">
  <span class="src-block-number">Code Snippet 1</span>:
  lua.h
</div>

在官方文档[^fn:1]中，有对所有 api 功能的绝佳描述。

结合之前 opcode 的实现过程以及一些基本的栈操作理解，相应的 api 实现并不难理解。

其中值得注意的是栈的索引。

在对栈进行操作之前，必须先索引到其中的元素。

api 内部使用一种自定义的映射关系，将整数映射到元素的栈位置。

{{< highlight C "linenos=table, linenostart=49" >}}
static TValue *index2adr (lua_State *L, int idx) {
  if (idx > 0) {
    TValue *o = L->base + (idx - 1);
    api_check(L, idx <= L->ci->top - L->base);
    if (o >= L->top) return cast(TValue *, luaO_nilobject);
    else return o;
  }
  else if (idx > LUA_REGISTRYINDEX) {
    api_check(L, idx != 0 && -idx <= L->top - L->base);
    return L->top + idx;
  }
  else switch (idx) {  /* pseudo-indices */
    case LUA_REGISTRYINDEX: return registry(L);
    case LUA_ENVIRONINDEX: {
      Closure *func = curr_func(L);
      sethvalue(L, &L->env, func->c.env);
      return &L->env;
    }
    case LUA_GLOBALSINDEX: return gt(L);
    default: {
      Closure *func = curr_func(L);
      idx = LUA_GLOBALSINDEX - idx;
      return (idx <= func->c.nupvalues)
		? &func->c.upvalue[idx-1]
		: cast(TValue *, luaO_nilobject);
    }
  }
}
{{< /highlight >}}


<div class="src-block-caption">
  <span class="src-block-number">Code Snippet 2</span>:
  lapi.c
</div>

{{< figure src="api-index2addr.png" >}}

其中 `L->base` 和 `L->top` 标识了栈底和栈顶。

正整数索引从 1 开始，索引 1 指向 `L->base` ，递增向上。

负整数索引从 -1 开始，索引 `L->top` 之下的元素，递减向下。

0 不作为索引来使用。

在上面的规则之外，api 内部使用几个特别定义的索引值，

{{< highlight C "linenos=table, linenostart=33" >}}
/*
** pseudo-indices
*/
#define LUA_REGISTRYINDEX	(-10000)
#define LUA_ENVIRONINDEX	(-10001)
#define LUA_GLOBALSINDEX	(-10002)
#define lua_upvalueindex(i)	(LUA_GLOBALSINDEX-(i))
{{< /highlight >}}


<div class="src-block-caption">
  <span class="src-block-number">Code Snippet 3</span>:
  lua.h
</div>

-   `LUA_REGISTRYINDEX` 索引全局状态的 `l_registry`
-   `LUA_ENVIRONINDEX` 索引当前 closure 的环境
-   `LUA_GLOBALSINDEX` 索引当前 `lua_State` 的全局表
-   更小的负数，依次索引当前 closure 的 upvalue


## c closure {#c-closure}

在 vm 章节提到过，closure 有两种类型，CClosure 和 LClosure。

LClosure 即从 Lua 代码编译得到的函数，而 CClosure 是通过 C api 实现的函数。

因为 CClosure 要和 Lua 交互，所以要遵循一定的约定[^fn:2]。

首先，CClosure 在 C 语言中需要定义为 `lua_CFunction` 类型，

{{< highlight C "linenos=table, linenostart=52" >}}
typedef int (*lua_CFunction) (lua_State *L);
{{< /highlight >}}


<div class="src-block-caption">
  <span class="src-block-number">Code Snippet 4</span>:
  lua.h
</div>

其中，在调用时，从 base 到 top 都是 CClosure 的参数，

最终，将返回值按顺序压栈，并返回参数个数。

这个传参，调用，返回值的约定和 vm 内部解析 LClosure 是一样的。

官方文档[^fn:2]提供了一段示例代码，

```C
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
```

```lua
avg, sum = foo(1, 2, 3)

print(avg, sum)
```

通过

```text
$ make -s example
```

可以编译运行上述示例。

其中先注册了 CClosure 为全局变量 foo，再在 lua 代码中调用，
打印出所有参数的平均值和总和。

其中栈的变化情况如下，

{{< figure src="api-closure-call.png" >}}


## practice {#practice}

在 `example/` 目录下，实现了两种 foo 的实现方式。

cclosure 小节在 C 语言层面，定义 foo 并注册到全局表中，而在 Lua 层面调用；
`example/lclosure.c` `example/lclosure.lua` 将 foo 在 Lua 代码中定义为全局变量，
而在 C 语言层面调用。

读者可通过

```text
$ make -s example
```

来对比这两种协同方式。

| 章节涉及文件 | 建议了解程度 |
|--------|--------|
| lua.h  | ★ ★ ★ ★ ★ |
| lapi.h | ★ ☆ ☆ ☆ ☆ |
| lapi.c | ★ ★ ★ ★ ★ |

[^fn:1]: : <http://www.lua.org/manual/5.1/manual.html#3>
[^fn:2]: : <http://www.lua.org/manual/5.1/manual.html#lua%5FCFunction>
