---
title: "object"
author: ["DreamAndDead"]
date: 2020-12-23T11:59:00+08:00
lastmod: 2021-02-23T11:42:20+08:00
draft: false
---

lua 是一种动态类型语言，类型不存在于变量中，而存在于值本身。

语言中定义了 8 种类型的值

-   nil
-   bool
-   number
-   string
-   table
-   function
-   userdata
-   thread

虽然章节名称为 object，和源代码的名称相同。
但是通常都翻译为“对象”，容易与 OOP 中的对象概念混杂在一起。
在本章，更乐意将其译为“值”。

从某种角度而言，程序就是“数据”与“操作数据的方法”。
所以第一步，先来了解 lua 中的值。


## tagged value {#tagged-value}

章节开始就提到，类型存在于值本身。
在 lua 内部，用 TValue（tagged value）结构表示值的概念。

{{< highlight c "linenos=table, linenostart=67" >}}
/*
** Tagged Values
*/

#define TValuefields	Value value; int tt

typedef struct lua_TValue {
  TValuefields;
} TValue;
{{< /highlight >}}


<div class="src-block-caption">
  <span class="src-block-number">Code Snippet 1</span>:
  lobject.h
</div>

tt 表示值的类型，value 表示值的数据。
明显地，类型是值的一部分。

{{< figure src="object-tvalue.png" >}}


### type {#type}

在 TValue 中，类型 tt 用 int 来标识，可以在代码中看到所有基础类型的宏定义

{{< highlight c "linenos=table, linenostart=69" >}}
/*
** basic types
*/
#define LUA_TNONE		(-1)

#define LUA_TNIL		0
#define LUA_TBOOLEAN		1
#define LUA_TLIGHTUSERDATA	2
#define LUA_TNUMBER		3
#define LUA_TSTRING		4
#define LUA_TTABLE		5
#define LUA_TFUNCTION		6
#define LUA_TUSERDATA		7
#define LUA_TTHREAD		8
{{< /highlight >}}


<div class="src-block-caption">
  <span class="src-block-number">Code Snippet 2</span>:
  lua.h
</div>

完全对应 lua 中的 8 种类型。

同时定义了相应的宏，方便检测值的类型。

{{< highlight c "linenos=table, linenostart=78" >}}
/* Macros to test type */
#define ttisnil(o)	(ttype(o) == LUA_TNIL)
#define ttisnumber(o)	(ttype(o) == LUA_TNUMBER)
#define ttisstring(o)	(ttype(o) == LUA_TSTRING)
#define ttistable(o)	(ttype(o) == LUA_TTABLE)
#define ttisfunction(o)	(ttype(o) == LUA_TFUNCTION)
#define ttisboolean(o)	(ttype(o) == LUA_TBOOLEAN)
#define ttisuserdata(o)	(ttype(o) == LUA_TUSERDATA)
#define ttisthread(o)	(ttype(o) == LUA_TTHREAD)
#define ttislightuserdata(o)	(ttype(o) == LUA_TLIGHTUSERDATA)

/* Macros to access values */
#define ttype(o)	((o)->tt)
{{< /highlight >}}


<div class="src-block-caption">
  <span class="src-block-number">Code Snippet 3</span>:
  lobject.h
</div>

细心如你，一定发现多出了一种 lightuserdata 类型。
这是由 userdata 细分出来的一种类型，目前先不做细致的解释，
之后到相应章节再具体分析。


### value {#value}

TValue 中，数据 value 用 union Value 结构来表示，有效利用内存空间。

{{< highlight c "linenos=table, linenostart=56" >}}
/*
** Union of all Lua values
*/
typedef union {
  GCObject *gc;
  void *p;
  lua_Number n;
  int b;
} Value;
{{< /highlight >}}


<div class="src-block-caption">
  <span class="src-block-number">Code Snippet 4</span>:
  lobject.h
</div>

不同类型的数据使用不同的键值来存取。

{{< figure src="object-value.png" >}}


## detail {#detail}

下面针对不同类型的值，详细分析。


### nil {#nil}

nil 是最简单的值，表示没有值。
由于只表示一个含义，故不需要 value，只用 tt 记录类型即可。

{{< highlight c "linenos=table, linenostart=27" >}}
const TValue luaO_nilobject_ = {{NULL}, LUA_TNIL};
{{< /highlight >}}


<div class="src-block-caption">
  <span class="src-block-number">Code Snippet 5</span>:
  lobject.c
</div>

{{< highlight c "linenos=table, linenostart=363" >}}
#define luaO_nilobject		(&luaO_nilobject_)

LUAI_DATA const TValue luaO_nilobject_;
{{< /highlight >}}


