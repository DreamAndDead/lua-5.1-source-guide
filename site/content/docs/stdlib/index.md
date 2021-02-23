---
title: "std lib"
author: ["DreamAndDead"]
date: 2021-01-18T16:08:00+08:00
lastmod: 2021-02-23T13:23:50+08:00
draft: false
---

在 lex 章节提到，require next 之类不是关键字而是函数，
在 api 章节提到 api 也用于内部作用，
它们描述的都是 lua 标准库。

本章节就来讲解 lua 内部是如何处理标准库的。


## register {#register}

标准库可以说是多种功能函数的集合，在被使用之前，必须先被注册。

{{< highlight C "linenos=table, linenostart=18" >}}
#define LUA_COLIBNAME	"coroutine"
LUALIB_API int (luaopen_base) (lua_State *L);

#define LUA_TABLIBNAME	"table"
LUALIB_API int (luaopen_table) (lua_State *L);

#define LUA_IOLIBNAME	"io"
LUALIB_API int (luaopen_io) (lua_State *L);

#define LUA_OSLIBNAME	"os"
LUALIB_API int (luaopen_os) (lua_State *L);

#define LUA_STRLIBNAME	"string"
LUALIB_API int (luaopen_string) (lua_State *L);

#define LUA_MATHLIBNAME	"math"
LUALIB_API int (luaopen_math) (lua_State *L);

#define LUA_DBLIBNAME	"debug"
LUALIB_API int (luaopen_debug) (lua_State *L);

#define LUA_LOADLIBNAME	"package"
LUALIB_API int (luaopen_package) (lua_State *L);


/* open all previous libraries */
LUALIB_API void (luaL_openlibs) (lua_State *L);
{{< /highlight >}}


<div class="src-block-caption">
  <span class="src-block-number">Code Snippet 1</span>:
  lualib.h
</div>

{{< highlight C "linenos=table, linenostart=35" >}}
typedef struct luaL_Reg {
  const char *name;
  lua_CFunction func;
} luaL_Reg;
{{< /highlight >}}


<div class="src-block-caption">
  <span class="src-block-number">Code Snippet 2</span>:
  lauxlib.h
</div>

{{< highlight C "linenos=table, linenostart=17" >}}
static const luaL_Reg lualibs[] = {
  {"", luaopen_base},
  {LUA_LOADLIBNAME, luaopen_package},
  {LUA_TABLIBNAME, luaopen_table},
  {LUA_IOLIBNAME, luaopen_io},
  {LUA_OSLIBNAME, luaopen_os},
  {LUA_STRLIBNAME, luaopen_string},
  {LUA_MATHLIBNAME, luaopen_math},
  {LUA_DBLIBNAME, luaopen_debug},
  {NULL, NULL}
};


LUALIB_API void luaL_openlibs (lua_State *L) {
  const luaL_Reg *lib = lualibs;
  for (; lib->func; lib++) {
    lua_pushcfunction(L, lib->func);
    lua_pushstring(L, lib->name);
    lua_call(L, 1, 0);
  }
}
{{< /highlight >}}


<div class="src-block-caption">
  <span class="src-block-number">Code Snippet 3</span>:
  linit.c
</div>

各个模块实现了各自的功能，分别注册到不同的模块名中。

| file       | module      |
|------------|-------------|
| lbaselib.c | (coroutine) |
| lmathlib.c | math        |
| lstrlib.c  | string      |
| ltablib.c  | table       |
| liolib.c   | io          |
| loslib.c   | os          |
| ldblib.c   | debug       |
| loadlib.c  | package     |

同时每个模块各自实现注册方法，由 `luaL_openlibs` 统一调用。

{{< highlight C "linenos=table, linenostart=229" >}}
LUALIB_API void (luaL_register) (lua_State *L, const char *libname,
				const luaL_Reg *l) {
  luaI_openlib(L, libname, l, 0);
}


static int libsize (const luaL_Reg *l) {
  int size = 0;
  for (; l->name; l++) size++;
  return size;
}


LUALIB_API void luaI_openlib (lua_State *L, const char *libname,
			      const luaL_Reg *l, int nup) {
  if (libname) {
    int size = libsize(l);
    /* check whether lib already exists */
    luaL_findtable(L, LUA_REGISTRYINDEX, "_LOADED", 1);
    lua_getfield(L, -1, libname);  /* get _LOADED[libname] */
    if (!lua_istable(L, -1)) {  /* not found? */
      lua_pop(L, 1);  /* remove previous result */
      /* try global variable (and create one if it does not exist) */
      if (luaL_findtable(L, LUA_GLOBALSINDEX, libname, size) != NULL)
	luaL_error(L, "name conflict for module " LUA_QS, libname);
      lua_pushvalue(L, -1);
      lua_setfield(L, -3, libname);  /* _LOADED[libname] = new table */
    }
    lua_remove(L, -2);  /* remove _LOADED table */
    lua_insert(L, -(nup+1));  /* move library table to below upvalues */
  }
  for (; l->name; l++) {
    int i;
    for (i=0; i<nup; i++)  /* copy upvalues to the top */
      lua_pushvalue(L, -nup);
    lua_pushcclosure(L, l->func, nup);
    lua_setfield(L, -(nup+2), l->name);
  }
  lua_pop(L, nup);  /* remove upvalues */
}
{{< /highlight >}}


