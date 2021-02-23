---
title: "gc"
author: ["DreamAndDead"]
date: 2021-01-19T15:16:00+08:00
lastmod: 2021-02-23T13:24:56+08:00
draft: false
---

本章来讲解 Lua 内部实现的 gc 机制。


## algo {#algo}

gc 算法有很多种，Lua 采用一种增量式三色标记清除算法来实现 gc 机制。

之所以说一种，是因为采用的 gc 算法与其说是一个算法，不如说是一类算法，
大体的思想是相同的，不过在实现细节有些许不同。


### mark & sweep {#mark-and-sweep}

双色标记清除算法是最经典的算法。

初始阶段，所有对象标记为白色；

{{< figure src="gc-2-color-root.png" >}}

标记阶段，将所有从 root 可达的对象标记为黑色；

{{< figure src="gc-2-color-root-1.png" >}}

回收阶段，将所有白色对象回收，同时将所有黑色对象重新标记回白色；

{{< figure src="gc-2-color-root-2.png" >}}

gc 的过程，就在这些阶段中循环进行，所有对象在两种颜色间完成标记和清理。

{{< figure src="gc-2-color.png" >}}

不过在传统的标记清除算法中，gc 过程是一个整体，主程序在这期间需要暂停。
如果需要处理的对象过多，则主程序需要暂停过长时间。

{{< figure src="gc-not-inc.png" >}}


### tri color incremental mark & sweep {#tri-color-incremental-mark-and-sweep}

三色标记清除算法是对上述算法的改进。

引入了第三种颜色灰色，使 gc 过程可以增量式的运行，
即 gc 过程可以分成短时间的小段穿插在主程序间执行。

{{< figure src="gc-inc.png" >}}

改进后的 gc 过程如下：

初始阶段，所有对象标识为白色；

标记阶段的开始，将所有从 root 可达的对象标记为灰色；

标记阶段，逐个取出灰色对象，将其所有可达的白色对象标记为灰色，最后将自身标记为黑色；

清除阶段，当不存在灰色对象时，开始清除白色对象，将所有黑色对象标记回白色。

改进后的算法，标记阶段可以增量式的运行，随时暂停和继续。

{{< figure src="gc-3-color.png" >}}

但是在主程序和 gc 交替的过程中，主程序可以随时修改对象间的引用关系，
这就给 gc 带来了困难。

比如以下情况，A 已经标记为黑色，B 标记为灰色，

{{< figure src="gc-problem-0.png" >}}

在 gc 间歇期间，主程序修改了对象间的引用关系，
B 不再引用 C，而 A 开始引用 C。

{{< figure src="gc-problem-1.png" >}}

虽然 C 也是可达对象，但是由于断开了 B 到 C 的连接，而 A 已经是黑色，
所以 C 无法被标记为灰色继而黑色，所以本轮 gc 会被回收，最终造成 A 对象的空指针引用，
这显然是不正确的。

所以算法中引用了写屏障（barrier）技术，来解决这种问题。

-   当黑色对象引用白色对象时，将此 ****白色**** 对象标记成灰色，称为 barrier forward
-   当黑色对象引用白色对象时，将此 ****黑色**** 对象标记回灰色，称为 barrier back

两种方法都可以解决上述问题，在 Lua 内部两种方式都有使用。

{{< figure src="gc-3-color-with-barrier.png" >}}

读者可以思考一下，为什么只在黑色引用白色时会出现问题。
（排列组合，白->白，白->灰，...，黑->黑）


### double white {#double-white}

Lua 内部更进一步[^fn:1]，引用了双白色，加上灰黑，也就是 4 种颜色。

双白色的目的在于，在一轮 gc 的过程中，主程序会新建新的对象，新建对象用另一种白色来标识。
这样在此轮 gc 最终回收的时候，只回收原有白色的对象即可，不会涉及到新建对象。

同时，最终黑色会被标记为另一种白色。

{{< figure src="gc-4-color-with-barrier.png" >}}

如果开始下一轮 gc，需要将所有 other white 翻转为 white，回到起始点。

但是这样代价比较高，Lua 直接使用标识 `g->currentwhite` 来表示当前 gc 处理的白色类型，
这样就只需要翻转 `g->currentwhite` 即可。


## bit {#bit}

下面来看 gc 算法是如何和 Lua 内部的对象关联起来的。

回忆 object 章节，