<div class="src-block-caption">
  <span class="src-block-number">Code Snippet 6</span>:
  lobject.h
</div>

可以看出，nil 值在内部是一个单例，所有使用 nil 的地方，都通过 `luaO_nilobject` 来引用。

{{< figure src="object-nil.png" >}}


### bool {#bool}

和其它语言一样，bool 值记录 true 和 false。

在存储的安排上，使用 tt 记录类型，用 value 中的 int b = 1/0 表示 true/false。

{{< figure src="object-bool.png" >}}


### light userdata {#light-userdata}

light userdata 表示 c 和 lua 协同时，由 c 一方传入的数据。
lua 内部只负责引用，而不负责其生命周期管理，什么时候应该释放，lua 不清楚也不过问。

所以内部在用 tt 记录类型之后，只用 value 中 void \* p 引用即可。

{{< figure src="object-userdata.png" >}}


### number {#number}

在默认设置下，lua 语言中所有数字都用 double 来表示。

{{< highlight c "linenos=table, linenostart=495" >}}
/*
** {==================================================================
@@ LUA_NUMBER is the type of numbers in Lua.
** CHANGE the following definitions only if you want to build Lua
** with a number type different from double. You may also need to
** change lua_number2int & lua_number2integer.
** ===================================================================
*/

#define LUA_NUMBER_DOUBLE
#define LUA_NUMBER	double
{{< /highlight >}}


<div class="src-block-caption">
  <span class="src-block-number">Code Snippet 7</span>:
  luaconf.h
</div>

{{< highlight c "linenos=table, linenostart=98" >}}
/* type of numbers in Lua */
typedef LUA_NUMBER lua_Number;
{{< /highlight >}}


<div class="src-block-caption">
  <span class="src-block-number">Code Snippet 8</span>:
  lua.h
</div>

类似的，用 tt 记录类型，用 value 中 `lua_Number n` 来记录 number 数值。

{{< figure src="object-number.png" >}}


### collectable {#collectable}

上面几种类型的值，内部表示都相对简单，剩余几种类型的数据就相对复杂一些。

-   string
-   table
-   function
-   userdata
-   thread

有一点是共通的，它们同属于可 gc 的值（iscollectable）。

{{< highlight c "linenos=table, linenostart=189" >}}
#define iscollectable(o)	(ttype(o) >= LUA_TSTRING)
{{< /highlight >}}


<div class="src-block-caption">
  <span class="src-block-number">Code Snippet 9</span>:
  lobject.h
</div>

{{< figure src="object-collectable.png" >}}

lua 内建了 gc 机制，其中关键的结构是 `GCObject` ，
用于表示所有 iscollectable 的值。

GCObject 是 union 结构，和 Value 结构类似，内部键值用于存取不同类型的数据。

{{< highlight c "linenos=table, linenostart=133" >}}
/*
** Union of all collectable objects
*/
union GCObject {
  GCheader gch;
  union TString ts;
  union Udata u;
  union Closure cl;
  struct Table h;
  struct Proto p;
  struct UpVal uv;
  struct lua_State th;  /* thread */
};
{{< /highlight >}}


<div class="src-block-caption">
  <span class="src-block-number">Code Snippet 10</span>:
  lstate.h
</div>

如果仔细观察内部内存的安排，会发现这种方式是非常巧妙的。

{{< figure src="object-gcobject.png" >}}

`gch h p uv th` 都是 struct，头部的字段都是 CommonHeader。

{{< highlight c "linenos=table, linenostart=39" >}}
/*
** Common Header for all collectable objects (in macro form, to be
** included in other objects)
*/
#define CommonHeader	GCObject *next; lu_byte tt; lu_byte marked


/*
** Common header in struct form
*/
typedef struct GCheader {
  CommonHeader;
} GCheader;
{{< /highlight >}}


<div class="src-block-caption">
  <span class="src-block-number">Code Snippet 11</span>:
  lobject.h
</div>

{{< highlight c "linenos=table, linenostart=338" >}}
typedef struct Table {
  CommonHeader;
  lu_byte flags;  /* 1<<p means tagmethod(p) is not present */
  lu_byte lsizenode;  /* log2 of size of `node' array */
  struct Table *metatable;
  TValue *array;  /* array part */
  Node *node;
  Node *lastfree;  /* any free position is before this position */
  GCObject *gclist;
  int sizearray;  /* size of `array' array */
} Table;
{{< /highlight >}}

{{< highlight c "linenos=table, linenostart=228" >}}
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

{{< highlight c "linenos=table, linenostart=270" >}}
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