<div class="src-block-caption">
  <span class="src-block-number">Code Snippet 4</span>:
  lauxlib.c
</div>

首先进行注册的是全局方法和 coroutine 模块，

{{< highlight C "linenos=table, linenostart=626" >}}
static void base_open (lua_State *L) {
  /* set global _G */
  lua_pushvalue(L, LUA_GLOBALSINDEX);
  lua_setglobal(L, "_G");
  /* open lib into global table */
  luaL_register(L, "_G", base_funcs);
  lua_pushliteral(L, LUA_VERSION);
  lua_setglobal(L, "_VERSION");  /* set global _VERSION */
  /* `ipairs' and `pairs' need auxiliary functions as upvalues */
  auxopen(L, "ipairs", luaB_ipairs, ipairsaux);
  auxopen(L, "pairs", luaB_pairs, luaB_next);
  /* `newproxy' needs a weaktable as upvalue */
  lua_createtable(L, 0, 1);  /* new table `w' */
  lua_pushvalue(L, -1);  /* `w' will be its own metatable */
  lua_setmetatable(L, -2);
  lua_pushliteral(L, "kv");
  lua_setfield(L, -2, "__mode");  /* metatable(w).__mode = "kv" */
  lua_pushcclosure(L, luaB_newproxy, 1);
  lua_setglobal(L, "newproxy");  /* set global `newproxy' */
}


LUALIB_API int luaopen_base (lua_State *L) {
  base_open(L);
  luaL_register(L, LUA_COLIBNAME, co_funcs);
  return 2;
}
{{< /highlight >}}


<div class="src-block-caption">
  <span class="src-block-number">Code Snippet 5</span>:
  lbaselib.c
</div>

line 628 629 在全局表中添加 \_G，指向全局表自身。

line 631 `luaL_register(L, "_G", base_funcs);` 将全局函数注册到 \_G 中。

在注册过程中，在 REGISTRY 表中使用 \_LOADED 记录相应注册的项，避免注册时出现重复冲突。
同时将相应的注册项添加到全局表中。

最终全部模块注册后，REGISTRY 表的内容大致如下，其中 \_LOADED.\_G 引用的正是全局表，

```lua
registry = {
   _LOADED = {
      _G = {
	 _G = {
	    -- ...
	 },
	 assert = ...,
	 dofile = ...,
	 --...
	 --...
	 coroutine = {
	    --...
	    --...
	 },
	 math = {
	    --...
	    --...
	 },
	 --...
      },
      coroutine = {
	 --...
	 --...
      },
      math = {
	 --...
	 --...
      },
      --...
   }
}
```

可通过

```text
$ make -s registry
```

来查看更具体的 REGISTRY 内容。


## module {#module}

base 模块注册了所有基础全局函数，

{{< highlight C "linenos=table, linenostart=447" >}}
static const luaL_Reg base_funcs[] = {
  {"assert", luaB_assert},
  {"collectgarbage", luaB_collectgarbage},
  {"dofile", luaB_dofile},
  {"error", luaB_error},
  {"gcinfo", luaB_gcinfo},
  {"getfenv", luaB_getfenv},
  {"getmetatable", luaB_getmetatable},
  {"loadfile", luaB_loadfile},
  {"load", luaB_load},
  {"loadstring", luaB_loadstring},
  {"next", luaB_next},
  {"pcall", luaB_pcall},
  {"print", luaB_print},
  {"rawequal", luaB_rawequal},
  {"rawget", luaB_rawget},
  {"rawset", luaB_rawset},
  {"select", luaB_select},
  {"setfenv", luaB_setfenv},
  {"setmetatable", luaB_setmetatable},
  {"tonumber", luaB_tonumber},
  {"tostring", luaB_tostring},
  {"type", luaB_type},
  {"unpack", luaB_unpack},
  {"xpcall", luaB_xpcall},
  {NULL, NULL}
};
{{< /highlight >}}


<div class="src-block-caption">
  <span class="src-block-number">Code Snippet 6</span>:
  lbaselib.c
</div>

其中每个函数都对应一个 C 函数实现，函数使用 api 接口与 Lua 进行数据交互，
然后将函数注册到 Lua 的全局表中，在运行 Lua 代码时就可以平滑调用。
正如 api 章节所述，这即是 api 在内部实现发挥的作用。

其它模块的注册过程与之类似，读者可结合官方文档[^fn:1]针对相应的方法进行了解。


