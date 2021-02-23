---
title: "generator"
author: ["DreamAndDead"]
date: 2021-01-08T11:34:00+08:00
lastmod: 2021-02-23T11:59:20+08:00
draft: false
---

上一章尝试单独解析语法分析过程，本章关注具体的代码生成过程。

{{< figure src="generator-feature.png" >}}


## function vs proto vs closure {#function-vs-proto-vs-closure}

在具体深入代码生成之前，先来区分三个概念，function proto 和 closure。

function，是 lua 语言中定义的概念，是 8 种基础类型之一，表示函数，
具体在 lua 代码中用关键字 `function` 来定义。

如同 string 概念在底层由 TString 结构来实现一样，
function 在底层用 Proto 结构来实现，是 function 整体编译之后得到的同语义结构。

编译得到的 Proto 是静态的，在实际运行的时候，需要封装为 Closure 结构，交由 vm 来执行。
Closure 为 upvalue 分配了空间，并统一表示了 c function 和 lua function。

这也是为什么在 object 章节，提到基础类型对应的实现结构时，用 Closure 而不是用 Proto 来表示 function。

所以在编译时期，我们关注 Proto，而在运行时期，才关注 Closure。


### chunk {#chunk}

lua 内部使用了一种巧妙的实现，在编译时，将整个文件当做一个匿名 function 来对待。
相当于文件头加了 `function ()` ，文件尾加了 `end` 。

{{< highlight c "linenos=table, linenostart=383" >}}
Proto *luaY_parser (lua_State *L, ZIO *z, Mbuffer *buff, const char *name) {
  struct LexState lexstate;
  struct FuncState funcstate;
  lexstate.buff = buff;
  luaX_setinput(L, &lexstate, z, luaS_new(L, name));
  open_func(&lexstate, &funcstate);
  funcstate.f->is_vararg = VARARG_ISVARARG;  /* main func. is always vararg */
  luaX_next(&lexstate);  /* read first token */
  chunk(&lexstate);
  check(&lexstate, TK_EOS);
  close_func(&lexstate);
  lua_assert(funcstate.prev == NULL);
  lua_assert(funcstate.f->nups == 0);
  lua_assert(lexstate.fs == NULL);
  return funcstate.f;
}
{{< /highlight >}}


<div class="src-block-caption">
  <span class="src-block-number">Code Snippet 1</span>:
  lparser.c
</div>

可以看到， `luaY_parser` 读取文件，最终生成并返回 `Proto *` 。

因为整体分析的入口是 chunk，lua 又将文件当做匿名函数来对待，
这也是很多 lua 书籍中提到 chunk 的原因，表示文件编译得到的结果。


### embeded {#embeded}

如果按照 function 和 Proto 一一对应的关系，会出现函数层级的问题。

比如下面的示例代码，

```lua
function a()
   function b()
   end
end

function c()
   function d()
   end

   function e()
   end
end
```

如果将 lua 代码文件看作 Proto chunk，代码中定义的 a b c d 同样是 function 且编译为 Proto。
但是 function a b c d e 是 lua 代码的一部分，所以其 Proto 也应该被包含在 Proto chunk 中。

lua 内部根据 function 定义的位置，来记录这种包含关系。

{{< figure src="generator-function-level.png" >}}

function a c 直接定义在代码文件（顶层匿名函数）中，
b d e 则直接定义在 a 和 c 中。

{{< figure src="generator-proto-level.png" >}}

Proto 结构中使用 struct Proto \* 数组 p（Line 235）来记录其直接包含的 Proto。

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
  TString **upvalues;  /* upvalue names */
  TString  *source;
  int sizeupvalues;
  int sizek;  /* size of `k' */
  int sizecode;
  int sizelineinfo;
  int sizep;  /* size of `p' */
  int sizelocvars;
  int linedefined;
  int lastlinedefined;
  GCObject *gclist;
  lu_byte nups;  /* number of upvalues */
  lu_byte numparams;
  lu_byte is_vararg;
  lu_byte maxstacksize;
} Proto;
{{< /highlight >}}


<div class="src-block-caption">
  <span class="src-block-number">Code Snippet 2</span>:
  lobject.h
</div>


### FuncState {#funcstate}

在 lua 的语法分析中，function 解析是一个重要的部分。

EBNF 和 regex 的区别在于，EBNF 可以描述一种递归过程，而 regex 则不能。

chunk 作为解析 function 的入口，得到 Proto，这个过程在遇到 function 定义时，不断的递归调用，生成 Proto，
并按照层级链接起来。

在了解这个过程之前，要先介绍另一个重要的结构 FuncState 。

{{< highlight c "linenos=table, linenostart=57" >}}
/* state needed to generate code for a given function */
typedef struct FuncState {
  Proto *f;  /* current function header */
  Table *h;  /* table to find (and reuse) elements in `k' */
  struct FuncState *prev;  /* enclosing function */
  struct LexState *ls;  /* lexical state */
  struct lua_State *L;  /* copy of the Lua state */
  struct BlockCnt *bl;  /* chain of current blocks */
  int pc;  /* next position to code (equivalent to `ncode') */
  int lasttarget;   /* `pc' of last `jump target' */
  int jpc;  /* list of pending jumps to `pc' */
  int freereg;  /* first free register */
  int nk;  /* number of elements in `k' */
  int np;  /* number of elements in `p' */
  short nlocvars;  /* number of elements in `locvars' */
  lu_byte nactvar;  /* number of active local variables */
  upvaldesc upvalues[LUAI_MAXUPVALUES];  /* upvalues */
  unsigned short actvar[LUAI_MAXVARS];  /* declared-variable stack */
} FuncState;
{{< /highlight >}}


<div class="src-block-caption">
  <span class="src-block-number">Code Snippet 3</span>:
  lparser.h
</div>

从名称可以看出，和 LexState 相似，也用于记录中间状态。
FuncState 用于记录 function 分析过程中的状态，和 function 定义一一对应，
每遇到一个 function 定义时，lua 都会新建一个 FuncState，记录当下解析 function 的中间状态。


### big picture {#big-picture}

LexState FuncState Proto 这三者在分析过程中协同生成最终的 Proto。

比如解析如下示例代码，

{{< highlight lua "linenos=table, linenostart=1" >}}
function a()
   function b()
   end
end
{{< /highlight >}}

在整体文件分析开始之前，parser 已经准备好 FuncState，通过 LexState.ls 索引，
FuncState.f 指向相应要生成的 Proto。

{{< figure src="generator-big-picture-0.png" >}}

解析第 1 行之后，需要函数定义 a，parser 生成新的 FuncState，并更新 ls.fs 的指向。
同时，fs a 通过 prev 指向 fs chunk，表示层级关系。

{{< figure src="generator-big-picture-1.png" >}}

第 2 行，遇到函数 b 定义，同样的，生成 FuncState 并更新 ls.fs 的指向。

{{< figure src="generator-big-picture-2.png" >}}

第 3 行，函数 b 定义结束，此时 ls.fs 指向 fs b 的 prev，回到上个函数定义层级。
并将函数 b 生成的 Proto 链接到上层函数 a 的 Proto。

此时，fs b 已经结束其作用。

{{< figure src="generator-big-picture-3.png" >}}

{{< figure src="generator-big-picture-4.png" >}}

第 4 行，函数 a 定义结束，同上，更新 ls.fs 指向，并链接 Proto a 到 Proto chunk。

{{< figure src="generator-big-picture-5.png" >}}

最终返回 Proto chunk，ls 和 fs 都已经结束其使命，毕竟它们的作用只用于记录中间状态

在 parser 内部，上面描述的过程发生在 `open_func() close_func()` 中，读者可仔细体会其细节。

{{< highlight c "linenos=table, linenostart=328" >}}
static void open_func (LexState *ls, FuncState *fs) {
  lua_State *L = ls->L;
  Proto *f = luaF_newproto(L);
  fs->f = f;
  fs->prev = ls->fs;  /* linked list of funcstates */
  fs->ls = ls;
  fs->L = L;
  ls->fs = fs;
  fs->pc = 0;
  fs->lasttarget = -1;
  fs->jpc = NO_JUMP;
  fs->freereg = 0;
  fs->nk = 0;
  fs->np = 0;
  fs->nlocvars = 0;
  fs->nactvar = 0;
  fs->bl = NULL;
  f->source = ls->source;
  f->maxstacksize = 2;  /* registers 0/1 are always valid */
  fs->h = luaH_new(L, 0, 0);
  /* anchor table of constants and prototype (to avoid being collected) */
  sethvalue2s(L, L->top, fs->h);
  incr_top(L);
  setptvalue2s(L, L->top, f);
  incr_top(L);
}


static void close_func (LexState *ls) {
  lua_State *L = ls->L;
  FuncState *fs = ls->fs;
  Proto *f = fs->f;
  removevars(ls, 0);
  luaK_ret(fs, 0, 0);  /* final return */
  luaM_reallocvector(L, f->code, f->sizecode, fs->pc, Instruction);
  f->sizecode = fs->pc;
  luaM_reallocvector(L, f->lineinfo, f->sizelineinfo, fs->pc, int);
  f->sizelineinfo = fs->pc;
  luaM_reallocvector(L, f->k, f->sizek, fs->nk, TValue);
  f->sizek = fs->nk;
  luaM_reallocvector(L, f->p, f->sizep, fs->np, Proto *);
  f->sizep = fs->np;
  luaM_reallocvector(L, f->locvars, f->sizelocvars, fs->nlocvars, LocVar);
  f->sizelocvars = fs->nlocvars;
  luaM_reallocvector(L, f->upvalues, f->sizeupvalues, f->nups, TString *);
  f->sizeupvalues = f->nups;
  lua_assert(luaG_checkcode(f));
  lua_assert(fs->bl == NULL);
  ls->fs = fs->prev;
  /* last token read was anchored in defunct function; must reanchor it */
  if (fs) anchor_token(ls);
  L->top -= 2;  /* remove table and prototype from the stack */
}
{{< /highlight >}}


<div class="src-block-caption">
  <span class="src-block-number">Code Snippet 4</span>:
  lparser.c
</div>


### FuncState vs Proto {#funcstate-vs-proto}

FuncState 和 Proto 作为分析过程中两个最重要的结构，值得详细做一番了解。

仔细观察两个结构内部的字段，会发现两者之间有紧密的联系，界限很模糊，
都些许记录了分析过程的结果。
关键的差异在于，Proto 只保留最终结果，而 FuncState 记录中间状态。

对应这个原则，来详细探究下两个结构的内部。

先来看 Proto。

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
  TString **upvalues;  /* upvalue names */
  TString  *source;
  int sizeupvalues;
  int sizek;  /* size of `k' */
  int sizecode;
  int sizelineinfo;
  int sizep;  /* size of `p' */
  int sizelocvars;
  int linedefined;
  int lastlinedefined;
  GCObject *gclist;
  lu_byte nups;  /* number of upvalues */
  lu_byte numparams;
  lu_byte is_vararg;
  lu_byte maxstacksize;
} Proto;
{{< /highlight >}}


<div class="src-block-caption">
  <span class="src-block-number">Code Snippet 5</span>:
  lobject.h
</div>

其中字段分为 3 部分来看

暂不讨论

-   `int *lineinfo`
-   `TString *source`
-   `int linedefined`
-   `int lastlinedefined`
-   `GCObject *gclist`

元信息

-   `lu_byte numparams` ，函数的固定参数个数
-   `lu_byte is_vararg` ，函数的可变参数
-   `lu_byte maxstacksize` ，函数运行时，最大使用的栈空间

数组结果

-   `TValue *k` ，常量表
-   `Instruction *code` ，字节码
-   `struct Proto **p` ，内部其它函数定义
-   `struct LocVar *locvars` ，局部变量信息
-   `TString **upvalues` ，upvalue 信息
-   与 len size 相关的字段

对照之前对 vm 执行模型的讨论，code 和 k 就与之对应。

这里一个有意思的区别，在于 size 和 n。

上面提到的 5 个数组，都对应一个 size 字段，用于记录数组的大小。
同时，也对应一个 n 字段，用于记录当前数组已使用的大小（下一个空闲的位置）。

在分析的过程中，数组 size 值记录空间总长度，当空间不足时，会继续扩大分配。
而数组 n 值用于时刻标识下一个空闲索引，记录分析结果并自增，它的值比 size 小。

当最终分析结束时，将 n 值赋值给相应的 size 值，省略多余不用的空间，此时两者才会相同。

如此看来，n 值应该存放在 FuncState 中，但是存在例外的是 `lu_byte nups` 。

{{< figure src="generator-fcode.png" >}}

{{< figure src="generator-fk.png" >}}

{{< figure src="generator-fp.png" >}}

{{< figure src="generator-fupval.png" >}}

{{< figure src="generator-flocvars.png" >}}

相同的视角，来观察 FuncState。

{{< highlight c "linenos=table, linenostart=57" >}}
/* state needed to generate code for a given function */
typedef struct FuncState {
  Proto *f;  /* current function header */
  Table *h;  /* table to find (and reuse) elements in `k' */
  struct FuncState *prev;  /* enclosing function */
  struct LexState *ls;  /* lexical state */
  struct lua_State *L;  /* copy of the Lua state */
  struct BlockCnt *bl;  /* chain of current blocks */
  int pc;  /* next position to code (equivalent to `ncode') */
  int lasttarget;   /* `pc' of last `jump target' */
  int jpc;  /* list of pending jumps to `pc' */
  int freereg;  /* first free register */
  int nk;  /* number of elements in `k' */
  int np;  /* number of elements in `p' */
  short nlocvars;  /* number of elements in `locvars' */
  lu_byte nactvar;  /* number of active local variables */
  upvaldesc upvalues[LUAI_MAXUPVALUES];  /* upvalues */
  unsigned short actvar[LUAI_MAXVARS];  /* declared-variable stack */
} FuncState;
{{< /highlight >}}


