---
title: "vm"
author: ["DreamAndDead"]
date: 2021-01-14T17:50:00+08:00
lastmod: 2021-02-23T13:20:35+08:00
draft: false
---

代码生成完成之后，整个文件分析成为一个单独的 Proto，交由 vm 来执行。

和 parser 相比，vm 更容易琢磨，因为它只会从 Proto 中取出字节码，
并按照指令的含义一行一行来执行。

所以各种指令的执行过程不是本章的重点，只需要参考 opcode 相应的注释就不难理解，
本章更关注 vm 内部各个组件的协同过程。


## model {#model}

之前在 opcode 章节简单提到了 vm 内部的模型，这里来详细讨论各个部分。

{{< figure src="vm-model.png" >}}


### code {#code}

vm 所执行的代码来自 parser，即存储在 Proto 中。

{{< highlight C "linenos=table, linenostart=228" >}}
/*
** Function Prototypes
*/
typedef struct Proto {
  CommonHeader;
  TValue *k;  /* constants used by the function */
  Instruction *code;
  struct Proto **p;  /* functions defined inside the function */
  int *lineinfo;  /* map from opcodes to source lines */
  struct LocVar *locvars;  /* information about local variables */
{{< /highlight >}}


<div class="src-block-caption">
  <span class="src-block-number">Code Snippet 1</span>:
  lobject.h
</div>

{{< highlight C "linenos=table, linenostart=84" >}}
/*
** type for virtual-machine instructions
** must be an unsigned with (at least) 4 bytes (see details in lopcodes.h)
*/
typedef lu_int32 Instruction;
{{< /highlight >}}


<div class="src-block-caption">
  <span class="src-block-number">Code Snippet 2</span>:
  llimits.h
</div>

Proto.code 是指令数组，索引从 0 开始，存储了所有生成的指令。

vm 在执行的时候，内部存在一个 pc 指针，指向当前要执行指令。

这个 pc 和代码生成阶段的 pc 是完全不同的，代码生成阶段的 pc 用来标识生成指令的下一个索引，
而 vm 在运行阶段的 pc 是一个指针。

{{< highlight C "linenos=table, linenostart=377" >}}
void luaV_execute (lua_State *L, int nexeccalls) {
  LClosure *cl;
  StkId base;
  TValue *k;
  const Instruction *pc;
{{< /highlight >}}


<div class="src-block-caption">
  <span class="src-block-number">Code Snippet 3</span>:
  lvm.c
</div>


### kst {#kst}

k 表在分析阶段，收集了所有常量，并提供索引供指令使用。

所以在执行指令的时候，需要 k 表的配合来引用常量，vm 中直接用 `TValue *k` 引用 Proto 中的 k 表。

{{< highlight C "linenos=table, linenostart=377" >}}
void luaV_execute (lua_State *L, int nexeccalls) {
  LClosure *cl;
  StkId base;
  TValue *k;
  const Instruction *pc;
 reentry:  /* entry point */
  lua_assert(isLua(L->ci));
  pc = L->savedpc;
  cl = &clvalue(L->ci->func)->l;
  base = L->base;
  k = cl->p->k;
{{< /highlight >}}


<div class="src-block-caption">
  <span class="src-block-number">Code Snippet 4</span>:
  lvm.c
</div>


### stack {#stack}

在代码生成阶段，parser 只能操作一个“想象”中的栈，而在 vm 中则是具体实现了它。

stack 的本质是一个 TValue 数组，通过 StkId 引用栈中元素。

{{< highlight C "linenos=table, linenostart=193" >}}
typedef TValue *StkId;  /* index to stack elements */
{{< /highlight >}}


<div class="src-block-caption">
  <span class="src-block-number">Code Snippet 5</span>:
  lobject.h
</div>

栈及栈的相应状态，存储在 `lua_State` 中，同 FuncState LexState 一样，
`lua_State` 也是用于记录状态的结构，具体的说，就是用来记录线程运行时的状态。

{{< highlight C "linenos=table, linenostart=97" >}}
/*
** `per thread' state
*/
struct lua_State {
  CommonHeader;
  lu_byte status;
  StkId top;  /* first free slot in the stack */
  StkId base;  /* base of current function */
  global_State *l_G;
  CallInfo *ci;  /* call info for current function */
  const Instruction *savedpc;  /* `savedpc' of current function */
  StkId stack_last;  /* last free slot in the stack */
  StkId stack;  /* stack base */
  CallInfo *end_ci;  /* points after end of ci array*/
  CallInfo *base_ci;  /* array of CallInfo's */
  int stacksize;
  int size_ci;  /* size of array `base_ci' */
  unsigned short nCcalls;  /* number of nested C calls */
  unsigned short baseCcalls;  /* nested C calls when resuming coroutine */
  lu_byte hookmask;
  lu_byte allowhook;
  int basehookcount;
  int hookcount;
  lua_Hook hook;
  TValue l_gt;  /* table of globals */
  TValue env;  /* temporary place for environments */
  GCObject *openupval;  /* list of open upvalues in this stack */
  GCObject *gclist;
  struct lua_longjmp *errorJmp;  /* current error recover point */
  ptrdiff_t errfunc;  /* current error handling function (stack index) */
};
{{< /highlight >}}


<div class="src-block-caption">
  <span class="src-block-number">Code Snippet 6</span>:
  lstate.h
</div>

其中

-   `lu_byte status` ，线程状态
-   `StkId top` ，函数调用时的栈顶指针
-   `StkId base` ，函数调用时的栈基指针
-   `global_State *l_G` ，指向 global state
-   `CallInfo *ci` ，当前 CallInfo
-   `const Instruction *savedpc` ，暂存指令位置
-   `StkId stack_last` ，栈空间的最后
-   `StkId stack` ，栈指针
-   `CallInfo *end_ci` ，CallInfo 数组的最后
-   `CallInfo *base_ci` ，CallInfo 数组的开始
-   `int statcksize` ，栈空间大小
-   `int size_ci` ，CallInfo 数组的大小
-   `TValue l_gt` ，Gbl 表
-   `TValue env` ，临时存储环境

至于 CallInfo，在后续函数调用章节再讲解。


### gbl {#gbl}

Gbl 表用于记录 lua 线程的全局变量，存储在 `lua_State.l_gt` 中，
是一个 table 结构。

setglobal/getglobal 指令就作用于这里。


### upvalue {#upvalue}

upvalue 是一个数组，元素为 `UpVal *` ，存在于每一个 closure 中。

{{< highlight C "linenos=table, linenostart=302" >}}
typedef struct LClosure {
  ClosureHeader;
  struct Proto *p;
  UpVal *upvals[1];
} LClosure;
{{< /highlight >}}


<div class="src-block-caption">
  <span class="src-block-number">Code Snippet 7</span>:
  lobject.h
</div>

{{< highlight C "linenos=table, linenostart=270" >}}
/*
** Upvalues
*/

typedef struct UpVal {
  CommonHeader;
  TValue *v;  /* points to stack or to its own value */
  union {
    TValue value;  /* the value (when closed) */
    struct {  /* double linked list (when open) */
      struct UpVal *prev;
      struct UpVal *next;
    } l;
  } u;
} UpVal;
{{< /highlight >}}


<div class="src-block-caption">
  <span class="src-block-number">Code Snippet 8</span>:
  lobject.h
</div>

对于每一个 Proto，在执行前都会封装为 closure，

{{< highlight C "linenos=table, linenostart=723" >}}
case OP_CLOSURE: {
  Proto *p;
  Closure *ncl;
  int nup, j;
  p = cl->p->p[GETARG_Bx(i)];
  nup = p->nups;
  ncl = luaF_newLclosure(L, nup, cl->env);
  ncl->l.p = p;
  for (j=0; j<nup; j++, pc++) {
    if (GET_OPCODE(*pc) == OP_GETUPVAL)
      ncl->l.upvals[j] = cl->upvals[GETARG_B(*pc)];
    else {
      lua_assert(GET_OPCODE(*pc) == OP_MOVE);
      ncl->l.upvals[j] = luaF_findupval(L, base + GETARG_B(*pc));
    }
  }
  setclvalue(L, ra, ncl);
  Protect(luaC_checkGC(L));
  continue;
{{< /highlight >}}


<div class="src-block-caption">
  <span class="src-block-number">Code Snippet 9</span>:
  lvm.c
</div>

其中调用 `luaF_newLclosure` 来执行，其中为 upvalue 数组开辟了空间，
数组元素是 `UpVal *` 指针类型，具体指向在运行时确定。

{{< highlight C "linenos=table, linenostart=33" >}}
Closure *luaF_newLclosure (lua_State *L, int nelems, Table *e) {
  Closure *c = cast(Closure *, luaM_malloc(L, sizeLclosure(nelems)));
  luaC_link(L, obj2gco(c), LUA_TFUNCTION);
  c->l.isC = 0;
  c->l.env = e;
  c->l.nupvalues = cast_byte(nelems);
  while (nelems--) c->l.upvals[nelems] = NULL;
  return c;
}
{{< /highlight >}}


<div class="src-block-caption">
  <span class="src-block-number">Code Snippet 10</span>:
  lfunc.c
</div>

前面提到，整个文件作为一个匿名函数来分析，最终得到 Proto 交由 vm 执行，
同样的原则，这个 Proto 在执行之前，需要封装为 closure，

{{< highlight C "linenos=table, linenostart=491" >}}
static void f_parser (lua_State *L, void *ud) {
  int i;
  Proto *tf;
  Closure *cl;
  struct SParser *p = cast(struct SParser *, ud);
  int c = luaZ_lookahead(p->z);
  luaC_checkGC(L);
  tf = ((c == LUA_SIGNATURE[0]) ? luaU_undump : luaY_parser)(L, p->z,
							     &p->buff, p->name);
  cl = luaF_newLclosure(L, tf->nups, hvalue(gt(L)));
  cl->l.p = tf;
  for (i = 0; i < tf->nups; i++)  /* initialize eventual upvalues */
    cl->l.upvals[i] = luaF_newupval(L);
  setclvalue(L, L->top, cl);
  incr_top(L);
}
{{< /highlight >}}


<div class="src-block-caption">
  <span class="src-block-number">Code Snippet 11</span>:
  ldo.c
</div>


## the loop {#the-loop}

vm 执行 closure 的入口为 `luaV_execute` ，

{{< highlight C "linenos=table, linenostart=377" >}}
void luaV_execute (lua_State *L, int nexeccalls) {
  LClosure *cl;
  StkId base;
  TValue *k;
  const Instruction *pc;
 reentry:  /* entry point */
  lua_assert(isLua(L->ci));
  pc = L->savedpc;
  cl = &clvalue(L->ci->func)->l;
  base = L->base;
  k = cl->p->k;
  /* main loop of interpreter */
  for (;;) {
    const Instruction i = *pc++;
    StkId ra;
    if ((L->hookmask & (LUA_MASKLINE | LUA_MASKCOUNT)) &&
	(--L->hookcount == 0 || L->hookmask & LUA_MASKLINE)) {
      traceexec(L, pc);
      if (L->status == LUA_YIELD) {  /* did hook yield? */
	L->savedpc = pc - 1;
	return;
      }
      base = L->base;
    }
    /* warning!! several calls may realloc the stack and invalidate `ra' */
    ra = RA(i);
    lua_assert(base == L->base && L->base == L->ci->base);
    lua_assert(base <= L->top && L->top <= L->stack + L->stacksize);
    lua_assert(L->top == L->ci->top || luaG_checkopenop(i));
    switch (GET_OPCODE(i)) {
      case OP_MOVE: {
	setobjs2s(L, ra, RB(i));
	continue;
      }
      case OP_LOADK: {
	setobj2s(L, ra, KBx(i));
	continue;
{{< /highlight >}}


<div class="src-block-caption">
  <span class="src-block-number">Code Snippet 12</span>:
  lvm.c
</div>

-   line 389，内部是一个死循环
-   line 390，默认自增 pc，从中取出指令
-   line 406，根据指令的类型，执行对应的操作

大部分指令的操作都非常简单，对应 opcode 的语义注释就可以理解。

下面只针对重要的部分，vm 是如何运行 closure 的。


## closure {#closure}

在编译时，并没有涉及到 closure 结构，作为 8 种基础类型之一，closure 结构在运行时发挥作用。

{{< highlight C "linenos=table, linenostart=287" >}}
/*
** Closures
*/

#define ClosureHeader \
	CommonHeader; lu_byte isC; lu_byte nupvalues; GCObject *gclist; \
	struct Table *env

typedef struct CClosure {
  ClosureHeader;
  lua_CFunction f;
  TValue upvalue[1];
} CClosure;


typedef struct LClosure {
  ClosureHeader;
  struct Proto *p;
  UpVal *upvals[1];
} LClosure;


typedef union Closure {
  CClosure c;
  LClosure l;
} Closure;


#define iscfunction(o)	(ttype(o) == LUA_TFUNCTION && clvalue(o)->c.isC)
#define isLfunction(o)	(ttype(o) == LUA_TFUNCTION && !clvalue(o)->c.isC)
{{< /highlight >}}


<div class="src-block-caption">
  <span class="src-block-number">Code Snippet 13</span>:
  lobject.h
</div>

Closure 是 union 类型，容纳 C Closure 和 Lua Closure 两种类型，C Closure 之后再讲解，
这里只看 Lua Closure。

-   `lu_byte isC` ，标识 Closure 是 C 还是 Lua
-   `lu_byte nupvalues` ，拥有 upvalue 的数量
-   `struct Table *env` ，函数运行环境，等同于 gbl 表
-   `struct Proto *p` ，指向 parser 生成的 Proto
-   `Upval *upvals[1]` ，为 upvalue 分配的空间


### def {#def}

回忆 parser 中 function 的定义过程，解析 function 定义的过程是递归，
生成相应的 Proto 并链接到上层 Proto.p 中。

所以在 vm 中和 function 定义相关的功能，只有使用 closure 指令进行封装这一步。

{{< highlight C "linenos=table, linenostart=723" >}}
case OP_CLOSURE: {
  Proto *p;
  Closure *ncl;
  int nup, j;
  p = cl->p->p[GETARG_Bx(i)];
  nup = p->nups;
  ncl = luaF_newLclosure(L, nup, cl->env);
  ncl->l.p = p;
  for (j=0; j<nup; j++, pc++) {
    if (GET_OPCODE(*pc) == OP_GETUPVAL)
      ncl->l.upvals[j] = cl->upvals[GETARG_B(*pc)];
    else {
      lua_assert(GET_OPCODE(*pc) == OP_MOVE);
      ncl->l.upvals[j] = luaF_findupval(L, base + GETARG_B(*pc));
    }
  }
  setclvalue(L, ra, ncl);
  Protect(luaC_checkGC(L));
  continue;
}
{{< /highlight >}}


<div class="src-block-caption">
  <span class="src-block-number">Code Snippet 14</span>:
  lvm.c
</div>

line 729 为 closure 结构分配空间。

line 731 - 738 是比较有意思的地方，还记得指令生成时，对 upvalue 的约定吗？

VLOCAL 使用 move 指令，VUPVAL 使用 getupval 指令，这里根据 upvalue 的数量，
向下读取相应数量的指令，初始化 upvalue。

详细到下面的 upval 小节解析。

line 739 将封装生成的 closure 赋值给变量。


### call {#call}

介绍函数调用之前，先来了解一下 CallInfo 结构。

整个线程的栈记录着计算的状态，函数调用具有天生的栈特性，
调用前入栈，调用后出栈。

CallInfo 就是用来记录函数调用对应栈的位置的。

{{< highlight C "linenos=table, linenostart=45" >}}
/*
** informations about a call
*/
typedef struct CallInfo {
  StkId base;  /* base for this function */
  StkId func;  /* function index in the stack */
  StkId	top;  /* top for this function */
  const Instruction *savedpc;
  int nresults;  /* expected number of results from this function */
  int tailcalls;  /* number of tail calls lost under this entry */
} CallInfo;
{{< /highlight >}}


<div class="src-block-caption">
  <span class="src-block-number">Code Snippet 15</span>:
  lstate.h
</div>

-   func，指向调用的函数本身
-   base，指向调用函数对应的栈基地址
-   top，指向调用函数对应的栈顶地址

`lua_State` 中，存在着一个 CallInfo 数组，索引从 0 开始，记录着函数调用的层次。

`base_ci` 指向索引 0， `end_ci` 指向最后， `ci` 指向当前的函数调用层次。
每当遇到新的函数调用，ci 自增；调用结束，ci 自减。

具体来看一个示例，

```lua
local function f()
end

f(1, 2, 3)
```

```text
; function [0] definition (level 1)
; 0 upvalues, 0 params, 2 is_vararg, 5 stacks
.function  0 0 2 5
.local  "f"  ; 0
.const  1  ; 0
.const  2  ; 1
.const  3  ; 2

  ; function [0] definition (level 2)
  ; 0 upvalues, 0 params, 0 is_vararg, 2 stacks
  .function  0 0 0 2
  [1] return     0   1
  ; end of function

[1] closure    0   0        ; 0 upvalues
[2] move       1   0
[3] loadk      2   0        ; 1
[4] loadk      3   1        ; 2
[5] loadk      4   2        ; 3
[6] call       1   4   1
[7] return     0   1
; end of function
```

定义一个函数 f，并以参数 1 2 3 来调用它。

在调用 call 指令之前，整体的栈状态如下，

{{< figure src="vm-stack-call.png" >}}

被调用的函数，先入栈，其后再压入传入的参数，在调用时，新增 CallInfo 结构，
ci->func 指向被调用的函数，ci->base 指向第一个参数，ci->top 指向取决于被调用的函数分配的空间大小。

上图指的是 vm 调用函数 chunk 对应的栈状态。

L->base L->top 永远指向当前正在被调用的函数的栈区域，代码生成过程中“想象”中的栈，就是由
L->base L->top 指定的区域。

调用 call 指令之后，栈状态如下，

{{< figure src="vm-stack-call-1.png" >}}

新增 ci，用于管理 chunk 调用函数 f 对应的状态，原则和上面相同。

相应代码具体描述了对应的过程，

{{< highlight C "linenos=table, linenostart=586" >}}
case OP_CALL: {
  int b = GETARG_B(i);
  int nresults = GETARG_C(i) - 1;
  if (b != 0) L->top = ra+b;  /* else previous instruction set top */
  L->savedpc = pc;
  switch (luaD_precall(L, ra, nresults)) {
    case PCRLUA: {
      nexeccalls++;
      goto reentry;  /* restart luaV_execute over new Lua function */
    }
    case PCRC: {
      /* it was a C function (`precall' called it); adjust results */
      if (nresults >= 0) L->top = L->ci->top;
      base = L->base;
      continue;
    }
    default: {
      return;  /* yield */
    }
  }
}
{{< /highlight >}}


<div class="src-block-caption">
  <span class="src-block-number">Code Snippet 16</span>:
  lvm.c
</div>

{{< highlight C "linenos=table, linenostart=265" >}}
int luaD_precall (lua_State *L, StkId func, int nresults) {
  LClosure *cl;
  ptrdiff_t funcr;
  if (!ttisfunction(func)) /* `func' is not a function? */
    func = tryfuncTM(L, func);  /* check the `function' tag method */
  funcr = savestack(L, func);
  cl = &clvalue(func)->l;
  L->ci->savedpc = L->savedpc;
  if (!cl->isC) {  /* Lua function? prepare its call */
    CallInfo *ci;
    StkId st, base;
    Proto *p = cl->p;
    luaD_checkstack(L, p->maxstacksize);
    func = restorestack(L, funcr);
    if (!p->is_vararg) {  /* no varargs? */
      base = func + 1;
      if (L->top > base + p->numparams)
	L->top = base + p->numparams;
    }
    else {  /* vararg function */
      int nargs = cast_int(L->top - func) - 1;
      base = adjust_varargs(L, p, nargs);
      func = restorestack(L, funcr);  /* previous call may change the stack */
    }
    ci = inc_ci(L);  /* now `enter' new function */
    ci->func = func;
    L->base = ci->base = base;
    ci->top = L->base + p->maxstacksize;
    lua_assert(ci->top <= L->stack_last);
    L->savedpc = p->code;  /* starting point */
    ci->tailcalls = 0;
    ci->nresults = nresults;
    for (st = L->top; st < ci->top; st++)
      setnilvalue(st);
    L->top = ci->top;
    if (L->hookmask & LUA_MASKCALL) {
      L->savedpc++;  /* hooks assume 'pc' is already incremented */
      luaD_callhook(L, LUA_HOOKCALL, -1);
      L->savedpc--;  /* correct 'pc' */
    }
    return PCRLUA;
  }
{{< /highlight >}}


<div class="src-block-caption">
  <span class="src-block-number">Code Snippet 17</span>:
  ldo.c
</div>


### return {#return}

return 的过程和 call 相反，收集相应的返回值，并将值从 ci->func 开始覆盖，
销毁当前 ci，返回到上层 ci。

上层 ci 从调用函数的位置收集相应的返回值。

{{< figure src="vm-stack-call-2.png" >}}

还是上面的示例，调用 f 返回之后，没有返回值。

ci 回退到上层，不收集返回值。

相应实现的代码如下，

{{< highlight C "linenos=table, linenostart=639" >}}
case OP_RETURN: {
  int b = GETARG_B(i);
  if (b != 0) L->top = ra+b-1;
  if (L->openupval) luaF_close(L, base);
  L->savedpc = pc;
  b = luaD_poscall(L, ra);
  if (--nexeccalls == 0)  /* was previous function running `here'? */
    return;  /* no: return */
  else {  /* yes: continue its execution */
    if (b) L->top = L->ci->top;
    lua_assert(isLua(L->ci));
    lua_assert(GET_OPCODE(*((L->ci)->savedpc - 1)) == OP_CALL);
    goto reentry;
  }
}
{{< /highlight >}}


<div class="src-block-caption">
  <span class="src-block-number">Code Snippet 18</span>:
  lvm.c
</div>

{{< highlight C "linenos=table, linenostart=343" >}}
int luaD_poscall (lua_State *L, StkId firstResult) {
  StkId res;
  int wanted, i;
  CallInfo *ci;
  if (L->hookmask & LUA_MASKRET)
    firstResult = callrethooks(L, firstResult);
  ci = L->ci--;
  res = ci->func;  /* res == final position of 1st result */
  wanted = ci->nresults;
  L->base = (ci - 1)->base;  /* restore base */
  L->savedpc = (ci - 1)->savedpc;  /* restore savedpc */
  /* move results to correct place */
  for (i = wanted; i != 0 && firstResult < L->top; i--)
    setobjs2s(L, res++, firstResult++);
  while (i-- > 0)
    setnilvalue(res++);
  L->top = res;
  return (wanted - LUA_MULTRET);  /* 0 iff wanted == LUA_MULTRET */
}
{{< /highlight >}}


<div class="src-block-caption">
  <span class="src-block-number">Code Snippet 19</span>:
  ldo.c
</div>


### upval {#upval}

之前已经零碎的提到 upvalue 的几个方面，
本节来详细讨论 vm 中是如何实现 upvalue 的。

先来看一段示例，

```lua
local a

local function f()
   local b

   local function g()
      b = 20
      a = 10
   end

   g()

   return g
end

local h = f()

h()
```

a 和 b 都是函数 g 的 upval。

当函数 g 在 f 内部第一次调用时，修改了 a 和 b 值，此时 a 和 b 在栈上都是存活的，
因为 a 是 chunk 的局部变量，b 是 f 的局部变量。

当调用 f，将 g 赋值与 h 时，此时调用 h，a 依然是存活的，但是由于离开了 f，b 在栈上已经被回收。

此时 g 如何访问到 upvalue b 呢？

lua 用一种灵巧的方法来解决这个问题。

{{< highlight C "linenos=table, linenostart=270" >}}
/*
** Upvalues
*/

typedef struct UpVal {
  CommonHeader;
  TValue *v;  /* points to stack or to its own value */
  union {
    TValue value;  /* the value (when closed) */
    struct {  /* double linked list (when open) */
      struct UpVal *prev;
      struct UpVal *next;
    } l;
  } u;
} UpVal;
{{< /highlight >}}


<div class="src-block-caption">
  <span class="src-block-number">Code Snippet 20</span>:
  lobject.h
</div>

从注释中可以看到，upval 有两种状态，open 和 closed。

其中 v 指向 upval 所引用的值，当状态为 closed 时，指向自身的 u.value；
当状态为 open 时，指向栈中元素。

比如上面的示例代码，当在函数 f 中调用 g 时，a 和 b 在栈上都是存活的，
相应的 upval 处于 open 状态，分别指向栈中对应的地址。

{{< figure src="vm-upval-open.png" >}}

当离开函数 f 调用 h 时，已经离开了函数 f 的作用域，b 不再于栈上存活，
于是进行 close 操作，将 b 的值拷贝到 u.value，并修改 v 的指向。

这里的操作对于 l->upvals 是完全透明的，因为其只通过 v 来访问 upval 的值。

{{< figure src="vm-upval-close.png" >}}

{{< highlight C "linenos=table, linenostart=723" >}}
case OP_CLOSURE: {
  Proto *p;
  Closure *ncl;
  int nup, j;
  p = cl->p->p[GETARG_Bx(i)];
  nup = p->nups;
  ncl = luaF_newLclosure(L, nup, cl->env);
  ncl->l.p = p;
  for (j=0; j<nup; j++, pc++) {
    if (GET_OPCODE(*pc) == OP_GETUPVAL)
      ncl->l.upvals[j] = cl->upvals[GETARG_B(*pc)];
    else {
      lua_assert(GET_OPCODE(*pc) == OP_MOVE);
      ncl->l.upvals[j] = luaF_findupval(L, base + GETARG_B(*pc));
    }
  }
  setclvalue(L, ra, ncl);
  Protect(luaC_checkGC(L));
  continue;
}
{{< /highlight >}}


<div class="src-block-caption">
  <span class="src-block-number">Code Snippet 21</span>:
  lvm.c
</div>

{{< highlight C "linenos=table, linenostart=53" >}}
UpVal *luaF_findupval (lua_State *L, StkId level) {
  global_State *g = G(L);
  GCObject **pp = &L->openupval;
  UpVal *p;
  UpVal *uv;
  while (*pp != NULL && (p = ngcotouv(*pp))->v >= level) {
    lua_assert(p->v != &p->u.value);
    if (p->v == level) {  /* found a corresponding upvalue? */
      if (isdead(g, obj2gco(p)))  /* is it dead? */
	changewhite(obj2gco(p));  /* ressurect it */
      return p;
    }
    pp = &p->next;
  }
  uv = luaM_new(L, UpVal);  /* not found: create a new one */
  uv->tt = LUA_TUPVAL;
  uv->marked = luaC_white(g);
  uv->v = level;  /* current value lives in the stack */
  uv->next = *pp;  /* chain it in the proper position */
  *pp = obj2gco(uv);
  uv->u.l.prev = &g->uvhead;  /* double link it in `uvhead' list */
  uv->u.l.next = g->uvhead.u.l.next;
  uv->u.l.next->u.l.prev = uv;
  g->uvhead.u.l.next = uv;
  lua_assert(uv->u.l.next->u.l.prev == uv && uv->u.l.prev->u.l.next == uv);
  return uv;
}
{{< /highlight >}}


<div class="src-block-caption">
  <span class="src-block-number">Code Snippet 22</span>:
  lfunc.c
</div>

其中 closure 之后的 move 指令，意味着 upval 处于 open 状态，upvale 需要去链接到栈。
而 getupval 指令，就直接引用上层 closure 相应的 upval 指向的地址就好。

L->openupval 是一个单向链表，其中链接着所有 open 状态的 upval，按栈的高地址到低地址的顺序排列。

注意 line 71 72，pp 是 &p->next，当 `*pp = obj2gco(uv)`  的时候，修改了 next 指针的值，
得以将新的 upval 插入到链表中。

至于 close 操作也不难理解， `luaF_close` 将所有高于 level 栈地址的 open upval 全部变成 close 状态，
即修改 v 指针指向自身，并从 L->openupval 中脱离。

{{< highlight C "linenos=table, linenostart=96" >}}
void luaF_close (lua_State *L, StkId level) {
  UpVal *uv;
  global_State *g = G(L);
  while (L->openupval != NULL && (uv = ngcotouv(L->openupval))->v >= level) {
    GCObject *o = obj2gco(uv);
    lua_assert(!isblack(o) && uv->v != &uv->u.value);
    L->openupval = uv->next;  /* remove from `open' list */
    if (isdead(g, o))
      luaF_freeupval(L, uv);  /* free upvalue */
    else {
      unlinkupval(uv);
      setobj(L, &uv->u.value, uv->v);
      uv->v = &uv->u.value;  /* now current value lives here */
      luaC_linkupval(L, uv);  /* link upvalue into `gcroot' list */
    }
  }
}
{{< /highlight >}}


<div class="src-block-caption">
  <span class="src-block-number">Code Snippet 23</span>:
  lfunc.c
</div>


## practice {#practice}

上面只提到了和 closure 相关的字节码逻辑，读者可以自行输入其它 lua 代码示例，
探索其它字节码的实现。

| 文件    | 建议 |
|-------|----|
| lvm.h   | 仔细阅读 |
| lvm.h   | 仔细阅读 |
| lfunc.h | 仔细阅读 |
| lfunc.c | 仔细阅读 |