{{< highlight C "linenos=table, linenostart=39" >}}
/*
** Common Header for all collectable objects (in macro form, to be
** included in other objects)
*/
#define CommonHeader	GCObject *next; lu_byte tt; lu_byte marked
{{< /highlight >}}


<div class="src-block-caption">
  <span class="src-block-number">Code Snippet 1</span>:
  lobject.h
</div>

每一个 GCObject 都有共同的 CommonHeader 字段，其中 marked 就是用来标识对象在 gc 过程中的状态。

{{< highlight C "linenos=table, linenostart=41" >}}
/*
** Layout for bit use in `marked' field:
** bit 0 - object is white (type 0)
** bit 1 - object is white (type 1)
** bit 2 - object is black
** bit 3 - for userdata: has been finalized
** bit 3 - for tables: has weak keys
** bit 4 - for tables: has weak values
** bit 5 - object is fixed (should not be collected)
** bit 6 - object is "super" fixed (only the main thread)
*/


#define WHITE0BIT	0
#define WHITE1BIT	1
#define BLACKBIT	2
#define FINALIZEDBIT	3
#define KEYWEAKBIT	3
#define VALUEWEAKBIT	4
#define FIXEDBIT	5
#define SFIXEDBIT	6
{{< /highlight >}}


<div class="src-block-caption">
  <span class="src-block-number">Code Snippet 2</span>:
  lgc.h
</div>

{{< figure src="gc-bit-mark.png" >}}

marked 字节中，前 3 位标识了颜色，任意时刻最多只有 1 位为 1。
当 3 个位都为 0 时，表示灰色。


## state {#state}

Lua 内部的 gc 过程分为如下几个状态，

{{< highlight C "linenos=table, linenostart=14" >}}
/*
** Possible states of the Garbage Collector
*/
#define GCSpause	0
#define GCSpropagate	1
#define GCSsweepstring	2
#define GCSsweep	3
#define GCSfinalize	4
{{< /highlight >}}


<div class="src-block-caption">
  <span class="src-block-number">Code Snippet 3</span>:
  lgc.h
</div>

不同状态间执行不同阶段的 gc 操作，

{{< figure src="gc-state.png" >}}

Lua 内部通过 `g->gcstate` 来记录当前的状态。


## phase {#phase}

gc 模块内部通过 `luaC_step` 来推动整个 gc 过程，

{{< highlight C "linenos=table, linenostart=610" >}}
void luaC_step (lua_State *L) {
  global_State *g = G(L);
  l_mem lim = (GCSTEPSIZE/100) * g->gcstepmul;
  if (lim == 0)
    lim = (MAX_LUMEM-1)/2;  /* no limit */
  g->gcdept += g->totalbytes - g->GCthreshold;
  do {
    lim -= singlestep(L);
    if (g->gcstate == GCSpause)
      break;
  } while (lim > 0);
  if (g->gcstate != GCSpause) {
    if (g->gcdept < GCSTEPSIZE)
      g->GCthreshold = g->totalbytes + GCSTEPSIZE;  /* - lim/g->gcstepmul;*/
    else {
      g->gcdept -= GCSTEPSIZE;
      g->GCthreshold = g->totalbytes;
    }
  }
  else {
    setthreshold(g);
  }
}
{{< /highlight >}}


<div class="src-block-caption">
  <span class="src-block-number">Code Snippet 4</span>:
  lgc.c
</div>

其中调用 singlestep 来进行每个 phase 操作，其中统计处理的对象空间大小的和，
达到阈值就结束此次增量 gc 过程。