<div class="src-block-caption">
  <span class="src-block-number">Code Snippet 6</span>:
  lparser.h
</div>

暂不讨论

-   `Proto *f`
-   `struct FuncState *prev`
-   `struct LexState *ls`
-   `struct lua_State *L`

后续讨论

-   `struct BlockCnt *bl`
-   `int lasttarget`
-   `int jpc`
-   `int freereg`

中间结果

-   `upvaldesc upvalues[LUAI_MAXUPVALUES]`
-   `unsigned short actvar[LUAI_MAXVARS]`
-   其它 n 字段

两个数组是定长的，即 size 是固定的， `f->nups` `fs->nactvar` 用于对应其 n 字段。

{{< figure src="generator-fsupval.png" >}}

{{< figure src="generator-fsactvar.png" >}}

在编译过程中，所得到的结果会不断的存储入上述数组及其它字段中。


## generate {#generate}

从某种角度看，编译过程就是规则间的同义转换过程。

代码生成，最终将符合语法规则的 lua 代码，生成为 vm 可执行的同义字节码，
这个过程是隐藏在语法分析下的艺术。

两个规则间可以进行同义转换的连接点，在于对 vm 的共识，
正因为编译器"懂得" vm，知晓字节码的格式与功能，知晓运行时的栈结构，
知晓 k 表 Gbl 表的读取方式，才能生成 vm 可执行的同义字节码。

这种共识贯穿在整个代码生成的过程中。

但是无论编译器如何了解 vm，编译时和运行时还是存在区别的。
代码生成时，只是想象存在一个假想的 vm，它在执行生成的所有结果。

所以代码生成这个过程是最为繁杂的，到 vm 真正运行时反而轻松了，只需要读指令，执行指令就可以了。

阅读代码生成相关的代码，笔者还没有精确地把握住其中的原理，只能提供几个原则给读者参考，

-   总体是语法制导翻译的过程
-   使用后缀方式的生成顺序，比如 a + b 按照 a b + 的顺序来转换生成
-   精确模拟 vm 的运行方式，包括栈运算，Gbl 表及其它

章节结束之后，读者可以多使用调试器分析示例代码，探索其中的奥妙。


## key concept {#key-concept}

在仔细探索代码生成之前，先明确几个在生成过程中的重点。


### variable {#variable}

从作用域来看，lua 中的变量有 3 类，分别为 `local upvalue global` ，
三者在底层的实现方式各不相同。


#### local {#local}

local 变量的活动范围（active），开始于在作用域中出现的那一刻，一直到作用域结束，
而作用域是有明显的栈特性的，新开辟作用域时入栈，离开作用域时出栈。

在一个作用域内，local 变量按照声明顺序入栈，离开作用域时全部出栈，变为 inactive 状态。

利用这个特性，lua 在编译时，在 fs 中用 actvar 和 nactvar 时刻记录着当前 active local 变量的状态。

比如如下示例代码，

```lua
local a

do
   local b
   do
      local c
   end
end

do
   local d
   do
      local e
   end
end
```

在代码分析的不同时刻， `fs->actvar` 记录的栈状态是这样的，

{{< figure src="generator-active-local-scope.png" >}}

上面只是粗略描述了 active local 变量的栈状态，而实际在 parser 内部，是通过两个数组来存储的。

{{< figure src="generator-actvar-locvars.png" >}}

数组 `fs->actvar` 的元素是 `unsigned short` 类型，只用来记录变量的索引。
索引数组 `f->locvars` 中的元素，其中元素类型为 `struct LocVar *` 。

{{< highlight c "linenos=table, linenostart=262" >}}
typedef struct LocVar {
  TString *varname;
  int startpc;  /* first point where variable is active */
  int endpc;    /* first point where variable is dead */
} LocVar;
{{< /highlight >}}


<div class="src-block-caption">
  <span class="src-block-number">Code Snippet 7</span>:
  lobject.h
</div>

LocVar 主要记录变量的名字， `startpc endpc` 在字节码层面记录其活动范围。

宏 getlocvar 精确描述了图示过程。

{{< highlight c "linenos=table, linenostart=32" >}}
#define getlocvar(fs, i)	((fs)->f->locvars[(fs)->actvar[i]])
{{< /highlight >}}


<div class="src-block-caption">
  <span class="src-block-number">Code Snippet 8</span>:
  lparser.c
</div>


#### upvalue {#upvalue}

upvalue 在本文翻译为上值，它即非 local，又不是 global。
直观从代码上看，即引用作用域之外的变量。

lua 将 function 作为基础类型之一，可以作为普通变量，参数，返回值，赋值，而四处流转。
又因为 local 变量的作用域限定于词法，这便是 upvalue 机制发挥作用的地方。

如下示例代码，

```lua
local function outer()
   local a = 0

   local function inner()
      a = a + 1
      print(a)
   end

   inner()

   return inner
end

local f = outer()

f()
f()
```

```text
1
2
3
```

内部第 1 次调用 inner() 时，输出 1 。
当调用 outer()，将 inner 赋值与 f，调用两次 f() 得到 2 3 。

第 1 次调用 inner() 时，依然在 a 的作用域内，输出 1 是符合直觉的。

问题在于调用 f() 时，因为 a 只作用在 outer 的作用域，而 f 在 outer 作用域外部，
已经离开了 a 的作用域，这种情况下为何还可以访问 a ？

这便是闭包机制的由来，a 对于 inner 而言是 upvalue 类型。
这也是 lua 中为何 function 不是 function 而是 closure 的原因，function 及 upvalue 组成了 closure，
所有 func 在运行时都封装为 closure 来运行，其中重要的原因就在于单独分配 upvalue 空间并管理。

详细的说，第 1 次调用 inner() 时，local a 依然存活，称 upvalue a 为 open 状态。
当离开 outer() 作用域，upvalue a 为 close 状态。


#### global {#global}

如果依然说，global 变量是除 local 变量和 upvalue 变量的变量，读者肯定不信服。

之所以存在 upvalue 和 global，隐含的一点是，在 lua 中外层变量对于内层是可见的，
既然是可见的，对于外层变量引用自然有一个查找的过程，变量类型正是在查找的过程中确定的。

-   在当前作用域中可以找到的，为 local 类型
-   在当前作用域之外的作用域可以找到的，为 upvalue 类型
-   所有作用域都无法找到的，为 global 类型

按照这个逻辑，顶层的 chunk 是没有 upvalue 的，在当前作用域中查找不到的变量，
只能是 global 类型。

setfenv 影响的就是函数的 global 环境，
设定不同的 global 表，可以影响内部对 global 的引用，
实现不同的运行效果，类似于封装成一个小沙盒，

比如如下代码，变量 a 对 outer inner 都是全局变量，所以全部修改都影响到 global a 的值。

```lua
local function outer()
  a = 10

  local function inner()
    a = a + 1
    return a
  end

  return inner
end

local f = outer()

print(f(), a)
print(f(), a)
print(f(), a)
```

```text
11	11
12	12
13	13
```


### register {#register}

寄存器的主要作用是，存取 local 变量和存取中间结果。

寄存器在编译时是一个抽象的概念，没有具体的分配空间，编译器只知晓存在这块区域，
并且按照自己的需要来使用和调试。

而在实际运行时，寄存器存储在 vm 的栈中。


## statement {#statement}

本节开始从实例具体分析代码生成的过程，和实例一起来探求其中的生成模式。

因为语法元素的递归性，其中的组合是无限的，所以本节只挑选讲解部分重要的“原子性”的部分，
至于各种组合的变数读者可自由探索。


### tool {#tool}

在开始以实例为基础的探索之前，先详细介绍相应工具的使用。

以交互式启动 chunkspy，用于临时检验一些想法。

```text
$ make spy
```

分析特定 lua 文件，输出相应的编译结果。

```text
$ make -s inspect source=lua_file_path
```

比如分析如下代码，

```lua
local a = 1
```

会输出如下结果，

{{< highlight text "linenos=table, linenostart=1">}}
; function [0] definition (level 1)
; 0 upvalues, 0 params, 2 is_vararg, 2 stacks
.function  0 0 2 2
.local  "a"  ; 0
.const  1  ; 0
[1] loadk      0   0        ; 1
[2] return     0   1
; end of function
{{< /highlight >}}

逐行来看，

line 1

level 1 指的是第一层级，即 chunk；
function [0] 表明是当前层级的第 1 个函数（以 0 开始索引）

line 2

函数有 0 个 upvalue，0 个参数，按 `0b010` 模式接收可变参数，需要分配栈容量 2。

line 3

意义和 line 2 相同，line 2 是 line 3 的注释

line 4 5

.local 列出所有局部变量的名称及索引，即 f->locvars 的内容
.const 列出 k 表的内容及索引

line 6 7

详细打印 f->code 指令，最终一行总是默认生成一条 return 指令

line 8

注释，表明 function 结束

读者结合 opcode 章节对各个指令功能的理解，不难理解 lua 代码和字节码的同义关系。


### local {#local}

先来观察 local 语句。

语法描述如下，

```bnf
stat      ::= localstat
localstat ::= LOCAL NAME {`,' NAME} [`=' explist]
localstat ::= LOCAL FUNCTION NAME body
```

localstat 可用于定义局部变量和局部函数。

函数部分到后面小节再讨论，对于局部变量，根据是否赋值可分为两种情况。


#### no assignment {#no-assignment}

如下简单的代码示例，定义局部变量，无赋值，

```lua
local a, b, c
```

分析得到如下结果，

```text
; function [0] definition (level 1)
; 0 upvalues, 0 params, 2 is_vararg, 3 stacks
.function  0 0 2 3
.local  "a"  ; 0
.local  "b"  ; 1
.local  "c"  ; 2
[1] return     0   1
; end of function
```

示例代码只是单纯进行了局部变量的声明，最终没有生成任何字节码。

分析的过程，就是递归向下的函数过程， `chunk -> stat -> localstat` 。

{{< highlight C "linenos=table, linenostart=1179" >}}
static void localstat (LexState *ls) {
  /* stat -> LOCAL NAME {`,' NAME} [`=' explist1] */
  int nvars = 0;
  int nexps;
  expdesc e;
  do {
    new_localvar(ls, str_checkname(ls), nvars++);
  } while (testnext(ls, ','));
  if (testnext(ls, '='))
    nexps = explist1(ls, &e);
  else {
    e.k = VVOID;
    nexps = 0;
  }
  adjust_assign(ls, nvars, nexps, &e);
  adjustlocalvars(ls, nvars);
}
{{< /highlight >}}


<div class="src-block-caption">
  <span class="src-block-number">Code Snippet 9</span>:
  lparser.c
</div>

关键在于 new\_localvar 函数，在循环中读入 a b c，并进行变量分析。

{{< highlight C "linenos=table, linenostart=160" >}}
static void new_localvar (LexState *ls, TString *name, int n) {
  FuncState *fs = ls->fs;
  luaY_checklimit(fs, fs->nactvar+n+1, LUAI_MAXVARS, "local variables");
  fs->actvar[fs->nactvar+n] = cast(unsigned short, registerlocalvar(ls, name));
}
{{< /highlight >}}


<div class="src-block-caption">
  <span class="src-block-number">Code Snippet 10</span>:
  lparser.c
</div>

{{< highlight C "linenos=table, linenostart=143" >}}
static int registerlocalvar (LexState *ls, TString *varname) {
  FuncState *fs = ls->fs;
  Proto *f = fs->f;
  int oldsize = f->sizelocvars;
  luaM_growvector(ls->L, f->locvars, fs->nlocvars, f->sizelocvars,
		  LocVar, SHRT_MAX, "too many local variables");
  while (oldsize < f->sizelocvars) f->locvars[oldsize++].varname = NULL;
  f->locvars[fs->nlocvars].varname = varname;
  luaC_objbarrier(ls->L, f, varname);
  return fs->nlocvars++;
}
{{< /highlight >}}


<div class="src-block-caption">
  <span class="src-block-number">Code Snippet 11</span>:
  lparser.c
</div>

其中根据变量出现的顺序，依次使用 registerlocalvar 得到变量索引，再记录到 `fs->actvar` 中。

这就是前面讨论过的，局部变量的存储方式，使用 `fs->actvar` 记录索引， `f->locvars` 记录变量名称。

{{< figure src="generator-local-no-assign.png" >}}

new\_locvar 完成的就是这个过程。

这也对应了 chunkspy 分析结果中的 .local 部分。


#### with assignment {#with-assignment}

再来看 local 变量赋值的情况。

分析示例代码，得到如下结果，

```lua
local a, b, c, d, e = 10, "second", nil, true, false
```

```text
; function [0] definition (level 1)
; 0 upvalues, 0 params, 2 is_vararg, 5 stacks
.function  0 0 2 5
.local  "a"  ; 0
.local  "b"  ; 1
.local  "c"  ; 2
.local  "d"  ; 3
.local  "e"  ; 4
.const  10  ; 0
.const  "second"  ; 1
[1] loadk      0   0        ; 10
[2] loadk      1   1        ; "second"
[3] loadnil    2   2
[4] loadbool   3   1   0    ; true
[5] loadbool   4   0   0    ; false
[6] return     0   1
; end of function
```

除了 .local 条目变多了，也增加了 .const 部分，意味着 k 表多出了 2 项记录。

依旧从 localstat 来分析，