## coroutine {#coroutine}

一个出人意料的点在于，协程是用 api 来实现的，而不是内建在 vm 中。

coroutine 模块一并在 baselib 中注册，

{{< highlight C "linenos=table, linenostart=605" >}}
static const luaL_Reg co_funcs[] = {
  {"create", luaB_cocreate},
  {"resume", luaB_coresume},
  {"running", luaB_corunning},
  {"status", luaB_costatus},
  {"wrap", luaB_cowrap},
  {"yield", luaB_yield},
  {NULL, NULL}
};
{{< /highlight >}}


<div class="src-block-caption">
  <span class="src-block-number">Code Snippet 7</span>:
  lbaselib.c
</div>

其中的方法，正是在 lua 代码中使用的 coroutine.\* 方法。


### create {#create}

至此，我们已经了解了 8 种基础类型的 7 种，余下的 thread 类型，正是协程。
而并不意外的，协程本身正是 `lua_State` 。

`lua_State` 记录了所有 lua 代码运行时的状态，协程可理解为是 vm 另外运行的一块 lua 代码，
所以用 `lua_State` 来表示。

从操作系统层面而言，lua 解释器是一个单线程程序。
lua 实现的协程，虽然在内部声明类型为 thread，但是本质上，
只是多个不同的 `lua_State` 交替控制权在轮换执行。

也就是说，协程是异步并发的，而不是并行的。

{{< figure src="stdlib-thread.png" >}}

lua 内部默认存在“主线程” main thread，就是多次出现在代码中的 `lua_State *L` 。

主线程可创建出新的协程并通过 resume 执行，此时主线程失去控制权；
协程通过 yield 放弃控制权，回到主线程调用时；
主线程可通过 resume 重新进入协程的中断点，继续执行。

{{< highlight C "linenos=table, linenostart=576" >}}
static int luaB_cocreate (lua_State *L) {
  lua_State *NL = lua_newthread(L);
  luaL_argcheck(L, lua_isfunction(L, 1) && !lua_iscfunction(L, 1), 1,
    "Lua function expected");
  lua_pushvalue(L, 1);  /* move function to top */
  lua_xmove(L, NL, 1);  /* move function from L to NL */
  return 1;
}
{{< /highlight >}}


<div class="src-block-caption">
  <span class="src-block-number">Code Snippet 8</span>:
  lbaselib.c
</div>

{{< figure src="stdlib-create.png" >}}

lua 内部通过 coroutine.create(f) 来创建协程，在主线程 L 的栈底即存在 `luaB_cocreate` 和 f，
通过 `lua_newthead` 创建协程 NL（即 `lua_State` ）并入栈，再将 f 复制到栈顶，
并通过 xmove 移动到 NL 的栈中，作为起始调用函数，最终返回 NL。

`lua_newthead` 最终调用了 `luaE_newthread` ，

{{< highlight C "linenos=table, linenostart=119" >}}
lua_State *luaE_newthread (lua_State *L) {
  lua_State *L1 = tostate(luaM_malloc(L, state_size(lua_State)));
  luaC_link(L, obj2gco(L1), LUA_TTHREAD);
  preinit_state(L1, G(L));
  stack_init(L1, L);  /* init stack */
  setobj2n(L, gt(L1), gt(L));  /* share table of globals */
  L1->hookmask = L->hookmask;
  L1->basehookcount = L->basehookcount;
  L1->hook = L->hook;
  resethookcount(L1);
  lua_assert(iswhite(obj2gco(L1)));
  return L1;
}
{{< /highlight >}}


<div class="src-block-caption">
  <span class="src-block-number">Code Snippet 9</span>:
  lstate.c
</div>

在 line 124 表明，协程是共享全局表的，即在协程中修改全局变量是相互影响的。


### resume & yield {#resume-and-yield}

resume 函数开始执行/恢复协程的运行，第一个参数为协程本身，后续参数为传递入协程的参数，

{{< highlight C "linenos=table, linenostart=518" >}}
static int auxresume (lua_State *L, lua_State *co, int narg) {
  int status = costatus(L, co);
  if (!lua_checkstack(co, narg))
    luaL_error(L, "too many arguments to resume");
  if (status != CO_SUS) {
    lua_pushfstring(L, "cannot resume %s coroutine", statnames[status]);
    return -1;  /* error flag */
  }
  lua_xmove(L, co, narg);
  lua_setlevel(L, co);
  status = lua_resume(co, narg);
  if (status == 0 || status == LUA_YIELD) {
    int nres = lua_gettop(co);
    if (!lua_checkstack(L, nres + 1))
      luaL_error(L, "too many results to resume");
    lua_xmove(co, L, nres);  /* move yielded values */
    return nres;
  }
  else {
    lua_xmove(co, L, 1);  /* move error message */
    return -1;  /* error flag */
  }
}