{{< highlight C "linenos=table, linenostart=556" >}}
static l_mem singlestep (lua_State *L) {
  global_State *g = G(L);
  /*lua_checkmemory(L);*/
  switch (g->gcstate) {
    case GCSpause: {
      markroot(L);  /* start a new collection */
      return 0;
    }
    case GCSpropagate: {
      if (g->gray)
	return propagatemark(g);
      else {  /* no more `gray' objects */
	atomic(L);  /* finish mark phase */
	return 0;
      }
    }
    case GCSsweepstring: {
      lu_mem old = g->totalbytes;
      sweepwholelist(L, &g->strt.hash[g->sweepstrgc++]);
      if (g->sweepstrgc >= g->strt.size)  /* nothing more to sweep? */
	g->gcstate = GCSsweep;  /* end sweep-string phase */
      lua_assert(old >= g->totalbytes);
      g->estimate -= old - g->totalbytes;
      return GCSWEEPCOST;
    }
    case GCSsweep: {
      lu_mem old = g->totalbytes;
      g->sweepgc = sweeplist(L, g->sweepgc, GCSWEEPMAX);
      if (*g->sweepgc == NULL) {  /* nothing more to sweep? */
	checkSizes(L);
	g->gcstate = GCSfinalize;  /* end sweep phase */
      }
      lua_assert(old >= g->totalbytes);
      g->estimate -= old - g->totalbytes;
      return GCSWEEPMAX*GCSWEEPCOST;
    }
    case GCSfinalize: {
      if (g->tmudata) {
	GCTM(L);
	if (g->estimate > GCFINALIZECOST)
	  g->estimate -= GCFINALIZECOST;
	return GCFINALIZECOST;
      }
      else {
	g->gcstate = GCSpause;  /* end collection */
	g->gcdept = 0;
	return 0;
      }
    }
    default: lua_assert(0); return 0;
  }
}
{{< /highlight >}}


<div class="src-block-caption">
  <span class="src-block-number">Code Snippet 5</span>:
  lgc.c
</div>


### push {#push}

push 阶段从 root 开始，

{{< highlight C "linenos=table, linenostart=500" >}}
/* mark root set */
static void markroot (lua_State *L) {
  global_State *g = G(L);
  g->gray = NULL;
  g->grayagain = NULL;
  g->weak = NULL;
  markobject(g, g->mainthread);
  /* make global table be traversed before main stack */
  markvalue(g, gt(g->mainthread));
  markvalue(g, registry(L));
  markmt(g);
  g->gcstate = GCSpropagate;
}
{{< /highlight >}}


<div class="src-block-caption">
  <span class="src-block-number">Code Snippet 6</span>:
  lgc.c
</div>

从 markroot 可以看出，gc 中的 root 从 mainthread registry globalState 开始。


### pop {#pop}

pop 阶段的主要入口在 propagatemark，

{{< highlight C "linenos=table, linenostart=273" >}}
/*
** traverse one gray object, turning it to black.
** Returns `quantity' traversed.
*/
static l_mem propagatemark (global_State *g) {
  GCObject *o = g->gray;
  lua_assert(isgray(o));
  gray2black(o);
  switch (o->gch.tt) {
    case LUA_TTABLE: {
      Table *h = gco2h(o);
      g->gray = h->gclist;
      if (traversetable(g, h))  /* table is weak? */
	black2gray(o);  /* keep it gray */
      return sizeof(Table) + sizeof(TValue) * h->sizearray +
			     sizeof(Node) * sizenode(h);
    }
    case LUA_TFUNCTION: {
      Closure *cl = gco2cl(o);
      g->gray = cl->c.gclist;
      traverseclosure(g, cl);
      return (cl->c.isC) ? sizeCclosure(cl->c.nupvalues) :
			   sizeLclosure(cl->l.nupvalues);
    }
    case LUA_TTHREAD: {
      lua_State *th = gco2th(o);
      g->gray = th->gclist;
      th->gclist = g->grayagain;
      g->grayagain = o;
      black2gray(o);
      traversestack(g, th);
      return sizeof(lua_State) + sizeof(TValue) * th->stacksize +
				 sizeof(CallInfo) * th->size_ci;
    }
    case LUA_TPROTO: {
      Proto *p = gco2p(o);
      g->gray = p->gclist;
      traverseproto(g, p);
      return sizeof(Proto) + sizeof(Instruction) * p->sizecode +
			     sizeof(Proto *) * p->sizep +
			     sizeof(TValue) * p->sizek +
			     sizeof(int) * p->sizelineinfo +
			     sizeof(LocVar) * p->sizelocvars +
			     sizeof(TString *) * p->sizeupvalues;
    }
    default: lua_assert(0); return 0;
  }
}
{{< /highlight >}}


<div class="src-block-caption">
  <span class="src-block-number">Code Snippet 7</span>:
  lgc.c
</div>

其中针对不同的对象类型，进行不同的处理。


### sweep {#sweep}

sweep 阶段通过 sweeplist 遍历并回收白色对象，

{{< highlight C "linenos=table, linenostart=404" >}}
#define sweepwholelist(L,p)	sweeplist(L,p,MAX_LUMEM)