{{< highlight C "linenos=table, linenostart=1179" >}}
static void localstat (LexState *ls) {
  /* stat -> LOCAL NAME {`,' NAME} [`=' explist1] */
  int nvars = 0;
  int nexps;
  expdesc e;
  do {
    new_localvar(ls, str_checkname(ls), nvars++);
  } while (testnext(ls, ','));
  if (testnext(ls, '='))
    nexps = explist1(ls, &e);
  else {
    e.k = VVOID;
    nexps = 0;
  }
  adjust_assign(ls, nvars, nexps, &e);
  adjustlocalvars(ls, nvars);
}
{{< /highlight >}}


<div class="src-block-caption">
  <span class="src-block-number">Code Snippet 12</span>:
  lparser.c
</div>

在记录变量信息之后，遇到 `=` ，开始分析 `=` 后的 表达式列表 ，作为变量的赋值内容。

后面的表达式都是简单表达式，最终会调用 simpleexp 进行解析。

```bnf
explist      ::= expr {`,' expr}
expr         ::= subexpr
subexpr      ::= (simpleexp | unop subexpr) {binop subexpr}

simpleexp    ::= NUMBER | STRING | NIL | TRUE | FALSE | DOTS |
		 constructor | FUNCTION body | primaryexp
```

下面有趣的地方来了，字节码和 k 表中的元素是何时生成的？
这就和代码生成的方式紧密相关了。

parser 模块中代码生成的强大在于，它是流式生成的。
意思即一边读入 token，分析状态，就直接生成代码！

从代码具体来看，

{{< highlight C "linenos=table, linenostart=596" >}}
static int explist1 (LexState *ls, expdesc *v) {
  /* explist1 -> expr { `,' expr } */
  int n = 1;  /* at least one expression */
  expr(ls, v);
  while (testnext(ls, ',')) {
    luaK_exp2nextreg(ls->fs, v);
    expr(ls, v);
    n++;
  }
  return n;
}
{{< /highlight >}}

在第 1 次分析表达式 时，读入并分析了 10，并在 第 2 次分析表达式 "second" 之前，已经生成代码并更新了 k 表。

先来看 expr()，由于分析的是简单表达式，最终会调用 simpleexp 进行分析，

{{< highlight C "linenos=table, linenostart=727" >}}
static void simpleexp (LexState *ls, expdesc *v) {
  /* simpleexp -> NUMBER | STRING | NIL | true | false | ... |
		  constructor | FUNCTION body | primaryexp */
  switch (ls->t.token) {
    case TK_NUMBER: {
      init_exp(v, VKNUM, 0);
      v->u.nval = ls->t.seminfo.r;
      break;
    }
    case TK_STRING: {
      codestring(ls, v, ls->t.seminfo.ts);
      break;
    }
    case TK_NIL: {
      init_exp(v, VNIL, 0);
      break;
    }
    case TK_TRUE: {
      init_exp(v, VTRUE, 0);
      break;
    }
    case TK_FALSE: {
      init_exp(v, VFALSE, 0);
      break;
    }
    case TK_DOTS: {  /* vararg */
      FuncState *fs = ls->fs;
      check_condition(ls, fs->f->is_vararg,
		      "cannot use " LUA_QL("...") " outside a vararg function");
      fs->f->is_vararg &= ~VARARG_NEEDSARG;  /* don't need 'arg' */
      init_exp(v, VVARARG, luaK_codeABC(fs, OP_VARARG, 0, 1, 0));
      break;
    }
    case '{': {  /* constructor */
      constructor(ls, v);
      return;
    }
    case TK_FUNCTION: {
      luaX_next(ls);
      body(ls, v, 0, ls->linenumber);
      return;
    }
    default: {
      primaryexp(ls, v);
      return;
    }
  }
  luaX_next(ls);
}
{{< /highlight >}}

第 1 次分析 10 时，token 类型是 `TK_NUMBER` ，直接填充 expdesc 即可，
然后调用 luaK\_exp2nextreg 生成代码。

luaK\_exp2nextreg 是一个综合过程，由更基础的几个函数组成。

深入分析之前，先来补充之前 FuncState 未描述的一个字段，freereg。

字节码被 vm 运行时，vm 维持一个栈，来存放寄存器和中间结果。
编译器只知晓这个栈的存在，但是在编译时，这个栈并没有真实存在，
只能凭借想象去操作它。

freereg 就是用来记录栈顶的变量。

当存储新的寄存器值时，freereg 就会自增，为寄存器开出空间；

{{< highlight c "linenos=table, linenostart=209" >}}
void luaK_reserveregs (FuncState *fs, int n) {
  luaK_checkstack(fs, n);
  fs->freereg += n;
}
{{< /highlight >}}


<div class="src-block-caption">
  <span class="src-block-number">Code Snippet 13</span>:
  lcode.c
</div>

相应的，如果寄存器不再使用，freereg 会自减，回收相应的空间。

{{< highlight c "linenos=table, linenostart=215" >}}
static void freereg (FuncState *fs, int reg) {
  if (!ISK(reg) && reg >= fs->nactvar) {
    fs->freereg--;
    lua_assert(reg == fs->freereg);
  }
}
{{< /highlight >}}


<div class="src-block-caption">
  <span class="src-block-number">Code Snippet 14</span>:
  lcode.c
</div>

从中可以看出，freereg 将栈分为两部分，在栈底为 local 变量保留空间（reg >= fs->nactvar），
上层用于计算中间结果。

{{< figure src="generator-freereg-stack.png" >}}

{{< highlight c "linenos=table, linenostart=414" >}}
void luaK_exp2nextreg (FuncState *fs, expdesc *e) {
  luaK_dischargevars(fs, e);
  freeexp(fs, e);
  luaK_reserveregs(fs, 1);
  exp2reg(fs, e, fs->freereg - 1);
}
{{< /highlight >}}


<div class="src-block-caption">
  <span class="src-block-number">Code Snippet 15</span>:
  lcode.c
</div>

在 luaK\_exp2nextreg 中，先找出下一个可用的栈/寄存器空间，然后将表达式的值解析到寄存器中，
即生成字节码。

最终在 discharge2reg 函数生成相应指令 loadk。

这里出现了第二个重点，对 k 表的操作。

因为其类型为数字，所以调用的是 luaK\_numberK。

{{< highlight c "linenos=table, linenostart=229" >}}
static int addk (FuncState *fs, TValue *k, TValue *v) {
  lua_State *L = fs->L;
  TValue *idx = luaH_set(L, fs->h, k);
  Proto *f = fs->f;
  int oldsize = f->sizek;
  if (ttisnumber(idx)) {
    lua_assert(luaO_rawequalObj(&fs->f->k[cast_int(nvalue(idx))], v));
    return cast_int(nvalue(idx));
  }
  else {  /* constant not found; create a new entry */
    setnvalue(idx, cast_num(fs->nk));
    luaM_growvector(L, f->k, fs->nk, f->sizek, TValue,
		    MAXARG_Bx, "constant table overflow");
    while (oldsize < f->sizek) setnilvalue(&f->k[oldsize++]);
    setobj(L, &f->k[fs->nk], v);
    luaC_barrier(L, f, v);
    return fs->nk++;
  }
}


int luaK_stringK (FuncState *fs, TString *s) {
  TValue o;
  setsvalue(fs->L, &o, s);
  return addk(fs, &o, &o);
}


int luaK_numberK (FuncState *fs, lua_Number r) {
  TValue o;
  setnvalue(&o, r);
  return addk(fs, &o, &o);
}


static int boolK (FuncState *fs, int b) {
  TValue o;
  setbvalue(&o, b);
  return addk(fs, &o, &o);
}


static int nilK (FuncState *fs) {
  TValue k, v;
  setnilvalue(&v);
  /* cannot use nil as key; instead use table itself to represent nil */
  sethvalue(fs->L, &k, fs->h);
  return addk(fs, &k, &v);
}
{{< /highlight >}}


<div class="src-block-caption">
  <span class="src-block-number">Code Snippet 16</span>:
  lcode.c
</div>

所有操作 k 表的方法，最终都使用 addk 操作，其作用也很简单，
在 k 表中搜索，如果存在，则直接返回相应索引，其中使用 table fs->h 做 k 表元素的反向索引，加快搜索过程；
若不存在，则自增，并返回相应的索引。

{{< figure src="generator-numberk-10.png" >}}

将数字 10 存储入 k 表之后，生成 loadk 指令，将 freereg 和 k 索引作为其操作数。

至此，parser 只读入了 token 10，便已经完成了操作 k 表，记录常数，并生成对应的指令，令人惊奇。

对于第 2 个表达式 "second"，在 simpleexp 时，提前调用 codestring 加入了 k 表，
将其作为 VK 类型来对待。

{{< highlight c "linenos=table, linenostart=133" >}}
static void codestring (LexState *ls, expdesc *e, TString *s) {
  init_exp(e, VK, luaK_stringK(ls->fs, s));
}
{{< /highlight >}}


<div class="src-block-caption">
  <span class="src-block-number">Code Snippet 17</span>:
  lparser.c
</div>

{{< figure src="generator-stringk-second.png" >}}

同样的生成 loadk 指令。

回到 localstat()，前面对变量和表达式进行解析之后，记录了 `=` 两边的数量 nvars nexps，
`adjust_assign()` 进行左右数量的调整，多余的 var 空间置为 nil，多余的 exp 则省略。

最终调用 `adjustlocalvars()` 调整 fs->nactvar 的值。


### expdesc {#expdesc}

从 localstat 的示例中，已经看到代码生成的逻辑是别具一格的。

结合递归下降，语法制导，后缀顺序，vm opcode 语义，得以以线性顺序生成字节码。

其中 expdesc 的作用是非常重要的，将一些属性附加到文法符号上，辅助代码生成过程。

```c
/*
** Expression descriptor
*/

typedef enum {
  VVOID,	/* no value */
  VNIL,
  VTRUE,
  VFALSE,
  VK,		/* info = index of constant in `k' */
  VKNUM,	/* nval = numerical value */
  VLOCAL,	/* info = local register */
  VUPVAL,       /* info = index of upvalue in `upvalues' */
  VGLOBAL,	/* info = index of table; aux = index of global name in `k' */
  VINDEXED,	/* info = table register; aux = index register (or `k') */
  VJMP,		/* info = instruction pc */
  VRELOCABLE,	/* info = instruction pc */
  VNONRELOC,	/* info = result register */
  VCALL,	/* info = instruction pc */
  VVARARG	/* info = instruction pc */
} expkind;

typedef struct expdesc {
  expkind k;
  union {
    struct { int info, aux; } s;
    lua_Number nval;
  } u;
  int t;  /* patch list of `exit when true' */
  int f;  /* patch list of `exit when false' */
} expdesc;
```

<div class="src-block-caption">
  <span class="src-block-number">Code Snippet 18</span>:
  lparser.h
</div>

expdesc 用于记录 exp 表达式的相关信息。

和 token 类型类似，expdesc 内部有字段记录类型，其它字段记录附加信息。

所有类型用 enum expkind 表示，相应类型后的注释描述了对应其它字段需要记录的信息。

其中重点的函数是 discharge2reg 和 dischargevars，用于解析相应的 expdesc，生成代码并更新状态。

| expkind    | u                                 | discharge                                  |
|------------|-----------------------------------|--------------------------------------------|
| VVOID      |                                   |                                            |
| VNIL       |                                   | 生成指令 loadnil，重置为 VNONRELOC         |
| VTRUE      |                                   | 生成指令 loadbool，重置为 VNONRELOC        |
| VFALSE     |                                   | 生成指令 loadbool，重置为 VNONRELOC        |
| VK         | info 记录 k 表索引                | 生成指令 loadk，重置为 VNONRELOC           |
| VKNUM      | nval 记录数值                     | 生成指令 loadk，重置为 VNONRELOC           |
| VLOCAL     | info 记录寄存器索引               | 重置为 VNONRELOC                           |
| VUPVAL     | info 记录 upvalues 数组中的索引   | 生成指令 GETUPVAL, 重置为 VRELOCABLE，info 记录指令索引 |
| VGLOBAL    | info 全局表的索引，aux 全局名称的 k 表索引 | 生成指令 GETGLOBAL, 重置为 VRELOCABLE，info 记录指令索引 |
| VINDEXED   | info table 所在寄存器的索引，aux 索引值的 RK 值 | 生成指令 GETTABLE, 重置为 VRELOCABLE，info 记录指令索引 |
| VJMP       | info 当前指令索引                 |                                            |
| VRELOCABLE | info 当前指令索引                 | 定位到指令位置，修改 A 参数为 reg          |
| VNONRELOC  | info 最终解析得到的寄存器位置     | 如果当前寄存器位置与目标位置不同，则生成 move 指令；相同则什么都不做 |
| VCALL      | info 当前指令索引                 | 重置为 VNONRELOC，info 记录指令的 A 参数   |
| VVARARG    | info 当前指令索引                 | 重置为 VRELOCABLE                          |

具体如此设计的原因及作用，还需要读者在不同情况下再尝试领会。


### assign {#assign}

本节来探讨赋值语句

```bnf
stat         ::= exprstat
exprstat     ::= assignstat