static int luaB_coresume (lua_State *L) {
  lua_State *co = lua_tothread(L, 1);
  int r;
  luaL_argcheck(L, co, 1, "coroutine expected");
  r = auxresume(L, co, lua_gettop(L) - 1);
  if (r < 0) {
    lua_pushboolean(L, 0);
    lua_insert(L, -2);
    return 2;  /* return false + error message */
  }
  else {
    lua_pushboolean(L, 1);
    lua_insert(L, -(r + 1));
    return r + 1;  /* return true + `resume' returns */
  }
}
{{< /highlight >}}


<div class="src-block-caption">
  <span class="src-block-number">Code Snippet 10</span>:
  lbaselib.c
</div>

line 544 先找到协程，
line 526 再通过 xmove 将参数传递到相应的栈中，
line 528 恢复其执行，

{{< highlight C "linenos=table, linenostart=418" >}}
LUA_API int lua_resume (lua_State *L, int nargs) {
  int status;
  lua_lock(L);
  if (L->status != LUA_YIELD && (L->status != 0 || L->ci != L->base_ci))
      return resume_error(L, "cannot resume non-suspended coroutine");
  if (L->nCcalls >= LUAI_MAXCCALLS)
    return resume_error(L, "C stack overflow");
  luai_userstateresume(L, nargs);
  lua_assert(L->errfunc == 0);
  L->baseCcalls = ++L->nCcalls;
  status = luaD_rawrunprotected(L, resume, L->top - nargs);
  if (status != 0) {  /* error? */
    L->status = cast_byte(status);  /* mark thread as `dead' */
    luaD_seterrorobj(L, status, L->top);
    L->ci->top = L->top;
  }
  else {
    lua_assert(L->nCcalls == L->baseCcalls);
    status = L->status;
  }
  --L->nCcalls;
  lua_unlock(L);
  return status;
}
{{< /highlight >}}


<div class="src-block-caption">
  <span class="src-block-number">Code Snippet 11</span>:
  ldo.c
</div>

执行协程之后，最终返回其状态值。

line 529 判断状态为 yield 时，回收其栈上的返回值，通过 xmove 移动到 L 中。

与之相配合的，yield 函数则直接准备参数数量，重置 `lua_State` 的状态为 yield 即可。

{{< highlight C "linenos=table, linenostart=593" >}}
static int luaB_yield (lua_State *L) {
  return lua_yield(L, lua_gettop(L));
}
{{< /highlight >}}


<div class="src-block-caption">
  <span class="src-block-number">Code Snippet 12</span>:
  lbaselib.c
</div>

{{< highlight C "linenos=table, linenostart=444" >}}
LUA_API int lua_yield (lua_State *L, int nresults) {
  luai_userstateyield(L, nresults);
  lua_lock(L);
  if (L->nCcalls > L->baseCcalls)
    luaG_runerror(L, "attempt to yield across metamethod/C-call boundary");
  L->base = L->top - nresults;  /* protect stack slots below */
  L->status = LUA_YIELD;
  lua_unlock(L);
  return -1;
}
{{< /highlight >}}


<div class="src-block-caption">
  <span class="src-block-number">Code Snippet 13</span>:
  ldo.c
</div>

比如如下示例代码，

```lua
local co = coroutine.create(function(a, b, c)
      local d, e = coroutine.yield(a + b + c)
      return d + e
      end)

print(coroutine.resume(co, 1, 2, 3))
print(coroutine.resume(co, 4, 5))
print(coroutine.resume(co))
```

```text
true	6
true	9
false	cannot resume dead coroutine
```

第一次 resume 时，将参数传递入 NL，

{{< figure src="stdlib-resume.png" >}}

协程内部执行 yield，返回状态 `LUA_YIELD` ，resume 通过 xmove 将结果从栈回收至 L，
最终 resume 自己压栈 bool 值 true 并 insert 所有返回值，作为调用 resume 的返回值。

{{< figure src="stdlib-resume-return.png" >}}

第二次调用 resume 时，传递参数 4 5，在协程内部，从中断的地方继续执行，
4 5 作为 yield 调用的返回值，赋值与 d e。

{{< figure src="stdlib-resume-2.png" >}}

最终协程内部 return 执行结束，resume 执行相同的过程，回收栈上的返回值。

{{< figure src="stdlib-resume-return-2.png" >}}


### status {#status}

在 lua.h 中，定义线程状态有如下几种，

{{< highlight C "linenos=table, linenostart=42" >}}
/* thread status; 0 is OK */
#define LUA_YIELD	1
#define LUA_ERRRUN	2
#define LUA_ERRSYNTAX	3
#define LUA_ERRMEM	4
#define LUA_ERRERR	5
{{< /highlight >}}


<div class="src-block-caption">
  <span class="src-block-number">Code Snippet 14</span>:
  lua.h
</div>

在线程运行没有出错的情况下，对协程状态的检测会更加细致，

