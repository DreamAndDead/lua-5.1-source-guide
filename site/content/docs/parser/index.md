---
title: "parser"
author: ["DreamAndDead"]
date: 2021-01-07T15:46:00+08:00
lastmod: 2021-02-23T11:57:33+08:00
draft: false
---

在 lexer 章节提到，lua 为了效率，将语法分析到代码生成的所有功能封装在 parser 模块中。
在过程中，没有 AST IR 等中间产物，直接从 token 到 opcode，一步到位。
相对的，这部分代码就相对难以理解。

虽然在代码实现没有明显的步骤划分，但是对于读者，
在理解代码过程中，还是先找出不同步骤的影子，最后再串联在一起。

这个章节，就是尝试从代码中“分离”出语法分析的部分，先对模块做初步的理解。

{{< figure src="parser-feature.png" >}}


## grammar {#grammar}

模块以语法分析作为入口，整体是一个语法制导翻译的过程。

官方文档[^fn:1]使用上下文无关文法来描述 lua 语法，但是省略了一些细节。
笔者结合 parser 代码中的实现过程和相关注释，重新整理语法描述如下，使用 EBNF 描述。

```bnf
chunk        ::= { stat [ `;' ] }

stat         ::= ifstat | whilestat | dostat | forstat | repeatstat |
		   funcstat | localstat | retstat | breakstat | exprstat

ifstat       ::= IF cond THEN block {ELSEIF cond THEN block} [ELSE block] END
cond         ::= expr
block        ::= chunk

whilestat    ::= WHILE cond DO block END

dostat       ::= DO block END