assignstat   ::= (prefixexp | primaryexp (`.' NAME | `[' expr `]')) assignment
assignment   ::= `,' assignstat | `=' explist

primaryexp   ::= prefixexp {`.' NAME | `[' expr `]' | `:' NAME funcargs | funcargs}
prefixexp    ::= NAME | `(' expr `)'
```

赋值语句根据变量的类型不同，分为 global upvalue local indexed 几种情况，
对应 expdesc 中的 VGLOBAL VUPVAL VLOCAL VINDEXED。


#### global {#global}

先来看 global 的赋值情况。

分析如下代码，

```lua
a, b, c = 10, 20, 30
```

```text
; function [0] definition (level 1)
; 0 upvalues, 0 params, 2 is_vararg, 3 stacks
.function  0 0 2 3
.const  "a"  ; 0
.const  "b"  ; 1
.const  "c"  ; 2
.const  10  ; 3
.const  20  ; 4
.const  30  ; 5
[1] loadk      0   3        ; 10
[2] loadk      1   4        ; 20
[3] loadk      2   5        ; 30
[4] setglobal  2   2        ; c
[5] setglobal  1   1        ; b
[6] setglobal  0   0        ; a
[7] return     0   1
; end of function
```

从 chunk 递归向下，最终到达 assignment 函数。

从 ebnf 描述中可以看出，assignment 是一个递归的过程。

{{< highlight c "linenos=table, linenostart=931" >}}
static void assignment (LexState *ls, struct LHS_assign *lh, int nvars) {
  expdesc e;
  check_condition(ls, VLOCAL <= lh->v.k && lh->v.k <= VINDEXED,
		      "syntax error");
  if (testnext(ls, ',')) {  /* assignment -> `,' primaryexp assignment */
    struct LHS_assign nv;
    nv.prev = lh;
    primaryexp(ls, &nv.v);
    if (nv.v.k == VLOCAL)
      check_conflict(ls, lh, &nv.v);
    luaY_checklimit(ls->fs, nvars, LUAI_MAXCCALLS - ls->L->nCcalls,
		    "variables in assignment");
    assignment(ls, &nv, nvars+1);
  }
  else {  /* assignment -> `=' explist1 */
    int nexps;
    checknext(ls, '=');
    nexps = explist1(ls, &e);
    if (nexps != nvars) {
      adjust_assign(ls, nvars, nexps, &e);
      if (nexps > nvars)
	ls->fs->freereg -= nexps - nvars;  /* remove extra values */
    }
    else {
      luaK_setoneret(ls->fs, &e);  /* close last expression */
      luaK_storevar(ls->fs, &lh->v, &e);
      return;  /* avoid default */
    }
  }
  init_exp(&e, VNONRELOC, ls->fs->freereg-1);  /* default assignment */
  luaK_storevar(ls->fs, &lh->v, &e);
}
{{< /highlight >}}


<div class="src-block-caption">
  <span class="src-block-number">Code Snippet 19</span>:
  lparser.c
</div>

在遇到 `=` 之前，执行 if 语句块，递归调用 primaryexp 分析变量；
遇到 `=` 之后，执行 else 语句块，分析表达式。
在递归的终点，将表达式得到的值赋值给变量。

因为示例代码中变量都很简单，primaryexp 主要调用 prefixexp 进行分析。

{{< highlight c "linenos=table, linenostart=667" >}}
static void prefixexp (LexState *ls, expdesc *v) {
  /* prefixexp -> NAME | '(' expr ')' */
  switch (ls->t.token) {
    case '(': {
      int line = ls->linenumber;
      luaX_next(ls);
      expr(ls, v);
      check_match(ls, ')', '(', line);
      luaK_dischargevars(ls->fs, v);
      return;
    }
    case TK_NAME: {
      singlevar(ls, v);
      return;
    }
    default: {
      luaX_syntaxerror(ls, "unexpected symbol");
      return;
    }
  }
}
{{< /highlight >}}


<div class="src-block-caption">
  <span class="src-block-number">Code Snippet 20</span>:
  lparser.c
</div>

对应其中的 `TK_NAME` 类型，调用 singlevar 确定变量的类型，内容调用 singlevaraux 来实现。

{{< highlight c "linenos=table, linenostart=224" >}}
static int singlevaraux (FuncState *fs, TString *n, expdesc *var, int base) {
  if (fs == NULL) {  /* no more levels? */
    init_exp(var, VGLOBAL, NO_REG);  /* default is global variable */
    return VGLOBAL;
  }
  else {
    int v = searchvar(fs, n);  /* look up at current level */
    if (v >= 0) {
      init_exp(var, VLOCAL, v);
      if (!base)
	markupval(fs, v);  /* local will be used as an upval */
      return VLOCAL;
    }
    else {  /* not found at current level; try upper one */
      if (singlevaraux(fs->prev, n, var, 0) == VGLOBAL)
	return VGLOBAL;
      var->u.s.info = indexupvalue(fs, n, var);  /* else was LOCAL or UPVAL */
      var->k = VUPVAL;  /* upvalue in this level */
      return VUPVAL;
    }
  }
}


static void singlevar (LexState *ls, expdesc *var) {
  TString *varname = str_checkname(ls);
  FuncState *fs = ls->fs;
  if (singlevaraux(fs, varname, var, 1) == VGLOBAL)
    var->u.s.info = luaK_stringK(fs, varname);  /* info points to global name */
}
{{< /highlight >}}


<div class="src-block-caption">
  <span class="src-block-number">Code Snippet 21</span>:
  lparser.c
</div>

singlevaraux 是非常关键的过程，回忆之前在分析过程中，关于嵌套的 function 定义和 fs->prev 的链条，
singlevaraux 就顺着 fs->prev 不断向上层作用域寻找变量。

如果 `fs == NULL` ，说明已经到顶层，变量只能为 global 类型；
如果在当前作用域可找到，说明是 local 变量；其它为 upval 变量。

示例中 a b c 都为全局变量，所以 singlevaraux 返回 VGLOBAL，
将相应 expdesc 类型赋值为 VGLOBAL，且 info 存储了变量名对应的 k 表索引。

表达式分析阶段，将 10 20 30 加入 k 表，同时载入寄存器。

最终赋值阶段，在每个递归层次，用 luaK\_storevar 来存储。

{{< highlight c "linenos=table, linenostart=472" >}}
void luaK_storevar (FuncState *fs, expdesc *var, expdesc *ex) {
  switch (var->k) {
    case VLOCAL: {
      freeexp(fs, ex);
      exp2reg(fs, ex, var->u.s.info);
      return;
    }
    case VUPVAL: {
      int e = luaK_exp2anyreg(fs, ex);
      luaK_codeABC(fs, OP_SETUPVAL, e, var->u.s.info, 0);
      break;
    }
    case VGLOBAL: {
      int e = luaK_exp2anyreg(fs, ex);
      luaK_codeABx(fs, OP_SETGLOBAL, e, var->u.s.info);
      break;
    }
    case VINDEXED: {
      int e = luaK_exp2RK(fs, ex);
      luaK_codeABC(fs, OP_SETTABLE, var->u.s.info, var->u.s.aux, e);
      break;
    }
    default: {
      lua_assert(0);  /* invalid var kind to store */
      break;
    }
  }
  freeexp(fs, ex);
}
{{< /highlight >}}


<div class="src-block-caption">
  <span class="src-block-number">Code Snippet 22</span>:
  lcode.c
</div>

对应 case VGLOBAL，生成 setglobal 指令。


#### upvalue {#upvalue}

分析如下代码，

```lua
local a

function f()
  a = 10
end
```

```text
; function [0] definition (level 1)
; 0 upvalues, 0 params, 2 is_vararg, 2 stacks
.function  0 0 2 2
.local  "a"  ; 0
.const  "f"  ; 0

  ; function [0] definition (level 2)
  ; 1 upvalues, 0 params, 0 is_vararg, 2 stacks
  .function  1 0 0 2
  .upvalue  "a"  ; 0
  .const  10  ; 0
  [1] loadk      0   0        ; 10
  [2] setupval   0   0        ; a
  [3] return     0   1
  ; end of function

[1] closure    1   0        ; 1 upvalues
[2] move       0   0
[3] setglobal  1   0        ; f
[4] return     0   1
; end of function
```

对于外层函数，a 是 local 变量，而对应内层函数，a 为 upval 变量。

基本过程同 global，不过 singlevaraux 搜索得到 VUPVAL，生成 setupval 指令。


#### local {#local}

{{< highlight lua "linenos=table, linenostart=1" >}}
local a = 1

local b
b = 1
{{< /highlight >}}

line 1 为 local 赋值语句，而 line 4 为普通赋值语句，不过恰巧赋值给 local 变量。

分析如下示例，

```lua
local a, b

b = 10
```

```text
; function [0] definition (level 1)
; 0 upvalues, 0 params, 2 is_vararg, 2 stacks
.function  0 0 2 2
.local  "a"  ; 0
.local  "b"  ; 1
.const  10  ; 0
[1] loadk      1   0        ; 10
[2] return     0   1
; end of function
```

分析过程与上相同，singlevaraux 确定为 VLOCAL，针对寄存器位置，直接生成 loadk。


#### indexed {#indexed}

```lua
local t = {}

t['a'] = 10
```

```text
; function [0] definition (level 1)
; 0 upvalues, 0 params, 2 is_vararg, 2 stacks
.function  0 0 2 2
.local  "t"  ; 0
.const  "a"  ; 0
.const  10  ; 1
[1] newtable   0   0   0    ; array=0, hash=0
[2] settable   0   256 257  ; "a" 10
[3] return     0   1
; end of function
```

VINDEXED 的分析分为两部分，singlevar 分析 t 为 local 变量，
同时在 primaryexp 中继续分析 'a' 为字符串值，存储在 k 表直接引用。
最终使用 `luaK_indexed` 确定 expdesc 的类型及相关数据。

{{< highlight c "linenos=table, linenostart=621" >}}
void luaK_indexed (FuncState *fs, expdesc *t, expdesc *k) {
  t->u.s.aux = luaK_exp2RK(fs, k);
  t->k = VINDEXED;
}
{{< /highlight >}}


<div class="src-block-caption">
  <span class="src-block-number">Code Snippet 23</span>:
  lcode.c
</div>

在最终赋值时，生成 gettable 指令。

之所以使用 RK(C) 作为索引，是因为索引值未必是常数，也可能是一个表，一个函数等其它值，
这里由 table 的特性决定的，这种通用的值只能由寄存器存储。


### function {#function}

这个小节关注 function 分析的过程。

语法描述中，涉及函数定义的地方，主要有 3 处，

```bnf
funcstat     ::= FUNCTION funcname body
funcname     ::= NAME {`.' NAME} [`:' NAME]
body         ::= `(' parlist `)' chunk END
parlist      ::= [ DOTS | NAME {`,' NAME} [`,' DOTS] ]

localstat    ::= LOCAL FUNCTION NAME body

simpleexp    ::= NUMBER | STRING | NIL | TRUE | FALSE | DOTS |
		 constructor | FUNCTION body | primaryexp
```

第 1 种对应全局函数定义，第 2 种对应 local 函数定义，第 3 种对应函数函数定义。

```lua
function f()
end

local function f()
end

local f = function ()
end
```

但无论哪一种形式，函数分析的核心函数在于 body，通过 chunk 生成 Proto，
最终赋值予 global/local 变量。


#### param {#param}

先来看参数部分。

```lua
local function f(a, b, ...)
end
```

```text
; function [0] definition (level 1)
; 0 upvalues, 0 params, 2 is_vararg, 2 stacks
.function  0 0 2 2
.local  "f"  ; 0

  ; function [0] definition (level 2)
  ; 0 upvalues, 2 params, 7 is_vararg, 3 stacks
  .function  0 2 7 3
  .local  "a"  ; 0
  .local  "b"  ; 1
  .local  "arg"  ; 2
  [1] return     0   1
  ; end of function

[1] closure    0   0        ; 0 upvalues
[2] return     0   1
; end of function
```

参数部分由 parlist 处理，分为固定参数和可变参数。

{{< highlight c "linenos=table, linenostart=543" >}}
static void parlist (LexState *ls) {
  /* parlist -> [ param { `,' param } ] */
  FuncState *fs = ls->fs;
  Proto *f = fs->f;
  int nparams = 0;
  f->is_vararg = 0;
  if (ls->t.token != ')') {  /* is `parlist' not empty? */
    do {
      switch (ls->t.token) {
	case TK_NAME: {  /* param -> NAME */
	  new_localvar(ls, str_checkname(ls), nparams++);
	  break;
	}
	case TK_DOTS: {  /* param -> `...' */
	  luaX_next(ls);
#if defined(LUA_COMPAT_VARARG)
	  /* use `arg' as default name */
	  new_localvarliteral(ls, "arg", nparams++);
	  f->is_vararg = VARARG_HASARG | VARARG_NEEDSARG;
#endif
	  f->is_vararg |= VARARG_ISVARARG;
	  break;
	}
	default: luaX_syntaxerror(ls, "<name> or " LUA_QL("...") " expected");
      }
    } while (!f->is_vararg && testnext(ls, ','));
  }
  adjustlocalvars(ls, nparams);
  f->numparams = cast_byte(fs->nactvar - (f->is_vararg & VARARG_HASARG));
  luaK_reserveregs(fs, fs->nactvar);  /* reserve register for parameters */
}
{{< /highlight >}}


<div class="src-block-caption">
  <span class="src-block-number">Code Snippet 24</span>:
  lparser.c
</div>

固定参数的处理方法，和 local 变量相同，不再赘述。

对于可变参数，即参数列表的最后定义中出现 `...` ，表明函数接收可变数量的参数，
全部收纳入 `...` 中。

在 lua5.0 中，可以在参数定义时使用 `...` ， 但是没有 `...` 表达式，
意味着在函数体中使用传入的参数时，通过变量 arg 来引用。

arg 是一个 table，以数组形式存储了所有可变参数，同时 arg.n 存储了数组的长度。

下面是 lua5.1 的同义描述，

```lua
local function f(a, b, ...)
  local arg = {...}
  arg.n = select("#", ...)
end
```

lua5.1 默认提供了对变量 arg 的兼容性，所以才会出现注册 arg 变量的情况。

`fs->is_vararg` 是用来记录可变参数状态的变量，含义由 3 个二进制位综合表示。

{{< highlight c "linenos=table, linenostart=256" >}}
/* masks for new-style vararg */
#define VARARG_HASARG		1
#define VARARG_ISVARARG		2
#define VARARG_NEEDSARG		4
{{< /highlight >}}


<div class="src-block-caption">
  <span class="src-block-number">Code Snippet 25</span>:
  lobject.h
</div>

| macro             | number | desc                             |
|-------------------|--------|----------------------------------|
| `VARARG_HASARG`   | 0b001  | 方便计算参数数量，直接使用 & 运算就可以 |
| `VARARG_ISVARARG` | 0b010  | 是否存在可变参数                 |
| `VARARG_NEEDSARG` | 0b100  | 是否需要 arg，当函数内部出现 `...` 表达式时，置为 0 |

内部有如下几种模式

| cond       | `is_vararg` |
|------------|-------------|
| 无可变参数 | 0b000       |
| chunk      | 0b010       |
| 不需要 arg 变量 | 0b011       |
| 默认的兼容情况 | 0b111       |


#### upval {#upval}

函数体就是 chunk 过程，作为分析的入口，在内部被递归调用，这里不再多做解释。

这里想重点说明的是，函数对 upvalue 的引用过程。

{{< highlight lua "linenos=table, linenostart=1" >}}
local a

local function f()
   local b

   local function g()
      b = 20
      a = 10
   end
end
{{< /highlight >}}

{{< highlight text "linenos=table, linenostart=nil">}}
 1  ; function [0] definition (level 1)
 2  ; 0 upvalues, 0 params, 2 is_vararg, 2 stacks
 3  .function  0 0 2 2
 4  .local  "a"  ; 0
 5  .local  "f"  ; 1
 6
 7    ; function [0] definition (level 2)
 8    ; 1 upvalues, 0 params, 0 is_vararg, 2 stacks
 9    .function  1 0 0 2
  .local  "b"  ; 0
  .local  "g"  ; 1
  .upvalue  "a"  ; 0

    ; function [0] definition (level 3)
    ; 2 upvalues, 0 params, 0 is_vararg, 2 stacks
    .function  2 0 0 2
    .upvalue  "b"  ; 0
    .upvalue  "a"  ; 1
    .const  20  ; 0
    .const  10  ; 1
    [1] loadk      0   0        ; 20
    [2] setupval   0   0        ; b
    [3] loadk      0   1        ; 10
    [4] setupval   0   1        ; a
    [5] return     0   1
    ; end of function

  [1] closure    1   0        ; 2 upvalues
  [2] move       0   0
  [3] getupval   0   0        ; a
  [4] return     0   1
  ; end of function

[1] closure    1   0        ; 1 upvalues
[2] move       0   0
[3] return     0   1
; end of function
{{< /highlight >}}

示例代码存在 3 层函数嵌套，chunk f g。

g 中引用的变量 a b 对于 g 而言都是 upvalue 类型。

当分析到 line 7 时，fs 的链接关系如下，

{{< figure src="generator-f-g-upval.png" >}}

首先分析变量 b，

{{< highlight c "linenos=table, linenostart=183" >}}
static int singlevaraux (FuncState *fs, TString *n, expdesc *var, int base) {
  if (fs == NULL) {  /* no more levels? */
    init_exp(var, VGLOBAL, NO_REG);  /* default is global variable */
    return VGLOBAL;
  }
  else {
    int v = searchvar(fs, n);  /* look up at current level */
    if (v >= 0) {
      init_exp(var, VLOCAL, v);
      if (!base)
	markupval(fs, v);  /* local will be used as an upval */
      return VLOCAL;
    }
    else {  /* not found at current level; try upper one */
      if (singlevaraux(fs->prev, n, var, 0) == VGLOBAL)
	return VGLOBAL;
      var->u.s.info = indexupvalue(fs, n, var);  /* else was LOCAL or UPVAL */
      var->k = VUPVAL;  /* upvalue in this level */
      return VUPVAL;
    }
  }
}
{{< /highlight >}}


<div class="src-block-caption">
  <span class="src-block-number">Code Snippet 26</span>:
  lparser.c
</div>

在 fs g() 中搜索无果，搜索上层 fs f()，在 fs f() 的 local 变量中找到 b，
调用 indexupvalue，然后标识为 VUPVAL 类型返回。

{{< highlight c "linenos=table, linenostart=183" >}}
static int indexupvalue (FuncState *fs, TString *name, expdesc *v) {
  int i;
  Proto *f = fs->f;
  int oldsize = f->sizeupvalues;
  for (i=0; i<f->nups; i++) {
    if (fs->upvalues[i].k == v->k && fs->upvalues[i].info == v->u.s.info) {
      lua_assert(f->upvalues[i] == name);
      return i;
    }
  }
  /* new one */
  luaY_checklimit(fs, f->nups + 1, LUAI_MAXUPVALUES, "upvalues");
  luaM_growvector(fs->L, f->upvalues, f->nups, f->sizeupvalues,
		  TString *, MAX_INT, "");
  while (oldsize < f->sizeupvalues) f->upvalues[oldsize++] = NULL;
  f->upvalues[f->nups] = name;
  luaC_objbarrier(fs->L, f, name);
  lua_assert(v->k == VLOCAL || v->k == VUPVAL);
  fs->upvalues[f->nups].k = cast_byte(v->k);
  fs->upvalues[f->nups].info = cast_byte(v->u.s.info);
  return f->nups++;
}
{{< /highlight >}}


<div class="src-block-caption">
  <span class="src-block-number">Code Snippet 27</span>:
  lparser.c
</div>

在 indexupvalue 中，先搜索是否已经存在 upvalue b，若没有则存储到 upvalues 数组中。

f->upvalues 记录变量名，fs->upvalues 记录 upval 信息。

{{< figure src="generator-f-g-upvalues-0.png" >}}

{{< figure src="generator-f-g-upvalues-1.png" >}}

upvalue 其实可分为两种情况，一种是 VLOCAL，一种是 VUPVAL。

b 属于 VLOCAL 的情况，因为 b 和 g() 在一个层级，g() 内部只需要向上查找一个层级便可定位 b。

{{< highlight c "linenos=table, linenostart=48" >}}
typedef struct upvaldesc {
  lu_byte k;
  lu_byte info;
} upvaldesc;
{{< /highlight >}}


<div class="src-block-caption">
  <span class="src-block-number">Code Snippet 28</span>:
  lparser.h
</div>

fs->upvalues 在记录 VLOCAL 的同时，也记录其对应的寄存器位置。

再来搜索变量 a，不存在于 g()，也不存在于 f() 中，在 chunk() 中找到。

此时 upvalues 数组的情况如下。

{{< figure src="generator-f-g-upvalues-2.png" >}}

{{< figure src="generator-f-g-upvalues-3.png" >}}

a 对于 g() 属于 VUPVAL 的情况，对于 f() 属于 VLOCAL 的情况。

值得注意，在搜索变量 a 的时候，indexupvalue 调用了两次，一次从 fs g() 出发，一次从 fs f() 出发。
这也解释了，为什么 f() 没有直接使用 a，但是其 upvalues 表中依然记录了 a。

当函数 g() 解析结束之后，将 Proto 结果链接到上层。

{{< figure src="generator-f-g-upvalues-4.png" >}}

得到 Proto 之后，生成 closure 指令将其赋值予变量 g。

同时在 closure 指令之后，生成了额外的两条指令，按顺序表明当前 closure 的 upvalue 的类型和索引信息。

```text
[2] move       0   0
[3] getupval   0   0        ; a
```

move 指令此时不表示普通的 move 含义，参数 A 无用，参数 B 指代 VLOCAL 的栈索引。
表示新建的 closure 第 1 个 upvalue 是 VLOCAL 类型，
指向当前作用域索引为 0 的寄存器。

getupval 指令同样，参数 A 无用，参数 B 表示上层 closure 中 upvalues 表中的序号。
表示第 2 个 upvalue 是 VUPVAL 类型，指向上个作用域索引为 0 的 upvalue。

使用这种方式，将 upvalue 的类型和索引存储到 code 中，
所以 f->upvalues 只需要单纯记录变量名称就足够了。

vm 在执行的时候，自然会理会其中的含义并做出相应处理。


### do {#do}

相信很多人都对 ebnf 描述中的 block 和 chunk 有疑问。

```bnf
stat         ::= dostat
dostat       ::= DO block END

block        ::= chunk
```

chunk 已经是分析的入口，为什么 block 又生成 chunk，这样看来 block
不是应该在 chunk 上层吗？

其实这个问题可以这样看，chunk 可以看作是分析语句列表的方法，
block 调用 chunk，是为了分析 block 中的语句列表，并不是要生成新的 FuncState。

实际上，block 有其自己的一套逻辑。

do 语句是最纯粹调用 block 的语句。

```lua
local a

do
   local b
   local c
   do
      local d

      a = 10
   end
end
```

```text
; function [0] definition (level 1)
; 0 upvalues, 0 params, 2 is_vararg, 4 stacks
.function  0 0 2 4
.local  "a"  ; 0
.local  "b"  ; 1
.local  "c"  ; 2
.local  "d"  ; 3
.const  10  ; 0
[1] loadk      0   0        ; 10
[2] return     0   1
; end of function
```

从结果中，好像什么都看不到，和正常声明变量，进行赋值，是一样的效果。

实际上，do 语句的作用主要在于描述块作用域。

在 block() 方法中，

{{< highlight c "linenos=table, linenostart=881" >}}
static void block (LexState *ls) {
  /* block -> chunk */
  FuncState *fs = ls->fs;
  BlockCnt bl;
  enterblock(fs, &bl, 0);
  chunk(ls);
  lua_assert(bl.breaklist == NO_JUMP);
  leaveblock(fs);
}
{{< /highlight >}}


<div class="src-block-caption">
  <span class="src-block-number">Code Snippet 29</span>:
  lparser.c
</div>

先后调用 enterblock 和 leaveblock 方法，操作 fs->bl。

这里也说明了，虽然同样调用 chunk，但是在函数定义时，其使用 `open_func` `close_func` 来操作
fs->prev 形成链状结构，所以 block() 的行为主要是由 enterblock leaveblock 决定的。

{{< highlight c "linenos=table, linenostart=37" >}}
/*
** nodes for block list (list of active blocks)
*/
typedef struct BlockCnt {
  struct BlockCnt *previous;  /* chain */
  int breaklist;  /* list of jumps out of this loop */
  lu_byte nactvar;  /* # active locals outside the breakable structure */
  lu_byte upval;  /* true if some variable in the block is an upvalue */
  lu_byte isbreakable;  /* true if `block' is a loop */
} BlockCnt;
{{< /highlight >}}


<div class="src-block-caption">
  <span class="src-block-number">Code Snippet 30</span>:
  lparser.c
</div>

BlockCnt 的结构并不复杂，

-   `struct BlockCnt *previous` ，指向父 block
-   `int breaklist` ，在 while 章节讲解
-   `lu_byte nactvar` ，进入 block 前保存 nactvar
-   `lu_byte upval` ，当前块作用域中是否有 local 变量用作 upvalue，在 repeat 章节讲解
-   `lu_byte isbreakable` ，是否是一个循环语句块，在 while 章节讲解。

<!--listend-->

{{< highlight c "linenos=table, linenostart=285" >}}
static void enterblock (FuncState *fs, BlockCnt *bl, lu_byte isbreakable) {
  bl->breaklist = NO_JUMP;
  bl->isbreakable = isbreakable;
  bl->nactvar = fs->nactvar;
  bl->upval = 0;
  bl->previous = fs->bl;
  fs->bl = bl;
  lua_assert(fs->freereg == fs->nactvar);
}


static void leaveblock (FuncState *fs) {
  BlockCnt *bl = fs->bl;
  fs->bl = bl->previous;
  removevars(fs->ls, bl->nactvar);
  if (bl->upval)
    luaK_codeABC(fs, OP_CLOSE, bl->nactvar, 0, 0);
  /* a block either controls scope or breaks (never both) */
  lua_assert(!bl->isbreakable || !bl->upval);
  lua_assert(bl->nactvar == fs->nactvar);
  fs->freereg = fs->nactvar;  /* free registers */
  luaK_patchtohere(fs, bl->breaklist);
}
{{< /highlight >}}


<div class="src-block-caption">
  <span class="src-block-number">Code Snippet 31</span>:
  lparser.c
</div>

enterblock 新建 BlockCnt，指向父 block，并记录当前 nactvar。
leaveblock 则相反，删除顶层 block，将 fs->freereg 重置回原来的 nactvar。

明显地起到了作用域分隔的作用。

{{< figure src="generator-do-block.png" >}}

在第 1 次进入 do block 时，外部只定义了 local a，只有一个局部变量，
此时保存 nactvar 为 1。

第 2 次进入 do block 时，增加了定义 local b c，新的 BlockCnt 链接到父 block，
保存 nactvar 为 3。

在内部，修改 a = 10，这个 a 正是最外层的 local a 而不是 upvalue，因为 upvalue
只作用于不同函数之间，目前 local a b c d 是属于一个函数作用域的。

离开内层 do block 时，恢复 freereg 到 nactvar=3 且重置了 fs->nactvar，相当于回收了变量 d。

至于 block 在循环中的作用，到循环语句章节再讲解。


### if {#if}

本节来分析，在代码生成过程中是如何处理 if 语句的。

```bnf
stat         ::= ifstat

ifstat       ::= IF cond THEN block {ELSEIF cond THEN block} [ELSE block] END
cond         ::= expr
block        ::= chunk
```

前面已经提到过，整体的分析过程是从左至右，从前至后的，
而 if 是分支结构，不同于分析过程的线性结构。

lua 内部使用一种精巧的方式解决这个问题。


#### if {#if}

首先来看示例代码，

```lua
local a, b

if b then
   a = 1
end
```

```text
; function [0] definition (level 1)
; 0 upvalues, 0 params, 2 is_vararg, 2 stacks
.function  0 0 2 2
.local  "a"  ; 0
.local  "b"  ; 1
.const  1  ; 0
[1] test       1       0    ; to [3] if true
[2] jmp        1            ; to [4]
[3] loadk      0   0        ; 1
[4] return     0   1
; end of function
```

整体流程的示意如下，TRUE 表示条件为真所执行的字节码，这里为 loadk。

{{< figure src="generator-if.png" >}}

在分支结构中扮演重要角色的是两种指令，test 和 jmp。

在 vm 的执行过程中，pc 问题默认自增的，即执行完当前指令后，pc++，
对于 test 和 jmp 也不例外。

jmp 指令有一个参数，即跳转的距离，可正可负，意味着可以向前跳转，也可以向后。

根据 pc++ 的原则，

-   指令 `jmp -1` 表示循环执行当前的 jmp 指令，因为 jmp 跳转到自身
-   指令 `jmp 0`  表示跳转到下一条指令，即正常执行
-   指令 `jmp 1`  表示略过下一条指令，跳转到下下一条指令

jmp 是无条件跳转，而 test 指令不同，需要针对 True 和 False 跳转到不同的地方。
lua 使用了一种简洁的模式来安排。

（假设参数 `C = 0` ）test 指令之后固定接着一条 jmp 指令，用于执行 False 跳转。
jmp 指令之后紧接着 True 语句块。

在这种安排下，

-   如果为 False，正常执行下一条指令，下一条 jmp 跳转到 False 语句块
-   如果为 True，vm 执行 pc++ ++，跳过 test 后的 jmp 指令，执行 True 语句块

这样就不用使得 test 指令过于复杂。

对照示例代码，内部使用 ifstat() 来分析 if 语句。

{{< highlight c "linenos=table, linenostart=1130" >}}
static int test_then_block (LexState *ls) {
  /* test_then_block -> [IF | ELSEIF] cond THEN block */
  int condexit;
  luaX_next(ls);  /* skip IF or ELSEIF */
  condexit = cond(ls);
  checknext(ls, TK_THEN);
  block(ls);  /* `then' part */
  return condexit;
}


static void ifstat (LexState *ls, int line) {
  /* ifstat -> IF cond THEN block {ELSEIF cond THEN block} [ELSE block] END */
  FuncState *fs = ls->fs;
  int flist;
  int escapelist = NO_JUMP;
  flist = test_then_block(ls);  /* IF cond THEN block */
  while (ls->t.token == TK_ELSEIF) {
    luaK_concat(fs, &escapelist, luaK_jump(fs));
    luaK_patchtohere(fs, flist);
    flist = test_then_block(ls);  /* ELSEIF cond THEN block */
  }
  if (ls->t.token == TK_ELSE) {
    luaK_concat(fs, &escapelist, luaK_jump(fs));
    luaK_patchtohere(fs, flist);
    luaX_next(ls);  /* skip ELSE (after patch, for correct line info) */
    block(ls);  /* `else' part */
  }
  else
    luaK_concat(fs, &escapelist, flist);
  luaK_patchtohere(fs, escapelist);
  check_match(ls, TK_END, TK_IF, line);
}
{{< /highlight >}}


<div class="src-block-caption">
  <span class="src-block-number">Code Snippet 32</span>:
  lparser.c
</div>

使用 `test_then_block()` 分析 `IF cond THEN block` 的部分，
使用 cond() 分析条件部分，

{{< highlight c "linenos=table, linenostart=965" >}}
static int cond (LexState *ls) {
  /* cond -> exp */
  expdesc v;
  expr(ls, &v);  /* read condition */
  if (v.k == VNIL) v.k = VFALSE;  /* `falses' are all equal here */
  luaK_goiftrue(ls->fs, &v);
  return v.f;
}
{{< /highlight >}}


<div class="src-block-caption">
  <span class="src-block-number">Code Snippet 33</span>:
  lparser.c
</div>

进入 `luaK_goiftrue()` ，调用 `jumponcond` 和 `condjump` ，生成了 test 指令和 jmp 指令，

{{< highlight c "linenos=table, linenostart=524" >}}
static int jumponcond (FuncState *fs, expdesc *e, int cond) {
  if (e->k == VRELOCABLE) {
    Instruction ie = getcode(fs, e);
    if (GET_OPCODE(ie) == OP_NOT) {
      fs->pc--;  /* remove previous OP_NOT */
      return condjump(fs, OP_TEST, GETARG_B(ie), 0, !cond);
    }
    /* else go through */
  }
  discharge2anyreg(fs, e);
  freeexp(fs, e);
  return condjump(fs, OP_TESTSET, NO_REG, e->u.s.info, cond);
}


void luaK_goiftrue (FuncState *fs, expdesc *e) {
  int pc;  /* pc of last jump */
  luaK_dischargevars(fs, e);
  switch (e->k) {
    case VK: case VKNUM: case VTRUE: {
      pc = NO_JUMP;  /* always true; do nothing */
      break;
    }
    case VJMP: {
      invertjump(fs, e);
      pc = e->u.s.info;
      break;
    }
    default: {
      pc = jumponcond(fs, e, 0);
      break;
    }
  }
  luaK_concat(fs, &e->f, pc);  /* insert last jump in `f' list */
  luaK_patchtohere(fs, e->t);
  e->t = NO_JUMP;
}
{{< /highlight >}}


<div class="src-block-caption">
  <span class="src-block-number">Code Snippet 34</span>:
  lcode.c
</div>

{{< highlight c "linenos=table, linenostart=74" >}}
static int condjump (FuncState *fs, OpCode op, int A, int B, int C) {
  luaK_codeABC(fs, op, A, B, C);
  return luaK_jump(fs);
}
{{< /highlight >}}


<div class="src-block-caption">
  <span class="src-block-number">Code Snippet 35</span>:
  lcode.c
</div>

最终 `cond()` 返回 jmp 指令的索引，在 ifstat() 中由 flist 保存。

下面就是关键的地方，lua 如何确定跳转的位置，其中有几个关键的过程，concat，patch 和 dischargejpc。

在 `test_then_block()` 之后，解析了 cond 和 true block，并保留了 jmp 指令的索引。

{{< figure src="generator-if-test-then-block.png" >}}

因为其后没有 else/elseif 语句，直接执行 line 1159，

{{< highlight c "linenos=table, linenostart=185" >}}
void luaK_concat (FuncState *fs, int *l1, int l2) {
  if (l2 == NO_JUMP) return;
  else if (*l1 == NO_JUMP)
    *l1 = l2;
  else {
    int list = *l1;
    int next;
    while ((next = getjump(fs, list)) != NO_JUMP)  /* find last element */
      list = next;
    fixjump(fs, list, l2);
  }
}
{{< /highlight >}}


<div class="src-block-caption">
  <span class="src-block-number">Code Snippet 36</span>:
  lcode.c
</div>

将 flist 链接到 escapelist 上，

{{< figure src="generator-if-test-then-block-1.png" >}}

其后执行 line 1160，执行 patch 过程，

{{< highlight c "linenos=table, linenostart=179" >}}
void luaK_patchtohere (FuncState *fs, int list) {
  luaK_getlabel(fs);
  luaK_concat(fs, &fs->jpc, list);
}
{{< /highlight >}}


<div class="src-block-caption">
  <span class="src-block-number">Code Snippet 37</span>:
  lcode.c
</div>

将 escapelist 链接到 fs->jpc 上，

{{< figure src="generator-if-test-then-block-2.png" >}}

最终在生成 TRUE 之后的语句时，执行 dischargejpc 过程，

{{< highlight c "linenos=table, linenostart=789" >}}
static int luaK_code (FuncState *fs, Instruction i, int line) {
  Proto *f = fs->f;
  dischargejpc(fs);  /* `pc' will change */
  /* put new instruction in code array */
  luaM_growvector(fs->L, f->code, fs->pc, f->sizecode, Instruction,
		  MAX_INT, "code size overflow");
  f->code[fs->pc] = i;
  /* save corresponding line information */
  luaM_growvector(fs->L, f->lineinfo, fs->pc, f->sizelineinfo, int,
		  MAX_INT, "code size overflow");
  f->lineinfo[fs->pc] = line;
  return fs->pc++;
}
{{< /highlight >}}


<div class="src-block-caption">
  <span class="src-block-number">Code Snippet 38</span>:
  lcode.c
</div>

{{< highlight c "linenos=table, linenostart=150" >}}
static void patchlistaux (FuncState *fs, int list, int vtarget, int reg,
			  int dtarget) {
  while (list != NO_JUMP) {
    int next = getjump(fs, list);
    if (patchtestreg(fs, list, reg))
      fixjump(fs, list, vtarget);
    else
      fixjump(fs, list, dtarget);  /* jump to default target */
    list = next;
  }
}


static void dischargejpc (FuncState *fs) {
  patchlistaux(fs, fs->jpc, fs->pc, NO_REG, fs->pc);
  fs->jpc = NO_JUMP;
}
{{< /highlight >}}


<div class="src-block-caption">
  <span class="src-block-number">Code Snippet 39</span>:
  lcode.c
</div>

{{< figure src="generator-if-3.png" >}}

此时已经在 TRUE 语句块之外，也明确当前的指令索引和 jmp 指令索引，
直接计算距离的差值，修改 jmp 指令的参数，跳转到此位置。

综合来看，concat 将需要重新定位的 jmp 指令链接起来，最终链接到 jpc 上，
由 dischargejpc 过程，调整所有链接的 jmp 指令，使其跳转到当前位置。

单纯的 if 语句比较简单，读者或许还体会不到这种方法的作用，下面来看更复杂的语句。


#### if else {#if-else}

```lua
local a, b

if b then
   a = 1
else
   a = 0
end
```

```text
; function [0] definition (level 1)
; 0 upvalues, 0 params, 2 is_vararg, 2 stacks
.function  0 0 2 2
.local  "a"  ; 0
.local  "b"  ; 1
.const  1  ; 0
.const  0  ; 1
[1] test       1       0    ; to [3] if true
[2] jmp        2            ; to [5]
[3] loadk      0   0        ; 1
[4] jmp        1            ; to [6]
[5] loadk      0   1        ; 0
[6] return     0   1
; end of function
```

{{< figure src="generator-if-else-0.png" >}}

{{< highlight c "linenos=table, linenostart=1141" >}}
static void ifstat (LexState *ls, int line) {
  /* ifstat -> IF cond THEN block {ELSEIF cond THEN block} [ELSE block] END */
  FuncState *fs = ls->fs;
  int flist;
  int escapelist = NO_JUMP;
  flist = test_then_block(ls);  /* IF cond THEN block */
  while (ls->t.token == TK_ELSEIF) {
    luaK_concat(fs, &escapelist, luaK_jump(fs));
    luaK_patchtohere(fs, flist);
    flist = test_then_block(ls);  /* ELSEIF cond THEN block */
  }
  if (ls->t.token == TK_ELSE) {
    luaK_concat(fs, &escapelist, luaK_jump(fs));
    luaK_patchtohere(fs, flist);
    luaX_next(ls);  /* skip ELSE (after patch, for correct line info) */
    block(ls);  /* `else' part */
  }
  else
    luaK_concat(fs, &escapelist, flist);
  luaK_patchtohere(fs, escapelist);
  check_match(ls, TK_END, TK_IF, line);
}
{{< /highlight >}}


<div class="src-block-caption">
  <span class="src-block-number">Code Snippet 40</span>:
  lparser.c
</div>

在 if else 语句中，解析 cond 和 true block 之后，要继续解析 else false block 部分。

false block 生成字节码也遵循一定的模式，先生成 jmp 指令，用于跳出 true block，
其次再生成 false block。

其中将这个 jmp 链接到 escapelist 上，因为分析到 false block 的起始位置，
所以重定向 test 部分的 jmp 到这个位置。

{{< figure src="generator-if-else-1.png" >}}

最终将 escapelist 链接到 jpc 上，进行 dischargejpc 操作。

{{< figure src="generator-if-else-2.png" >}}

由这种模式可以看出，flist 表示 false list，escapelist 表示跳出 true list。

discharge 的过程就是先将目标链接到 fs->jpc 上，然后从 fs->jpc 开始，重新定位所有 jmp 的目标位置。


#### if elseif {#if-elseif}

```lua
local a, b, c

if b then
   a = 1
elseif c then
   a = 2
end
```

```text
; function [0] definition (level 1)
; 0 upvalues, 0 params, 2 is_vararg, 3 stacks
.function  0 0 2 3
.local  "a"  ; 0
.local  "b"  ; 1
.local  "c"  ; 2
.const  1  ; 0
.const  2  ; 1
[1] test       1       0    ; to [3] if true
[2] jmp        2            ; to [5]
[3] loadk      0   0        ; 1
[4] jmp        3            ; to [8]
[5] test       2       0    ; to [7] if true
[6] jmp        1            ; to [8]
[7] loadk      0   1        ; 2
[8] return     0   1
; end of function
```

{{< figure src="generator-if-else-if-0.png" >}}

{{< highlight c "linenos=table, linenostart=1141" >}}
static void ifstat (LexState *ls, int line) {
  /* ifstat -> IF cond THEN block {ELSEIF cond THEN block} [ELSE block] END */
  FuncState *fs = ls->fs;
  int flist;
  int escapelist = NO_JUMP;
  flist = test_then_block(ls);  /* IF cond THEN block */
  while (ls->t.token == TK_ELSEIF) {
    luaK_concat(fs, &escapelist, luaK_jump(fs));
    luaK_patchtohere(fs, flist);
    flist = test_then_block(ls);  /* ELSEIF cond THEN block */
  }
  if (ls->t.token == TK_ELSE) {
    luaK_concat(fs, &escapelist, luaK_jump(fs));
    luaK_patchtohere(fs, flist);
    luaX_next(ls);  /* skip ELSE (after patch, for correct line info) */
    block(ls);  /* `else' part */
  }
  else
    luaK_concat(fs, &escapelist, flist);
  luaK_patchtohere(fs, escapelist);
  check_match(ls, TK_END, TK_IF, line);
}
{{< /highlight >}}


<div class="src-block-caption">
  <span class="src-block-number">Code Snippet 41</span>:
  lparser.c
</div>

elseif 结构是不限数量的，相比之下，if 和 else 只能有一个，
所以这里用 while 循环来重复检测所有 elseif 块。

对于一个 elseif 块，先生成 jmp 指令，再重新调用 `test_then_block` ，当做一个 if 块来处理。

示例代码中只有一个 elseif 块，所以在执行到 line 1151 时，生成字节码如下，

{{< figure src="generator-if-else-if-1.png" >}}

在生成最终的 return 之前，在 line 1159 将 flist 链接到 escapelist 上，因为它们有同样的终点。

{{< highlight c "linenos=table, linenostart=185" >}}
void luaK_concat (FuncState *fs, int *l1, int l2) {
  if (l2 == NO_JUMP) return;
  else if (*l1 == NO_JUMP)
    *l1 = l2;
  else {
    int list = *l1;
    int next;
    while ((next = getjump(fs, list)) != NO_JUMP)  /* find last element */
      list = next;
    fixjump(fs, list, l2);
  }
}
{{< /highlight >}}


<div class="src-block-caption">
  <span class="src-block-number">Code Snippet 42</span>:
  lcode.c
</div>

其中将 4 jmp 指令，跳转到 6 jmp，相当于将 jmp 链接起来，以 escapelist 为索引链的开始。

{{< figure src="generator-if-else-if-2.png" >}}

最终在 discharge 的时候，只需要顺着 escapelist 往下，就可以访问到所有需要重定位的 jmp 指令，
并进行相应参数的修改。


#### if elseif else {#if-elseif-else}

嵌套的过程，读者可使用上述方法，自主探索，在此不再赘述。


### while {#while}

分支之后，来探索经典的 while 循环结构。

```bnf
whilestat    ::= WHILE cond DO block END
```

分析如下简单的示例，

```lua
local a, b

while b do
   a = 1
end
```

```text
; function [0] definition (level 1)
; 0 upvalues, 0 params, 2 is_vararg, 2 stacks
.function  0 0 2 2
.local  "a"  ; 0
.local  "b"  ; 1
.const  1  ; 0
[1] test       1       0    ; to [3] if true
[2] jmp        2            ; to [5]
[3] loadk      0   0        ; 1
[4] jmp        -4           ; to [1]
[5] return     0   1
; end of function
```

{{< figure src="generator-while-0.png" >}}

可以看出，while 结构生成字节码也是模式化的，cond 生成 test 和 jmp 指令，
其后是循环体，最后的 jmp 指令用于跳转到循环开始，只有 test 为 false 的时候才会跳出循环体。

{{< highlight c "linenos=table, linenostart=991" >}}
static void whilestat (LexState *ls, int line) {
  /* whilestat -> WHILE cond DO block END */
  FuncState *fs = ls->fs;
  int whileinit;
  int condexit;
  BlockCnt bl;
  luaX_next(ls);  /* skip WHILE */
  whileinit = luaK_getlabel(fs);
  condexit = cond(ls);
  enterblock(fs, &bl, 1);
  checknext(ls, TK_DO);
  block(ls);
  luaK_patchlist(fs, luaK_jump(fs), whileinit);
  check_match(ls, TK_END, TK_WHILE, line);
  leaveblock(fs);
  luaK_patchtohere(fs, condexit);  /* false conditions finish the loop */
}
{{< /highlight >}}


<div class="src-block-caption">
  <span class="src-block-number">Code Snippet 43</span>:
  lparser.c
</div>

生成的过程并不难理解，根据对 concat 和 patch 的理解，

{{< figure src="generator-while-1.png" >}}


#### break {#break}

因为 break 语句只能用于循环中，所以放在这里和 while 一起讲解。

```bnf
breakstat    ::= BREAK
```

分析如下示例，

```lua
local a, b

while b do
   a = 1
   break
end
```

```text
; function [0] definition (level 1)
; 0 upvalues, 0 params, 2 is_vararg, 2 stacks
.function  0 0 2 2
.local  "a"  ; 0
.local  "b"  ; 1
.const  1  ; 0
[1] test       1       0    ; to [3] if true
[2] jmp        3            ; to [6]
[3] loadk      0   0        ; 1
[4] jmp        1            ; to [6]
[5] jmp        -5           ; to [1]
[6] return     0   1
; end of function
```

{{< figure src="generator-break-0.png" >}}

可以看出，break 在循环体生成了 jmp 指令，跳转到循环外，这个过程由以下几点协同来实现。

{{< highlight c "linenos=table, linenostart=975" >}}
static void breakstat (LexState *ls) {
  FuncState *fs = ls->fs;
  BlockCnt *bl = fs->bl;
  int upval = 0;
  while (bl && !bl->isbreakable) {
    upval |= bl->upval;
    bl = bl->previous;
  }
  if (!bl)
    luaX_syntaxerror(ls, "no loop to break");
  if (upval)
    luaK_codeABC(fs, OP_CLOSE, bl->nactvar, 0, 0);
  luaK_concat(fs, &bl->breaklist, luaK_jump(fs));
}


static void whilestat (LexState *ls, int line) {
  /* whilestat -> WHILE cond DO block END */
  FuncState *fs = ls->fs;
  int whileinit;
  int condexit;
  BlockCnt bl;
  luaX_next(ls);  /* skip WHILE */
  whileinit = luaK_getlabel(fs);
  condexit = cond(ls);
  enterblock(fs, &bl, 1);
  checknext(ls, TK_DO);
  block(ls);
  luaK_patchlist(fs, luaK_jump(fs), whileinit);
  check_match(ls, TK_END, TK_WHILE, line);
  leaveblock(fs);
  luaK_patchtohere(fs, condexit);  /* false conditions finish the loop */
}
{{< /highlight >}}


<div class="src-block-caption">
  <span class="src-block-number">Code Snippet 44</span>:
  lparser.c
</div>

line 1000，调用 enterblock 新建了 `breakable = 1` 的 BlockCnt，

line 979，break 语句不断向上层的 BlockCnt 检测是否存在 breakable 的 BlockCnt，
不然就提示语法错误，no loop to break。（直到代码生成时，才检测出这个语法错误）

找到相应的 BlockCnt 之后，line 987 将 break 生成的 jmp 指令链接到 bl->breaklist 上，

{{< highlight c "linenos=table, linenostart=296" >}}
static void leaveblock (FuncState *fs) {
  BlockCnt *bl = fs->bl;
  fs->bl = bl->previous;
  removevars(fs->ls, bl->nactvar);
  if (bl->upval)
    luaK_codeABC(fs, OP_CLOSE, bl->nactvar, 0, 0);
  /* a block either controls scope or breaks (never both) */
  lua_assert(!bl->isbreakable || !bl->upval);
  lua_assert(bl->nactvar == fs->nactvar);
  fs->freereg = fs->nactvar;  /* free registers */
  luaK_patchtohere(fs, bl->breaklist);
}
{{< /highlight >}}


<div class="src-block-caption">
  <span class="src-block-number">Code Snippet 45</span>:
  lparser.c
</div>

最终在 line 1005 leaveblock 的时候，line 306 将 bl->breaklist 上的 jmp 重定位。


### for {#for}

repeat 循环和 while 循环非常相似，主要是通过 jmp 来实现的。
而 for 循环很特殊，用专门的指令来实现。

```bnf
forstat      ::= FOR (fornum | forlist) END
fornum       ::= NAME = expr `,' expr [`,' expr] forbody
forlist      ::= NAME {`,' NAME} IN explist forbody
forbody      ::= DO block
```

for 语句分为两种，一种只用于数字迭代的 fornum，

```lua
for i = 1, 10, 2 do

end
```

另一种通用迭代 forlist，

```lua
for k, v in pairs(t) do

end
```

两种用法在底层使用不同的指令来实现。


#### fornum {#fornum}

```bnf
fornum       ::= NAME = expr `,' expr [`,' expr] forbody
forbody      ::= DO block
```

`=` 后的 3 个表达式对应循环变量的初始值，目标值和间隔值，间隔值默认为 1。

分析如下代码，

```lua
local a = 0