{{< highlight C "linenos=table, linenostart=482" >}}
#define CO_RUN	0	/* running */
#define CO_SUS	1	/* suspended */
#define CO_NOR	2	/* 'normal' (it resumed another coroutine) */
#define CO_DEAD	3

static const char *const statnames[] =
    {"running", "suspended", "normal", "dead"};

static int costatus (lua_State *L, lua_State *co) {
  if (L == co) return CO_RUN;
  switch (lua_status(co)) {
    case LUA_YIELD:
      return CO_SUS;
    case 0: {
      lua_Debug ar;
      if (lua_getstack(co, 0, &ar) > 0)  /* does it have frames? */
	return CO_NOR;  /* it is running */
      else if (lua_gettop(co) == 0)
	  return CO_DEAD;
      else
	return CO_SUS;  /* initial state */
    }
    default:  /* some error occured */
      return CO_DEAD;
  }
}


static int luaB_costatus (lua_State *L) {
  lua_State *co = lua_tothread(L, 1);
  luaL_argcheck(L, co, 1, "coroutine expected");
  lua_pushstring(L, statnames[costatus(L, co)]);
  return 1;
}
{{< /highlight >}}


<div class="src-block-caption">
  <span class="src-block-number">Code Snippet 15</span>:
  lbaselib.c
</div>

在调用 `luaB_costatus` 时要明确一点，正在调用的线程，正是拥有控制权而正在运行的线程。

`CO_RUN` 状态，对应于协程自身检测自身的状态，在检测的此刻必然是 running 状态。

```lua
local co = coroutine.create(function(co)
      print(coroutine.status(co))
end)

coroutine.resume(co, co)
```

```text
running
```

在协程刚刚新建/yield 之后，对应的状态为 `CO_SUS` 。

```lua
local co = coroutine.create(function()
      coroutine.yield()
end)

print(coroutine.status(co))
coroutine.resume(co)
print(coroutine.status(co))
```

```text
suspended
suspended
```

如果协程本身 resume 了其它协程，此刻检测其状态，对应 `CO_NOR` 。

```lua
local co = coroutine.create(function(co)
      local a = coroutine.create(function()
	    print(coroutine.status(co))
      end)

      coroutine.resume(a)
end)

coroutine.resume(co, co)
```

```text
normal
```

当协程执行结束/运行出错，状态都为 `CO_DEAD` 。

```lua
local co = coroutine.create(function()
      coroutine.yield()
end)

coroutine.resume(co)
coroutine.resume(co)
coroutine.resume(co)

print(coroutine.status(co))
```

```text
dead
```

需要注意的是，主线程是无法检测状态的，因为在 lua 代码层面根本没有相应的变量来对应其 `lua_State` 。


## debug {#debug}

标准库提供了 debug 库，在 lua 语言层面提供了接口，用于自省和设置钩子。

debug 库内部的实现可以印证之前所有的描述，这一章就来了解下 debug 库的相关实现。


### getinfo {#getinfo}

debug 库提供了如下函数，

{{< highlight C "linenos=table, linenostart=375" >}}
static const luaL_Reg dblib[] = {
  {"debug", db_debug},
  {"getfenv", db_getfenv},
  {"gethook", db_gethook},
  {"getinfo", db_getinfo},
  {"getlocal", db_getlocal},
  {"getregistry", db_getregistry},
  {"getmetatable", db_getmetatable},
  {"getupvalue", db_getupvalue},
  {"setfenv", db_setfenv},
  {"sethook", db_sethook},
  {"setlocal", db_setlocal},
  {"setmetatable", db_setmetatable},
  {"setupvalue", db_setupvalue},
  {"traceback", db_errorfb},
  {NULL, NULL}
};
{{< /highlight >}}


<div class="src-block-caption">
  <span class="src-block-number">Code Snippet 16</span>:
  ldblib.c
</div>

getinfo 用于运行时自省，可以得到很多运行时的信息。

根据官方文档[^fn:2]的描述，参数 thread 和 what 是可选的。

```text
debug.getinfo ([thread,] function [, what])
```

在实现中，

{{< highlight C "linenos=table, linenostart=76" >}}
static lua_State *getthread (lua_State *L, int *arg) {
  if (lua_isthread(L, 1)) {
    *arg = 1;
    return lua_tothread(L, 1);
  }
  else {
    *arg = 0;
    return L;
  }
}
{{< /highlight >}}


<div class="src-block-caption">
  <span class="src-block-number">Code Snippet 17</span>:
  ldblib.c
</div>