static GCObject **sweeplist (lua_State *L, GCObject **p, lu_mem count) {
  GCObject *curr;
  global_State *g = G(L);
  int deadmask = otherwhite(g);
  while ((curr = *p) != NULL && count-- > 0) {
    if (curr->gch.tt == LUA_TTHREAD)  /* sweep open upvalues of each thread */
      sweepwholelist(L, &gco2th(curr)->openupval);
    if ((curr->gch.marked ^ WHITEBITS) & deadmask) {  /* not dead? */
      lua_assert(!isdead(g, curr) || testbit(curr->gch.marked, FIXEDBIT));
      makewhite(g, curr);  /* make it white (for next cycle) */
      p = &curr->gch.next;
    }
    else {  /* must erase `curr' */
      lua_assert(isdead(g, curr) || deadmask == bitmask(SFIXEDBIT));
      *p = curr->gch.next;
      if (curr == g->rootgc)  /* is the first element of the list? */
	g->rootgc = curr->gch.next;  /* adjust first */
      freeobj(L, curr);
    }
  }
  return p;
}
{{< /highlight >}}


<div class="src-block-caption">
  <span class="src-block-number">Code Snippet 8</span>:
  lgc.c
</div>

最终通过 freeobj 回收相应内存空间，

{{< highlight C "linenos=table, linenostart=378" >}}
static void freeobj (lua_State *L, GCObject *o) {
  switch (o->gch.tt) {
    case LUA_TPROTO: luaF_freeproto(L, gco2p(o)); break;
    case LUA_TFUNCTION: luaF_freeclosure(L, gco2cl(o)); break;
    case LUA_TUPVAL: luaF_freeupval(L, gco2uv(o)); break;
    case LUA_TTABLE: luaH_free(L, gco2h(o)); break;
    case LUA_TTHREAD: {
      lua_assert(gco2th(o) != L && gco2th(o) != G(L)->mainthread);
      luaE_freethread(L, gco2th(o));
      break;
    }
    case LUA_TSTRING: {
      G(L)->strt.nuse--;
      luaM_freemem(L, o, sizestring(gco2ts(o)));
      break;
    }
    case LUA_TUSERDATA: {
      luaM_freemem(L, o, sizeudata(gco2u(o)));
      break;
    }
    default: lua_assert(0);
  }
}
{{< /highlight >}}


<div class="src-block-caption">
  <span class="src-block-number">Code Snippet 9</span>:
  lgc.c
</div>


## barrier {#barrier}

`luaC_barrierf` 和 `luaC_barrierback` 提供了 forward barrier 和 backward barrier 的实现。

{{< highlight C "linenos=table, linenostart=661" >}}
void luaC_barrierf (lua_State *L, GCObject *o, GCObject *v) {
  global_State *g = G(L);
  lua_assert(isblack(o) && iswhite(v) && !isdead(g, v) && !isdead(g, o));
  lua_assert(g->gcstate != GCSfinalize && g->gcstate != GCSpause);
  lua_assert(ttype(&o->gch) != LUA_TTABLE);
  /* must keep invariant? */
  if (g->gcstate == GCSpropagate)
    reallymarkobject(g, v);  /* restore invariant */
  else  /* don't mind */
    makewhite(g, o);  /* mark as white just to avoid other barriers */
}


void luaC_barrierback (lua_State *L, Table *t) {
  global_State *g = G(L);
  GCObject *o = obj2gco(t);
  lua_assert(isblack(o) && !isdead(g, o));
  lua_assert(g->gcstate != GCSfinalize && g->gcstate != GCSpause);
  black2gray(o);  /* make table gray (again) */
  t->gclist = g->grayagain;
  g->grayagain = o;
}
{{< /highlight >}}


<div class="src-block-caption">
  <span class="src-block-number">Code Snippet 10</span>:
  lgc.c
</div>

在 Lua 内部，只有 table 对象使用 backward barrier，因为其作为容器，
引用其它可变动的对象比较多，置为灰色就不用一直触发写屏障，提高效率。


## practice {#practice}

| 章节涉及文件 | 建议阅读程度 |
|--------|--------|
| lgc.h  | ★ ★ ★ ★ ☆ |
| lgc.c  | ★ ★ ★ ☆ ☆ |

[^fn:1]: : <http://wiki.luajit.org/New-Garbage-Collector#gc-algorithms>