for i = 1, 10, 2 do
   a = a + 1
end
```

```text
; function [0] definition (level 1)
; 0 upvalues, 0 params, 2 is_vararg, 5 stacks
.function  0 0 2 5
.local  "a"  ; 0
.local  "(for index)"  ; 1
.local  "(for limit)"  ; 2
.local  "(for step)"  ; 3
.local  "i"  ; 4
.const  0  ; 0
.const  1  ; 1
.const  10  ; 2
.const  2  ; 3
[1] loadk      0   0        ; 0
[2] loadk      1   1        ; 1
[3] loadk      2   2        ; 10
[4] loadk      3   3        ; 2
[5] forprep    1   1        ; to [7]
[6] add        0   0   257  ; 1
[7] forloop    1   -2       ; to [6] if loop
[8] return     0   1
; end of function
```

{{< figure src="generator-fornum-0.png" >}}

其中的生成模式也明确，先生成 forprep 做准备工作，跳转到 forloop，
之后分析 forbody，最终生成 fooloop，用于跳转到循环开始/结束循环。

根据 opcode 描述的语义，

```text
OP_FORPREP,/*	A sBx	R(A)-=R(A+2); pc+=sBx				*/

OP_FORLOOP,/*	A sBx	R(A)+=R(A+2);
			if R(A) <?= R(A+1) then { pc+=sBx; R(A+3)=R(A) }*/