{{< highlight C "linenos=table, linenostart=99" >}}
static int db_getinfo (lua_State *L) {
  lua_Debug ar;
  int arg;
  lua_State *L1 = getthread(L, &arg);
  const char *options = luaL_optstring(L, arg+2, "flnSu");
  if (lua_isnumber(L, arg+1)) {
    if (!lua_getstack(L1, (int)lua_tointeger(L, arg+1), &ar)) {
      lua_pushnil(L);  /* level out of range */
      return 1;
    }
  }
  else if (lua_isfunction(L, arg+1)) {
    lua_pushfstring(L, ">%s", options);
    options = lua_tostring(L, -1);
    lua_pushvalue(L, arg+1);
    lua_xmove(L, L1, 1);
  }
  else
    return luaL_argerror(L, arg+1, "function or level expected");
  if (!lua_getinfo(L1, options, &ar))
    return luaL_argerror(L, arg+2, "invalid option");
  lua_createtable(L, 0, 2);
  if (strchr(options, 'S')) {
    settabss(L, "source", ar.source);
    settabss(L, "short_src", ar.short_src);
    settabsi(L, "linedefined", ar.linedefined);
    settabsi(L, "lastlinedefined", ar.lastlinedefined);
    settabss(L, "what", ar.what);
  }
  if (strchr(options, 'l'))
    settabsi(L, "currentline", ar.currentline);
  if (strchr(options, 'u'))
    settabsi(L, "nups", ar.nups);
  if (strchr(options, 'n')) {
    settabss(L, "name", ar.name);
    settabss(L, "namewhat", ar.namewhat);
  }
  if (strchr(options, 'L'))
    treatstackoption(L, L1, "activelines");
  if (strchr(options, 'f'))
    treatstackoption(L, L1, "func");
  return 1;  /* return table */
}
{{< /highlight >}}


<div class="src-block-caption">
  <span class="src-block-number">Code Snippet 18</span>:
  ldblib.c
</div>

如果没有 thread，则从当前线程获取信息；如果没有 what，默认为 "flnSu"。

在 line 118 调用 `lua_getinfo` 来获取信息。

其中根据需要获取的信息的缩写，将所有信息存储到 `lua_Debug` 结构中返回。
不同的缩写对应不同的字段。

{{< highlight C "linenos=table, linenostart=346" >}}
struct lua_Debug {
  int event;
  const char *name;	/* (n) */
  const char *namewhat;	/* (n) `global', `local', `field', `method' */
  const char *what;	/* (S) `Lua', `C', `main', `tail' */
  const char *source;	/* (S) */
  int currentline;	/* (l) */
  int nups;		/* (u) number of upvalues */
  int linedefined;	/* (S) */
  int lastlinedefined;	/* (S) */
  char short_src[LUA_IDSIZE]; /* (S) */
  /* private part */
  int i_ci;  /* active function */
};
{{< /highlight >}}


<div class="src-block-caption">
  <span class="src-block-number">Code Snippet 19</span>:
  lua.h
</div>

在 `lua_getinfo` 内部，就是分别获取不同信息再整合到 `lua_Debug` 的过程。

{{< highlight C "linenos=table, linenostart=193" >}}
static int auxgetinfo (lua_State *L, const char *what, lua_Debug *ar,
		    Closure *f, CallInfo *ci) {
  int status = 1;
  if (f == NULL) {
    info_tailcall(ar);
    return status;
  }
  for (; *what; what++) {
    switch (*what) {
      case 'S': {
	funcinfo(ar, f);
	break;
      }
      case 'l': {
	ar->currentline = (ci) ? currentline(L, ci) : -1;
	break;
      }
      case 'u': {
	ar->nups = f->c.nupvalues;
	break;
      }
      case 'n': {
	ar->namewhat = (ci) ? getfuncname(L, ci, &ar->name) : NULL;
	if (ar->namewhat == NULL) {
	  ar->namewhat = "";  /* not found */
	  ar->name = NULL;
	}
	break;
      }
      case 'L':
      case 'f':  /* handled by lua_getinfo */
	break;
      default: status = 0;  /* invalid option */
    }
  }
  return status;
}


LUA_API int lua_getinfo (lua_State *L, const char *what, lua_Debug *ar) {
  int status;
  Closure *f = NULL;
  CallInfo *ci = NULL;
  lua_lock(L);
  if (*what == '>') {
    StkId func = L->top - 1;
    luai_apicheck(L, ttisfunction(func));
    what++;  /* skip the '>' */
    f = clvalue(func);
    L->top--;  /* pop function */
  }
  else if (ar->i_ci != 0) {  /* no tail call? */
    ci = L->base_ci + ar->i_ci;
    lua_assert(ttisfunction(ci->func));
    f = clvalue(ci->func);
  }
  status = auxgetinfo(L, what, ar, f, ci);
  if (strchr(what, 'f')) {
    if (f == NULL) setnilvalue(L->top);
    else setclvalue(L, L->top, f);
    incr_top(L);
  }
  if (strchr(what, 'L'))
    collectvalidlines(L, f);
  lua_unlock(L);
  return status;
}
{{< /highlight >}}


<div class="src-block-caption">
  <span class="src-block-number">Code Snippet 20</span>:
  ldebug.c
</div>

