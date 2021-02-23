---
title: "memory"
author: ["DreamAndDead"]
date: 2020-12-23T11:59:00+08:00
lastmod: 2021-02-23T11:47:53+08:00
draft: false
---

内存管理对所有程序都很关键，对于动态语言更是如此。

lua 是单线程程序，即使在内部实现了协程，但内存还是统一管理的。

内存回收使用 gc 算法，是非常重要的模块，而相对地，内存分配就显得非常简单。

本章就讲解 lua 源码中关于内存分配的内容。


## core api {#core-api}

内存分配，无外乎涉及 3 个基础 api

-   malloc
-   realloc
-   free

对于了解操作系统和 C 语言的大家都不陌生。

lua 内部将其简化为 1 个 api，定义原型为 `lua_Alloc`

{{< highlight c "linenos=table, linenostart=63" >}}
/*
** prototype for memory-allocation functions
*/
typedef void * (*lua_Alloc) (void *ud, void *ptr, size_t osize, size_t nsize);
{{< /highlight >}}


<div class="src-block-caption">
  <span class="src-block-number">Code Snippet 1</span>:
  lua.h
</div>

这是一个函数指针，规定其行为需遵从如下约定

{{< highlight c "linenos=table, linenostart=23" >}}
/*
** About the realloc function:
** void * frealloc (void *ud, void *ptr, size_t osize, size_t nsize);
** (`osize' is the old size, `nsize' is the new size)
**
** Lua ensures that (ptr == NULL) iff (osize == 0).
**
** * frealloc(ud, NULL, 0, x) creates a new block of size `x'
**
** * frealloc(ud, p, x, 0) frees the block `p'
** (in this specific case, frealloc must return NULL).
** particularly, frealloc(ud, NULL, 0, 0) does nothing
** (which is equivalent to free(NULL) in ANSI C)
**
** frealloc returns NULL if it cannot create or reallocate the area
** (any reallocation to an equal or smaller size cannot fail!)
*/
{{< /highlight >}}


<div class="src-block-caption">
  <span class="src-block-number">Code Snippet 2</span>:
  lmem.c
</div>

简单的说，就是根据参数的不同，将 3 个基础 api 的功能用 1 个 api 来表示

-   malloc， `frealloc(ud, NULL, 0, ns)` ，分配大小为 ns 的内存，返回头地址
-   realloc， `frealloc(ud, p, os, ns)` ，变更 p 开始的内存块大小从 os 到 ns，失败返回 NULL
-   free， `frealloc(ud, p, os, 0)` ，回收以 p 开始的 os 大小的内存块，返回 NULL

lua 默认提供一个符合约定的 frealloc 函数供内部使用，可以看到它是非常纯粹的

{{< highlight c "linenos=table, linenostart=627" >}}
static void *l_alloc (void *ud, void *ptr, size_t osize, size_t nsize) {
  (void)ud;
  (void)osize;
  if (nsize == 0) {
    free(ptr);
    return NULL;
  }
  else
    return realloc(ptr, nsize);
}
{{< /highlight >}}


<div class="src-block-caption">
  <span class="src-block-number">Code Snippet 3</span>:
  lauxlib.c
</div>


### about global state {#about-global-state}

在 [overview]({{< relref "overview" >}}) 章节，简单提到了 `global_State` ，字面意义上理解，它和全局的状态相关。

这里就是它的一个应用方面，记录内存分配相关的状态。

{{< highlight C "linenos=table, linenostart=65" >}}
/*
** `global state', shared by all threads of this state
*/
typedef struct global_State {
  stringtable strt;  /* hash table for strings */
  lua_Alloc frealloc;  /* function to reallocate memory */
  void *ud;         /* auxiliary data to `frealloc' */
  lu_byte currentwhite;
  lu_byte gcstate;  /* state of garbage collector */
  int sweepstrgc;  /* position of sweep in `strt' */
  GCObject *rootgc;  /* list of all collectable objects */
  GCObject **sweepgc;  /* position of sweep in `rootgc' */
  GCObject *gray;  /* list of gray objects */
  GCObject *grayagain;  /* list of objects to be traversed atomically */
  GCObject *weak;  /* list of weak tables (to be cleared) */
  GCObject *tmudata;  /* last element of list of userdata to be GC */
  Mbuffer buff;  /* temporary buffer for string concatentation */
  lu_mem GCthreshold;
  lu_mem totalbytes;  /* number of bytes currently allocated */
  lu_mem estimate;  /* an estimate of number of bytes actually in use */
  lu_mem gcdept;  /* how much GC is `behind schedule' */
  int gcpause;  /* size of pause between successive GCs */
  int gcstepmul;  /* GC `granularity' */
  lua_CFunction panic;  /* to be called in unprotected errors */
  TValue l_registry;
  struct lua_State *mainthread;
  UpVal uvhead;  /* head of double-linked list of all open upvalues */
  struct Table *mt[NUM_TAGS];  /* metatables for basic types */
  TString *tmname[TM_N];  /* array with tag-method names */
} global_State;
{{< /highlight >}}