```

forprep 先将循环变量减去间隔值，再跳转到 forloop。

而 forloop 将循环值加上间隔值，再和结束值对比，判断是否要跳出循环，
如果继续循环，则将循环值赋给循环变量；否则跳出循环。

{{< highlight C "linenos=table, linenostart=1046" >}}
static void forbody (LexState *ls, int base, int line, int nvars, int isnum) {
  /* forbody -> DO block */
  BlockCnt bl;
  FuncState *fs = ls->fs;
  int prep, endfor;
  adjustlocalvars(ls, 3);  /* control variables */
  checknext(ls, TK_DO);
  prep = isnum ? luaK_codeAsBx(fs, OP_FORPREP, base, NO_JUMP) : luaK_jump(fs);
  enterblock(fs, &bl, 0);  /* scope for declared variables */
  adjustlocalvars(ls, nvars);
  luaK_reserveregs(fs, nvars);
  block(ls);
  leaveblock(fs);  /* end of scope for declared variables */
  luaK_patchtohere(fs, prep);
  endfor = (isnum) ? luaK_codeAsBx(fs, OP_FORLOOP, base, NO_JUMP) :
		     luaK_codeABC(fs, OP_TFORLOOP, base, 0, nvars);
  luaK_fixline(fs, line);  /* pretend that `OP_FOR' starts the loop */
  luaK_patchlist(fs, (isnum ? endfor : luaK_jump(fs)), prep + 1);
}