{{< highlight c "linenos=table, linenostart=97" >}}
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
  <span class="src-block-number">Code Snippet 12</span>:
  lstate.h
</div>

`ts u cl` 虽然是 union，但是其中多余的字段是用于对齐的，实质还是 struct。

{{< highlight c "linenos=table, linenostart=196" >}}
/*
** String headers for string table
*/
typedef union TString {
  L_Umaxalign dummy;  /* ensures maximum alignment for strings */
  struct {
    CommonHeader;
    lu_byte reserved;
    unsigned int hash;
    size_t len;
  } tsv;
} TString;
{{< /highlight >}}


<div class="src-block-caption">
  <span class="src-block-number">Code Snippet 13</span>:
  lobject.h
</div>

{{< highlight c "linenos=table, linenostart=215" >}}
typedef union Udata {
  L_Umaxalign dummy;  /* ensures maximum alignment for `local' udata */
  struct {
    CommonHeader;
    struct Table *metatable;
    struct Table *env;
    size_t len;
  } uv;
} Udata;
{{< /highlight >}}

{{< highlight c "linenos=table, linenostart=287" >}}
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
{{< /highlight >}}

GCObject 将类型重新备份了一份，GCHeader 中的 tt 和 TValue 中的 tt 是相同的。

{{< highlight c "linenos=table, linenostart=105" >}}
/*
** for internal debug only
*/
#define checkconsistency(obj) \
  lua_assert(!iscollectable(obj) || (ttype(obj) == (obj)->value.gc->gch.tt))
{{< /highlight >}}


<div class="src-block-caption">
  <span class="src-block-number">Code Snippet 14</span>:
  lobject.h
</div>

这样的话，GCObject 可以脱离 TValue，使用 GCHeader gch 先来读取 tt，再根据 tt 来使用不同的键值来引用数据。

{{< highlight c "linenos=table, linenostart=148" >}}
/* macros to convert a GCObject into a specific value */
#define rawgco2ts(o)	check_exp((o)->gch.tt == LUA_TSTRING, &((o)->ts))
#define gco2ts(o)	(&rawgco2ts(o)->tsv)
#define rawgco2u(o)	check_exp((o)->gch.tt == LUA_TUSERDATA, &((o)->u))
#define gco2u(o)	(&rawgco2u(o)->uv)
#define gco2cl(o)	check_exp((o)->gch.tt == LUA_TFUNCTION, &((o)->cl))
#define gco2h(o)	check_exp((o)->gch.tt == LUA_TTABLE, &((o)->h))
#define gco2p(o)	check_exp((o)->gch.tt == LUA_TPROTO, &((o)->p))
#define gco2uv(o)	check_exp((o)->gch.tt == LUA_TUPVAL, &((o)->uv))
#define ngcotouv(o) \
	check_exp((o) == NULL || (o)->gch.tt == LUA_TUPVAL, &((o)->uv))
#define gco2th(o)	check_exp((o)->gch.tt == LUA_TTHREAD, &((o)->th))
{{< /highlight >}}


<div class="src-block-caption">
  <span class="src-block-number">Code Snippet 15</span>:
  lstate.h
</div>

至于不同类型的数据如何记录，在后面会分章节讨论。


### internal {#internal}

细心如你，一定又发现了，GCObject 中除了 gch，多出了 p uv，是 8 种类型之外的。

事实上，在 thread 之后，新定义了 3 个类型，同属于 iscollectable，只用于内部使用

-   proto
-   upval
-   deadkey

<!--listend-->

{{< highlight c "linenos=table, linenostart=19" >}}
/* tags for values visible from Lua */
#define LAST_TAG	LUA_TTHREAD

#define NUM_TAGS	(LAST_TAG+1)


/*
** Extra tags for non-values
*/
#define LUA_TPROTO	(LAST_TAG+1)
#define LUA_TUPVAL	(LAST_TAG+2)
#define LUA_TDEADKEY	(LAST_TAG+3)
{{< /highlight >}}


<div class="src-block-caption">
  <span class="src-block-number">Code Snippet 16</span>:
  lobject.h
</div>

proto 和 upval 就对应 GCObject 中多出的 2 个键值 p uv，
至于 deadkey，到特定章节再讨论。


## practice {#practice}

| 文件      | 建议 | 描述                                   |
|---------|----|--------------------------------------|
| lobject.h | 仔细阅读 | 这个文件非常关键，除了定义了关键的数据结构之外，还定义了大量的宏辅助数据操作 |
| lstate.h  | 浏览阅读 | 其中定义了和运行时状态相关的数据结构，尽量理解，加深印象 |
| lobject.c | 可以阅读 | 实现了 lobject.h 中声明的方法，并非核心内容 |