结合官方文档[^fn:3]，不难理解 getinfo 的行为。


### getlocal {#getlocal}

getlocal 方法，最终深入到 func 模块中的 `luaF_getlocalname` 函数，

{{< highlight C "linenos=table, linenostart=112" >}}
static const char *findlocal (lua_State *L, CallInfo *ci, int n) {
  const char *name;
  Proto *fp = getluaproto(ci);
  if (fp && (name = luaF_getlocalname(fp, n, currentpc(L, ci))) != NULL)
    return name;  /* is a local variable in a Lua function */
  else {
    StkId limit = (ci == L->ci) ? L->top : (ci+1)->func;
    if (limit - ci->base >= n && n > 0)  /* is 'n' inside 'ci' stack? */
      return "(*temporary)";
    else
      return NULL;
  }
}


LUA_API const char *lua_getlocal (lua_State *L, const lua_Debug *ar, int n) {
  CallInfo *ci = L->base_ci + ar->i_ci;
  const char *name = findlocal(L, ci, n);
  lua_lock(L);
  if (name)
      luaA_pushobject(L, ci->base + (n - 1));
  lua_unlock(L);
  return name;
}
{{< /highlight >}}


<div class="src-block-caption">
  <span class="src-block-number">Code Snippet 21</span>:
  ldebug.c
</div>

{{< highlight C "linenos=table, linenostart=159" >}}
/*
** Look for n-th local variable at line `line' in function `func'.
** Returns NULL if not found.
*/
const char *luaF_getlocalname (const Proto *f, int local_number, int pc) {
  int i;
  for (i = 0; i<f->sizelocvars && f->locvars[i].startpc <= pc; i++) {
    if (pc < f->locvars[i].endpc) {  /* is variable active? */
      local_number--;
      if (local_number == 0)
	return getstr(f->locvars[i].varname);
    }
  }
  return NULL;  /* not found */
}
{{< /highlight >}}


<div class="src-block-caption">
  <span class="src-block-number">Code Snippet 22</span>:
  lfunc.c
</div>

其中正是通过 `f->locvars` 来进行寻找，这和 generator 章节是相同的。


### getupval {#getupval}

getupval 方法，最终调用 api 模块中的 `lua_getupvalue` 函数，

{{< highlight C "linenos=table, linenostart=1039" >}}
static const char *aux_upvalue (StkId fi, int n, TValue **val) {
  Closure *f;
  if (!ttisfunction(fi)) return NULL;
  f = clvalue(fi);
  if (f->c.isC) {
    if (!(1 <= n && n <= f->c.nupvalues)) return NULL;
    *val = &f->c.upvalue[n-1];
    return "";
  }
  else {
    Proto *p = f->l.p;
    if (!(1 <= n && n <= p->sizeupvalues)) return NULL;
    *val = f->l.upvals[n-1]->v;
    return getstr(p->upvalues[n-1]);
  }
}


LUA_API const char *lua_getupvalue (lua_State *L, int funcindex, int n) {
  const char *name;
  TValue *val;
  lua_lock(L);
  name = aux_upvalue(index2adr(L, funcindex), n, &val);
  if (name) {
    setobj2s(L, L->top, val);
    api_incr_top(L);
  }
  lua_unlock(L);
  return name;
}
{{< /highlight >}}


<div class="src-block-caption">
  <span class="src-block-number">Code Snippet 23</span>:
  lapi.c
</div>

其中正是通过 `Closure.upvalues` 来寻找 upval 的。


### hook {#hook}

debug 模块提供的另一方面的功能就是 hook。

hook 有 4 种类型[^fn:4]， 分别为 `call return line count` 。

{{< highlight C "linenos=table, linenostart=308" >}}
/*
** Event codes
*/
#define LUA_HOOKCALL	0
#define LUA_HOOKRET	1
#define LUA_HOOKLINE	2
#define LUA_HOOKCOUNT	3
#define LUA_HOOKTAILRET 4


/*
** Event masks
*/
#define LUA_MASKCALL	(1 << LUA_HOOKCALL)
#define LUA_MASKRET	(1 << LUA_HOOKRET)
#define LUA_MASKLINE	(1 << LUA_HOOKLINE)
#define LUA_MASKCOUNT	(1 << LUA_HOOKCOUNT)
{{< /highlight >}}


<div class="src-block-caption">
  <span class="src-block-number">Code Snippet 24</span>:
  lua.h
</div>

sethook 先解析 mask 和 count，再调用 `lua_sethook` 设置 hook。

{{< highlight C "linenos=table, linenostart=225" >}}
static int makemask (const char *smask, int count) {
  int mask = 0;
  if (strchr(smask, 'c')) mask |= LUA_MASKCALL;
  if (strchr(smask, 'r')) mask |= LUA_MASKRET;
  if (strchr(smask, 'l')) mask |= LUA_MASKLINE;
  if (count > 0) mask |= LUA_MASKCOUNT;
  return mask;
}
{{< /highlight >}}