static void fornum (LexState *ls, TString *varname, int line) {
  /* fornum -> NAME = exp1,exp1[,exp1] forbody */
  FuncState *fs = ls->fs;
  int base = fs->freereg;
  new_localvarliteral(ls, "(for index)", 0);
  new_localvarliteral(ls, "(for limit)", 1);
  new_localvarliteral(ls, "(for step)", 2);
  new_localvar(ls, varname, 3);
  checknext(ls, '=');
  exp1(ls);  /* initial value */
  checknext(ls, ',');
  exp1(ls);  /* limit */
  if (testnext(ls, ','))
    exp1(ls);  /* optional step */
  else {  /* default step = 1 */
    luaK_codeABx(fs, OP_LOADK, fs->freereg, luaK_numberK(fs, 1));
    luaK_reserveregs(fs, 1);
  }
  forbody(ls, base, line, 1, 1);
}
{{< /highlight >}}


<div class="src-block-caption">
  <span class="src-block-number">Code Snippet 46</span>:
  lparser.c
</div>

生成的过程并不难理解，值得关注的是变量部分。

在 local 表中隐式生成了 3 个变量，

```text
.local  "(for index)"  ; 1
.local  "(for limit)"  ; 2
.local  "(for step)"  ; 3
```

分别对应初始值，结束值和间隔值，变量都加了 ()，所以不会和 lua 代码中分析得到的变量名冲突。

在 fornum 语句整体分析的过程中，生成了 3 层 BlockCnt，

{{< figure src="generator-fornum-3-blocks.png" >}}

最外层 block 是在 forstat 中生成的， `breakable = 1` ，用于 break；

中间层 block 将隐式生成的变量 (for index) 之类和循环变量 i 分开；

最内层 block 用于 forbody block。


#### forlist {#forlist}

```bnf
forlist      ::= NAME {`,' NAME} IN explist forbody
forbody      ::= DO block
```

forlist 用于迭代器循环，最常见的就是用 pairs 循环遍历 table。

分析如下示例，

```lua
local a = 0

for k, v in pairs({}) do
   a = a + 1