forstat      ::= FOR (fornum | forlist) END
fornum       ::= NAME = expr `,' expr [`,' expr] forbody
forlist      ::= NAME {`,' NAME} IN explist forbody
forbody      ::= DO block

repeatstat   ::= REPEAT block UNTIL cond

funcstat     ::= FUNCTION funcname body
funcname     ::= NAME {`.' NAME} [`:' NAME]
body         ::= `(' parlist `)' chunk END
parlist      ::= [ DOTS | NAME {`,' NAME} [`,' DOTS] ]

localstat    ::= LOCAL FUNCTION NAME body | LOCAL NAME {`,' NAME} [`=' explist]

retstat      ::= RETURN [explist]

breakstat    ::= BREAK

exprstat     ::= assignstat | funccallstat

assignstat   ::= (prefixexp | primaryexp (`.' NAME | `[' expr `]')) assignment
assignment   ::= `,' assignstat | `=' explist

primaryexp   ::= prefixexp {`.' NAME | `[' expr `]' | `:' NAME funcargs | funcargs}
prefixexp    ::= NAME | `(' expr `)'

funccallstat ::= prefixexp primaryexp (`:' NAME funcargs | funcargs)
funcargs     ::= `(' [ explist ] `)' | constructor | STRING

explist      ::= expr {`,' expr}
expr         ::= subexpr
subexpr      ::= (simpleexp | unop subexpr) {binop subexpr}

simpleexp    ::= NUMBER | STRING | NIL | TRUE | FALSE | DOTS |
		 constructor | FUNCTION body | primaryexp

binop        ::= `+´ | `-´ | `*´ | `/´ | `^´ | `%´ | CONCAT |
		 `<´ | LE | `>´ | GE | EQ | NE | AND | OR
unop         ::= `-´ | NOT | `#´

constructor  ::= `{' [fieldlist] `}'
fieldlist    ::= field {fieldsep field} [fieldsep]
field        ::= `[' expr `]' `=' expr | NAME `=' expr | expr
fieldsep     ::= `,' | `;'
```

-   `{ a }` 表示 0 个或多个 a
-   `[ a ]` 表示 0 个或一个 a
-   `( a )` 表示组
-   `|`  表示或
-   大写单词，\`单字符' 表示终结符，和 lex 阶段生成的 token 一一对应
-   小写单词 表示非终结符，整体以 chunk 为入口

之前提到，在 lex 过程，lua 并没有完全使用 regex 对词法做完整的限制，存在些许不完美的实现。
同样的“问题”在语法分析的 EBNF 描述中也存在。


### binop {#binop}

在语法描述上，没有控制二元运算的优先级，而是将优先级在 subexpr 过程中用代码隐式实现。


### break {#break}

break 语句位置并不是随意的，只能放置在 loop 块中，而语法描述并没有描述这种限制，
同样的，lua 将此限制实现在代码层面。


### return {#return}

return 语句只能放置在块的最后一行，而语法描述没有表示出此种限制。


## recursive descent {#recursive-descent}

parser 模块使用 LL(1) 递归下降法进行语法分析。

递归下降法有一个明显的优点，通常在实现中，
每个非终结符都对应一个同名函数来实现，如 `chunk() statement()` 等。

{{< highlight c "linenos=table, linenostart=1271" >}}
static int statement (LexState *ls) {
  int line = ls->linenumber;  /* may be needed for error messages */
  switch (ls->t.token) {
    case TK_IF: {  /* stat -> ifstat */
      ifstat(ls, line);
      return 0;
    }
    case TK_WHILE: {  /* stat -> whilestat */
      whilestat(ls, line);
      return 0;
    }
    case TK_DO: {  /* stat -> DO block END */
      luaX_next(ls);  /* skip DO */
      block(ls);
      check_match(ls, TK_END, TK_DO, line);
      return 0;
    }
    case TK_FOR: {  /* stat -> forstat */
      forstat(ls, line);
      return 0;
    }
    case TK_REPEAT: {  /* stat -> repeatstat */
      repeatstat(ls, line);
      return 0;
    }
    case TK_FUNCTION: {
      funcstat(ls, line);  /* stat -> funcstat */
      return 0;
    }
    case TK_LOCAL: {  /* stat -> localstat */
      luaX_next(ls);  /* skip LOCAL */
      if (testnext(ls, TK_FUNCTION))  /* local function? */
	localfunc(ls);
      else
	localstat(ls);
      return 0;
    }
    case TK_RETURN: {  /* stat -> retstat */
      retstat(ls);
      return 1;  /* must be last statement */
    }
    case TK_BREAK: {  /* stat -> breakstat */
      luaX_next(ls);  /* skip BREAK */
      breakstat(ls);
      return 1;  /* must be last statement */
    }
    default: {
      exprstat(ls);
      return 0;  /* to avoid warnings */
    }
  }
}


static void chunk (LexState *ls) {
  /* chunk -> { stat [`;'] } */
  int islast = 0;
  enterlevel(ls);
  while (!islast && !block_follow(ls->t.token)) {
    islast = statement(ls);
    testnext(ls, ';');
    lua_assert(ls->fs->f->maxstacksize >= ls->fs->freereg &&
	       ls->fs->freereg >= ls->fs->nactvar);
    ls->fs->freereg = ls->fs->nactvar;  /* free registers */
  }
  leavelevel(ls);
}
{{< /highlight >}}


<div class="src-block-caption">
  <span class="src-block-number">Code Snippet 1</span>:
  lparser.c
</div>

这些函数都有一个共性，全部都接收参数 `LexState *ls` ，从其得到 token。
部分函数接收参数 `expdesc* v` ，表示当前过程之后，得到的表达式结果。

`expdesc` 结构非常关键，在代码生成章节再详细描述。

{{< highlight c "linenos=table, linenostart=15" >}}
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
{{< /highlight >}}


<div class="src-block-caption">
  <span class="src-block-number">Code Snippet 2</span>:
  lparser.h
</div>

如此对照 EBNF 的语法描述，就可以方便地对语法分析的过程有大体的了解。

所有函数之间的调用过程，就像是隐式的 AST 的遍历过程。
代码生成的实现过程就隐藏在这一个个函数中。

{{< figure src="parser-ast.png" >}}

整体以 chunk 为入口，下分为多个 stat，每个 stat 有独立的结构，最终到基础的 expr 单元，
像一棵树形结构，自顶向下。


## practice {#practice}

`luaY_parser` 是 parser 模块的入口，

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
  <span class="src-block-number">Code Snippet 3</span>:
  lparser.c
</div>

Line 391 调用 chunk，开始递归向下的分析。

读者可以使用调试器，在 chunk 处加上断点，运行 lua 代码，
使用 next/step 观察内部运行的走向，对照 EBNF 来理解语法分析的整体结构。

```text
$ make -s debug source=if.lua
```

建议最开始以 stat 为单位，对每个 stat 进行独立的观察，最终再整合为宏观的理解。

[^fn:1]: : <http://www.lua.org/manual/5.1/manual.html#8>