<div class="src-block-caption">
  <span class="src-block-number">Code Snippet 25</span>:
  ldblib.c
</div>

{{< highlight C "linenos=table, linenostart=258" >}}
static int db_sethook (lua_State *L) {
  int arg, mask, count;
  lua_Hook func;
  lua_State *L1 = getthread(L, &arg);
  if (lua_isnoneornil(L, arg+1)) {
    lua_settop(L, arg+1);
    func = NULL; mask = 0; count = 0;  /* turn off hooks */
  }
  else {
    const char *smask = luaL_checkstring(L, arg+2);
    luaL_checktype(L, arg+1, LUA_TFUNCTION);
    count = luaL_optint(L, arg+3, 0);
    func = hookf; mask = makemask(smask, count);
  }
  gethooktable(L);
  lua_pushlightuserdata(L, L1);
  lua_pushvalue(L, arg+1);
  lua_rawset(L, -3);  /* set new hook */
  lua_pop(L, 1);  /* remove hook table */
  lua_sethook(L1, func, mask, count);  /* set hooks */
  return 0;
}
{{< /highlight >}}


<div class="src-block-caption">
  <span class="src-block-number">Code Snippet 26</span>:
  ldblib.c
</div>

{{< highlight C "linenos=table, linenostart=53" >}}
/*
** this function can be called asynchronous (e.g. during a signal)
*/
LUA_API int lua_sethook (lua_State *L, lua_Hook func, int mask, int count) {
  if (func == NULL || mask == 0) {  /* turn off hooks? */
    mask = 0;
    func = NULL;
  }
  L->hook = func;
  L->basehookcount = count;
  resethookcount(L);
  L->hookmask = cast_byte(mask);
  return 1;
}
{{< /highlight >}}


<div class="src-block-caption">
  <span class="src-block-number">Code Snippet 27</span>:
  ldebug.c
</div>

其中将所有 hook 信息存储到当前 `lua_State` 中。

hook 调用的时间点散落在 lvm.c 和 ldo.c 中，全部通过 `luaD_callhook` 来调用。

{{< highlight C "linenos=table, linenostart=181" >}}
void luaD_callhook (lua_State *L, int event, int line) {
  lua_Hook hook = L->hook;
  if (hook && L->allowhook) {
    ptrdiff_t top = savestack(L, L->top);
    ptrdiff_t ci_top = savestack(L, L->ci->top);
    lua_Debug ar;
    ar.event = event;
    ar.currentline = line;
    if (event == LUA_HOOKTAILRET)
      ar.i_ci = 0;  /* tail call; no debug information about it */
    else
      ar.i_ci = cast_int(L->ci - L->base_ci);
    luaD_checkstack(L, LUA_MINSTACK);  /* ensure minimum stack size */
    L->ci->top = L->top + LUA_MINSTACK;
    lua_assert(L->ci->top <= L->stack_last);
    L->allowhook = 0;  /* cannot call hooks inside a hook */
    lua_unlock(L);
    (*hook)(L, &ar);
    lua_lock(L);
    lua_assert(!L->allowhook);
    L->allowhook = 1;
    L->ci->top = restorestack(L, ci_top);
    L->top = restorestack(L, top);
  }
}
{{< /highlight >}}


<div class="src-block-caption">
  <span class="src-block-number">Code Snippet 28</span>:
  ldo.c
</div>

可能通过搜索 `luaD_callhook` 的调用位置，确认不同的 mask 对应的调用时机，
这一点和 vm 的运行相关，细节就不再赘述。


## practice {#practice}

标准库的代码量并不小，但是安排的架构很清晰，读者可根据自己的需要和兴趣有目的的按点阅读。

| 章节涉及文件 | 建议阅读程度 |
|--------|--------|
| linit.c    | ★ ★ ★ ★ ★ |
| lbaselib.c | ★ ★ ★ ★ ☆ |
| lmathlib.c | ★ ★ ☆ ☆ ☆ |
| lstrlib.c  | ★ ★ ☆ ☆ ☆ |
| ltablib.c  | ★ ★ ☆ ☆ ☆ |
| liolib.c   | ★ ★ ☆ ☆ ☆ |
| loslib.c   | ★ ★ ☆ ☆ ☆ |
| loadlib.c  | ★ ★ ☆ ☆ ☆ |
| ldblib.c   | ★ ★ ☆ ☆ ☆ |
| ldebug.c   | ★ ★ ☆ ☆ ☆ |

[^fn:1]: : <http://www.lua.org/manual/5.1/manual.html#5>
[^fn:2]: : <http://www.lua.org/manual/5.1/manual.html#5.9>
[^fn:3]: : <http://www.lua.org/manual/5.1/manual.html#lua%5Fgetinfo>
[^fn:4]: : <http://www.lua.org/manual/5.1/manual.html#lua%5Fsethook>