end
```

```text
; function [0] definition (level 1)
; 0 upvalues, 0 params, 2 is_vararg, 7 stacks
.function  0 0 2 7
.local  "a"  ; 0
.local  "(for generator)"  ; 1
.local  "(for state)"  ; 2
.local  "(for control)"  ; 3
.local  "k"  ; 4
.local  "v"  ; 5
.const  0  ; 0
.const  "pairs"  ; 1
.const  1  ; 2
[1] loadk      0   0        ; 0
[2] getglobal  1   1        ; pairs
[3] newtable   2   0   0    ; array=0, hash=0
[4] call       1   2   4
[5] jmp        1            ; to [7]
[6] add        0   0   258  ; 1
[7] tforloop   1       2    ; to [9] if exit
[8] jmp        -3           ; to [6]
[9] return     0   1
; end of function
```

{{< figure src="generator-forlist-0.png" >}}

forlist 的生成模式有些不同，先生成 jmp 跳转到 tforloop 指令，
而 tforloop 根据 opcode 的语义，

```text
OP_TFORLOOP,/*	A C	R(A+3), ... ,R(A+2+C) := R(A)(R(A+1), R(A+2));
                        if R(A+3) ~= nil then R(A+2)=R(A+3) else pc++	*/
```

判断为 true 时，正常执行下一条指令；为 false 时，执行 pc++，跳过下一条指令。
而下一条指令固定是 jmp，用于定位到 forbody 的开始。

{{< highlight C "linenos=table, linenostart=1089" >}}
static void forlist (LexState *ls, TString *indexname) {
  /* forlist -> NAME {,NAME} IN explist1 forbody */
  FuncState *fs = ls->fs;
  expdesc e;
  int nvars = 0;
  int line;
  int base = fs->freereg;
  /* create control variables */
  new_localvarliteral(ls, "(for generator)", nvars++);
  new_localvarliteral(ls, "(for state)", nvars++);
  new_localvarliteral(ls, "(for control)", nvars++);
  /* create declared variables */
  new_localvar(ls, indexname, nvars++);
  while (testnext(ls, ','))
    new_localvar(ls, str_checkname(ls), nvars++);
  checknext(ls, TK_IN);
  line = ls->linenumber;
  adjust_assign(ls, 3, explist1(ls, &e), &e);
  luaK_checkstack(fs, 3);  /* extra space to call generator */
  forbody(ls, base, line, nvars - 3, 0);
}
{{< /highlight >}}


<div class="src-block-caption">
  <span class="src-block-number">Code Snippet 47</span>:
  lparser.c
</div>

{{< highlight C "linenos=table, linenostart=1046" >}}
static void forbody (LexState *ls, int base, int line, int nvars, int isnum) {
  /* forbody -> DO block */
  BlockCnt bl;
  FuncState *fs = ls->fs;
  int prep, endfor;
  adjustlocalvars(ls, 3);  /* control variables */
  checknext(ls, TK_DO);
  prep = isnum ? luaK_codeAsBx(fs, OP_FORPREP, base, NO_JUMP) : luaK_jump(fs);
  enterblock(fs, &bl, 0);  /* scope for declared variables */
  adjustlocalvars(ls, nvars);
  luaK_reserveregs(fs, nvars);
  block(ls);
  leaveblock(fs);  /* end of scope for declared variables */
  luaK_patchtohere(fs, prep);
  endfor = (isnum) ? luaK_codeAsBx(fs, OP_FORLOOP, base, NO_JUMP) :
		     luaK_codeABC(fs, OP_TFORLOOP, base, 0, nvars);
  luaK_fixline(fs, line);  /* pretend that `OP_FOR' starts the loop */
  luaK_patchlist(fs, (isnum ? endfor : luaK_jump(fs)), prep + 1);
}
{{< /highlight >}}


<div class="src-block-caption">
  <span class="src-block-number">Code Snippet 48</span>:
  lparser.c
</div>

其中同样隐式声明了 3 个变量，用于控制循环状态，

```text
.local  "(for generator)"  ; 1
.local  "(for state)"  ; 2
.local  "(for control)"  ; 3
```


### ret {#ret}

return 语句是非常直观的，

```bnf
retstat      ::= RETURN [explist]
```

用于从当前 closure 中返回，

```text
OP_RETURN,/*	A B	return R(A), ... ,R(A+B-2)	(see note)	*/
```

示例代码，

```lua
local a, b

return a, b
```

```text
; function [0] definition (level 1)
; 0 upvalues, 0 params, 2 is_vararg, 4 stacks
.function  0 0 2 4
.local  "a"  ; 0
.local  "b"  ; 1
[1] move       2   0
[2] move       3   1
[3] return     2   3
[4] return     0   1
; end of function
```

对应 retstat 过程，

{{< highlight C "linenos=table, linenostart=1238" >}}
static void retstat (LexState *ls) {
  /* stat -> RETURN explist */
  FuncState *fs = ls->fs;
  expdesc e;
  int first, nret;  /* registers with returned values */
  luaX_next(ls);  /* skip RETURN */
  if (block_follow(ls->t.token) || ls->t.token == ';')
    first = nret = 0;  /* return no values */
  else {
    nret = explist1(ls, &e);  /* optional return values */
    if (hasmultret(e.k)) {
      luaK_setmultret(fs, &e);
      if (e.k == VCALL && nret == 1) {  /* tail call? */
	SET_OPCODE(getcode(fs,&e), OP_TAILCALL);
	lua_assert(GETARG_A(getcode(fs,&e)) == fs->nactvar);
      }
      first = fs->nactvar;
      nret = LUA_MULTRET;  /* return all values */
    }
    else {
      if (nret == 1)  /* only one single value? */
	first = luaK_exp2anyreg(fs, &e);
      else {
	luaK_exp2nextreg(fs, &e);  /* values must go to the `stack' */
	first = fs->nactvar;  /* return all `active' values */
	lua_assert(nret == fs->freereg - first);
      }
    }
  }
  luaK_ret(fs, first, nret);
}
{{< /highlight >}}


<div class="src-block-caption">
  <span class="src-block-number">Code Snippet 49</span>:
  lparser.c
</div>

在 line 1267 生成 return 指令。


### function call {#function-call}

```bnf
funccallstat ::= prefixexp primaryexp (`:' NAME funcargs | funcargs)
funcargs     ::= `(' [ explist ] `)' | constructor | STRING
```

函数调用和函数定义不同。

假如函数定义接收 2 个参数，返回 1 个值，
而在函数调用时，可传递 3 个参数，不使用返回值。

至于多/少的参数/返回值怎么处理，取决于 vm，在 lua 中，如果多了则废弃，少了则补 nil。

比如如下示例，

```lua
local function f()
   return 1
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
  .const  1  ; 0
  [1] loadk      0   0        ; 1
  [2] return     0   2
  [3] return     0   1
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

哪怕函数定义不接收参数，返回 1 个值，在调用时，只根据调用语句的意愿，
传入 3 个参数，不要返回值。

{{< figure src="generator-func-call.png" >}}

根据 opcode 的语义，

```text
OP_CALL,/*	A B C	R(A), ... ,R(A+C-2) := R(A)(R(A+1), ... ,R(A+B-1)) */
```

在调用前，先将函数压栈，其次紧随着传入的参数值；
调用后，将所有返回值，从调用函数处，向上覆盖。

示例因为不需要返回值，所以调用后，原来的函数加参数位置置为空。

call 指令生成过程参考 funcargs，

{{< highlight C "linenos=table, linenostart=609" >}}
static void funcargs (LexState *ls, expdesc *f) {
  FuncState *fs = ls->fs;
  expdesc args;
  int base, nparams;
  int line = ls->linenumber;
  switch (ls->t.token) {
    case '(': {  /* funcargs -> `(' [ explist1 ] `)' */
      if (line != ls->lastline)
	luaX_syntaxerror(ls,"ambiguous syntax (function call x new statement)");
      luaX_next(ls);
      if (ls->t.token == ')')  /* arg list is empty? */
	args.k = VVOID;
      else {
	explist1(ls, &args);
	luaK_setmultret(fs, &args);
      }
      check_match(ls, ')', '(', line);
      break;
    }
    case '{': {  /* funcargs -> constructor */
      constructor(ls, &args);
      break;
    }
    case TK_STRING: {  /* funcargs -> STRING */
      codestring(ls, &args, ls->t.seminfo.ts);
      luaX_next(ls);  /* must use `seminfo' before `next' */
      break;
    }
    default: {
      luaX_syntaxerror(ls, "function arguments expected");
      return;
    }
  }
  lua_assert(f->k == VNONRELOC);
  base = f->u.s.info;  /* base register for call */
  if (hasmultret(args.k))
    nparams = LUA_MULTRET;  /* open call */
  else {
    if (args.k != VVOID)
      luaK_exp2nextreg(fs, &args);  /* close last argument */
    nparams = fs->freereg - (base+1);
  }
  init_exp(f, VCALL, luaK_codeABC(fs, OP_CALL, base, nparams+1, 2));
  luaK_fixline(fs, line);
  fs->freereg = base+1;  /* call remove function and arguments and leaves
			    (unless changed) one result */
}
{{< /highlight >}}


<div class="src-block-caption">
  <span class="src-block-number">Code Snippet 50</span>:
  lparser.c
</div>

计算参数的个数，line 651 生成 call 指令，返回值暂时用 1，根据上下文再进行后续的修正。


#### self {#self}

使用 `:` 的函数定义和调用方式，更多是出于一种便利，
作用就是将调用对象本身，默认当作第 1 个参数。

如下两种定义方式就是同义的，

```lua
local o = {}

function o.f(self)
  print(self)
end

function o:g()
  print(self)
end

o.f(o)

o:g()
```

```text
table: 0x557b5c2091c0
table: 0x557b5c2091c0
```

分析示例，

```lua
local o = {}

function o:f()
end

o:f()
```

```text
; function [0] definition (level 1)
; 0 upvalues, 0 params, 2 is_vararg, 3 stacks
.function  0 0 2 3
.local  "o"  ; 0
.const  "f"  ; 0

; function [0] definition (level 2)
; 0 upvalues, 1 params, 0 is_vararg, 2 stacks
.function  0 1 0 2
.local  "self"  ; 0
[1] return     0   1
; end of function

[1] newtable   0   0   0    ; array=0, hash=0
[2] closure    1   0        ; 0 upvalues
[3] settable   0   256 1    ; "f"
[4] self       1   0   256  ; "f"
[5] call       1   2   1
[6] return     0   1
; end of function
```

self 指令生成在 call 指令之前，结合 self 指令的语义，

```text
OP_SELF,/*	A B C	R(A+1) := R(B); R(A) := R(B)[RK(C)]		*/
```

结合示例字节码，self 相当于在栈中布置了 o 和 f，方便 call 进行调用，

{{< figure src="generator-self.png" >}}

内部在 primaryexp 中调用 `luaK_self` 生成 self 指令，

{{< highlight C "linenos=table, linenostart=690" >}}
static void primaryexp (LexState *ls, expdesc *v) {
  /* primaryexp ->
	prefixexp { `.' NAME | `[' exp `]' | `:' NAME funcargs | funcargs } */
  FuncState *fs = ls->fs;
  prefixexp(ls, v);
  for (;;) {
    switch (ls->t.token) {
      case '.': {  /* field */
	field(ls, v);
	break;
      }
      case '[': {  /* `[' exp1 `]' */
	expdesc key;
	luaK_exp2anyreg(fs, v);
	yindex(ls, &key);
	luaK_indexed(fs, v, &key);
	break;
      }
      case ':': {  /* `:' NAME funcargs */
	expdesc key;
	luaX_next(ls);
	checkname(ls, &key);
	luaK_self(fs, v, &key);
	funcargs(ls, v);
	break;
      }
      case '(': case TK_STRING: case '{': {  /* funcargs */
	luaK_exp2nextreg(fs, v);
	funcargs(ls, v);
	break;
      }
      default: return;
    }
  }
}
{{< /highlight >}}


<div class="src-block-caption">
  <span class="src-block-number">Code Snippet 51</span>:
  lparser.c
</div>

{{< highlight C "linenos=table, linenostart=503" >}}
void luaK_self (FuncState *fs, expdesc *e, expdesc *key) {
  int func;
  luaK_exp2anyreg(fs, e);
  freeexp(fs, e);
  func = fs->freereg;
  luaK_reserveregs(fs, 2);
  luaK_codeABC(fs, OP_SELF, func, e->u.s.info, luaK_exp2RK(fs, key));
  freeexp(fs, key);
  e->u.s.info = func;
  e->k = VNONRELOC;
}
{{< /highlight >}}


<div class="src-block-caption">
  <span class="src-block-number">Code Snippet 52</span>:
  lcode.c
</div>


#### tailcall {#tailcall}

结合 return，存在种特殊形式的函数调用 tailcall。

```lua
-- tail call
return f()
-- not tail call
return a, b, f()
```

在 return 语句后，仅跟随单独的函数调用，这种形式称为尾调用，
在 vm 中可以进行栈优化，到 vm 章节再详细解释。


## practice {#practice}

这个章节的内容虽然很长，但还远远没有将所有功能描述完全。

其它值得研究的功能包括

-   binop，二元运算
    -   arithmetic，算术运算，如何优先级
    -   logic，逻辑运算，and or 短路逻辑
-   table 字面量
-   repeat 语句
-   close，修改 upvalue 状态
-   etc

希望读者可以自行结合代码示例探索。

| 文件      | 建议 |
|---------|----|
| lparser.h | 仔细阅读 |
| lparser.c | 仔细阅读 |
| lcode.h   | 仔细阅读 |
| lcode.c   | 仔细阅读 |