<div class="src-block-caption">
  <span class="src-block-number">Code Snippet 4</span>:
  lstate.h
</div>

-   frealloc 引用内部的内存分配函数，即上面提到的 `l_alloc`
-   ud 引用 frealloc 函数的第一个参数，提供辅助数据，用于用户自定义
-   totalbytes 记录已分配的总内存大小

在了解 `global_State` 相关字段后，就不难理解 lua 在 c api 层面提供的相关接口，
使用户自定义内存管理函数。

{{< highlight c "linenos=table, linenostart=1007" >}}
LUA_API lua_Alloc lua_getallocf (lua_State *L, void **ud) {
  lua_Alloc f;
  lua_lock(L);
  if (ud) *ud = G(L)->ud;
  f = G(L)->frealloc;
  lua_unlock(L);
  return f;
}


LUA_API void lua_setallocf (lua_State *L, lua_Alloc f, void *ud) {
  lua_lock(L);
  G(L)->ud = ud;
  G(L)->frealloc = f;
  lua_unlock(L);
}
{{< /highlight >}}


<div class="src-block-caption">
  <span class="src-block-number">Code Snippet 5</span>:
  lapi.c
</div>


## generic api {#generic-api}

核心 api 定义之后，其它上层方法不过是对它的封装。

{{< figure src="mem-call.png" >}}

lmem.h 对外提供了诸多函数和宏，依赖关系如图示，这里简要介绍图中标识的 3 个方法，其余留给读者自行阅读。


### `luaM_realloc_` {#luam-realloc}

对核心 api 进行了封装，检测函数错误，以及计算 totalbytes，为其它方法提供了基础。

{{< highlight c "linenos=table, linenostart=73" >}}
/*
** generic allocation routine.
*/
void *luaM_realloc_ (lua_State *L, void *block, size_t osize, size_t nsize) {
  global_State *g = G(L);
  lua_assert((osize == 0) == (block == NULL));
  block = (*g->frealloc)(g->ud, block, osize, nsize);
  if (block == NULL && nsize > 0)
    luaD_throw(L, LUA_ERRMEM);
  lua_assert((nsize == 0) == (block == NULL));
  g->totalbytes = (g->totalbytes - osize) + nsize;
  return block;
}
{{< /highlight >}}


<div class="src-block-caption">
  <span class="src-block-number">Code Snippet 6</span>:
  lmem.c
</div>


### `luaM_rellocv` {#luam-rellocv}

这个方法是一个宏，其中参数含义为

-   L -> `lua_State`
-   b -> block pointer
-   on -> old number n
-   n -> new number n
-   e -> elem size

<!--listend-->

{{< highlight c "linenos=table, linenostart=19" >}}
#define luaM_reallocv(L,b,on,n,e) \
	((cast(size_t, (n)+1) <= MAX_SIZET/(e)) ?  /* +1 to avoid warnings */ \
		luaM_realloc_(L, (b), (on)*(e), (n)*(e)) : \
		luaM_toobig(L))
{{< /highlight >}}


<div class="src-block-caption">
  <span class="src-block-number">Code Snippet 7</span>:
  lmem.h
</div>

可以看出，这个宏在 `luaM_realloc_` 的基础上，方便对多元素数组进行内存分配，省去重复手动计算内存大小的困扰。

其中有一个细节，使用 `n+1` 和 `MAX_SIZET/e` 进行比较，而非使用 `(n+1) * e` 和 `MAX_SIZET` 进行比较，
因为 `size_t` 是无符号类型，先进行除法来避免比较时溢出。


### `luaM_growaux_` {#luam-growaux}

这个方法在 `luaM_rellocv` 的基础上，添加了 limit 的限制。

最小不能小于 4， 最大不能超过 limit，按 2 倍速度进行内存 grow，适用于管理 **类 vector 结构** 。

{{< highlight c "linenos=table, linenostart=46" >}}
void *luaM_growaux_ (lua_State *L, void *block, int *size, size_t size_elems,
		     int limit, const char *errormsg) {
  void *newblock;
  int newsize;
  if (*size >= limit/2) {  /* cannot double it? */
    if (*size >= limit)  /* cannot grow even a little? */
      luaG_runerror(L, errormsg);
    newsize = limit;  /* still have at least one free place */
  }
  else {
    newsize = (*size)*2;
    if (newsize < MINSIZEARRAY)
      newsize = MINSIZEARRAY;  /* minimum size */
  }
  newblock = luaM_reallocv(L, block, *size, newsize, size_elems);
  *size = newsize;  /* update only when everything else is OK */
  return newblock;
}
{{< /highlight >}}


<div class="src-block-caption">
  <span class="src-block-number">Code Snippet 8</span>:
  lmem.c
</div>


## practice {#practice}

本章并不复杂，明确了上面的基础，剩下的方法并不难理解。

| 文件   | 建议 |
|------|----|
| lmem.h | 仔细阅读 |
| lmem.c | 仔细阅读 |
