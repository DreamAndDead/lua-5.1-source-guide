---
title: "lexer"
author: ["DreamAndDead"]
date: 2021-01-05T16:40:00+08:00
lastmod: 2021-02-23T11:53:27+08:00
draft: false
---

之前的章节，关注的是内部的一些实现，为后续打基础。

后续的章节关注 lua 是如何从文本代码到最终实际运行起来的。

本章关注 lua 中的词法分析部分，即 lexer，这通常是编译过程的第一步。


## lexer {#lexer}

传统的编译过程大家都不陌生。

{{< figure src="compiler-trandition.png" >}}

lua 是解释型语言，但同样存在从源码到字节码的编译过程，区别在于其运行在 VM 上。

经过历史的演变，lua 的内部实现为了效率，遵从如下的过程。

{{< figure src="compiler-lua-detail-process.png" >}}

AST 使用虚线表示，是因为内部没有显式的 AST 结构。

综合来看，lexer 完成了从 code 到 token 的过程，
parser 孤身一人完成了从 token 到 opcode 的过程。

{{< figure src="lexer-feature.png" >}}

单纯从从文件角度看，lua 代码只是文本文件，由字符组成。
文本形式的编程语言由机器理解并执行，需要经过一系列组件的处理过程。
不同组件有明确的分工，不同的组件有不同的输入和输出，组成上下游关系。

lexer 通常是第一个组件，将源代码转换为 token，将字符流转化为 token 流，作为后续 parser 的输入。

{{< figure src="lexer-stream.png" >}}


## Token {#token}

简单的说，token 就是多个字符组成的有序序列。

lua 内部用 struct 表示 token，

{{< highlight c "linenos=table, linenostart=43" >}}
typedef union {
  lua_Number r;
  TString *ts;
} SemInfo;  /* semantics information */


typedef struct Token {
  int token;
  SemInfo seminfo;
} Token;
{{< /highlight >}}


<div class="src-block-caption">
  <span class="src-block-number">Code Snippet 1</span>:
  llex.h
</div>


### int token {#int-token}

token 定义为 int，表示 Token 的类型，所有类型定义在 enum 结构中。

{{< highlight c "linenos=table, linenostart=14" >}}
#define FIRST_RESERVED	257

/* maximum length of a reserved word */
#define TOKEN_LEN	(sizeof("function")/sizeof(char))


/*
* WARNING: if you change the order of this enumeration,
* grep "ORDER RESERVED"
*/
enum RESERVED {
  /* terminal symbols denoted by reserved words */
  TK_AND = FIRST_RESERVED, TK_BREAK,
  TK_DO, TK_ELSE, TK_ELSEIF, TK_END, TK_FALSE, TK_FOR, TK_FUNCTION,
  TK_IF, TK_IN, TK_LOCAL, TK_NIL, TK_NOT, TK_OR, TK_REPEAT,
  TK_RETURN, TK_THEN, TK_TRUE, TK_UNTIL, TK_WHILE,
  /* other terminal symbols */
  TK_CONCAT, TK_DOTS, TK_EQ, TK_GE, TK_LE, TK_NE, TK_NUMBER,
  TK_NAME, TK_STRING, TK_EOS
};
{{< /highlight >}}


<div class="src-block-caption">
  <span class="src-block-number">Code Snippet 2</span>:
  llex.h
</div>

每个 token 类型都有对应的文本表示，

{{< highlight c "linenos=table, linenostart=36" >}}
/* ORDER RESERVED */
const char *const luaX_tokens [] = {
    "and", "break", "do", "else", "elseif",
    "end", "false", "for", "function", "if",
    "in", "local", "nil", "not", "or", "repeat",
    "return", "then", "true", "until", "while",
    "..", "...", "==", ">=", "<=", "~=",
    "<number>", "<name>", "<string>", "<eof>",
    NULL
};
{{< /highlight >}}


<div class="src-block-caption">
  <span class="src-block-number">Code Snippet 3</span>:
  llex.c
</div>

-   `and` 到 `while` 之间是所有关键字
-   `..` 到 `~=` 之间是二元运算符
-   `<number>` 表示数字字面量
-   `<name>` 表示变量名称
-   `<string>` 表示字符串字面量
-   `<eof>` 表示文件结束符

在上面所有类型中，看不到单字符 token 的影子，如 `( , . ; [` 。
这是因为单字符用单字节 ascii 码表示（0 - 255），可以直接用自身来表示，记录在 int token 中。
这也是多字符 token 从 `FIRST_RESERVED 257` 开始的原因，巧妙的将两者分开。


### Seminfo {#seminfo}

Seminfo 用于存储 token 类型对应的内容。

对于单字符，关键字和二元运算符，不需要记录额外内容，因为类型的文本表示是唯一的。
`<number> <name> <string>` 则不同，相应类型下存在无数可能的内容，这就是 seminfo 的作用。

-   `lua_Number r` 用来记录 `<number>` 相应的内容
-   `TString *ts` 用来记录 `<name>` 变量的名称， `<string>` 字符串内容


## LexState {#lexstate}

lex 是一个过程，过程中需要记录当下所处的状态，比如文件读取的位置，匹配的结果等，
这个关键的数据结构就是 LexState。

整个 lex 过程围绕 LexState 展开，这样说毫不为过，清楚其有非常大的助益。

{{< highlight C "linenos=table, linenostart=55" >}}
typedef struct LexState {
  int current;  /* current character (charint) */
  int linenumber;  /* input line counter */
  int lastline;  /* line of last token `consumed' */
  Token t;  /* current token */
  Token lookahead;  /* look ahead token */
  struct FuncState *fs;  /* `FuncState' is private to the parser */
  struct lua_State *L;
  ZIO *z;  /* input stream */
  Mbuffer *buff;  /* buffer for tokens */
  TString *source;  /* current source name */
  char decpoint;  /* locale decimal point */
} LexState;
{{< /highlight >}}


<div class="src-block-caption">
  <span class="src-block-number">Code Snippet 4</span>:
  llex.h
</div>

将其中所有字段分为 3 部分

lex 过程的重要部分

-   `ZIO *z` ，源代码文件流
-   `Mbuffer *buff` ，lex 匹配过程中的 buffer
-   `int current` ，当前 token 之后紧跟的字符
-   `Token t` ，当前 token
-   `Token lookahead` ，前瞻的下一个 token

在 parser 章节再讨论

-   `struct FuncState *fs`
-   `struct lua_State *L`

非重点，暂不讨论

-   `int linenumber` ，当前 current 所处行号
-   `int lastline` ，上一个 token 所处行号
-   `TString *source` ，源代码的名称
-   `char decpoint` ，和数字的 l10n 相关

{{< figure src="lexer-lexstate-inside.png" >}}

内部数据间的协同，在 method 小节继续讲述。


## method {#method}


### `luaX_init` {#luax-init}

前面在 string 章节，关于其中 reserved 字段的作用没有讲述，刚好在 lexer 章节补上。

{{< highlight c "linenos=table, linenostart=35" >}}
/* number of reserved words */
#define NUM_RESERVED	(cast(int, TK_WHILE-FIRST_RESERVED+1))
{{< /highlight >}}


<div class="src-block-caption">
  <span class="src-block-number">Code Snippet 5</span>:
  llex.h
</div>

{{< highlight c "linenos=table, linenostart=64" >}}
void luaX_init (lua_State *L) {
  int i;
  for (i=0; i<NUM_RESERVED; i++) {
    TString *ts = luaS_new(L, luaX_tokens[i]);
    luaS_fix(ts);  /* reserved words are never collected */
    lua_assert(strlen(luaX_tokens[i])+1 <= TOKEN_LEN);
    ts->tsv.reserved = cast_byte(i+1);  /* reserved word */
  }
}
{{< /highlight >}}


<div class="src-block-caption">
  <span class="src-block-number">Code Snippet 6</span>:
  llex.c
</div>

之前提到，string 在 lua 内部只保存一份，是不可修改的。

`luaX_init` 将所有关键字（如 `local function end` 等）预先分配，存储入全局表。
特别的，在其 reserved 字段上记录其在 `enum RESERVED` 中的序号，从 1 开始。

这样带来的效果是，所有 reserved != 0 的 string 都是关键字，且可以由 reserved 来判断出关键字的 token 类型。

这一点间接方便了 `luaX_next` 中，关键字类型 token 的判断过程。


### `llex` {#llex}

本质上来看，lexer 就是遵循些许模式，从字符流的头部开始匹配，找到并返回相匹配的 token。

不同 token 的模式通常用 regex 来描述，将所有的模式转化为代码的形式，就是 lex 过程。

一般而言，这是一个相对枯燥又考验耐心的工作，好在有 lexer generator 这样的工具，如 flex，
它可以直接将 regex 规则转化为 lex 代码。

一般而言，一个语言的诞生初期，都会使用 lexer generator，方便快速迭代，
到了后期语言本身相对稳定的时候，为了提升效率，都会将 lex 过程重写，python ruby lua 都是如此。

这也意味着，阅读 lua 中 lex 过程的代码不如同义的 flex 代码[^fn:1]轻松。

lex 过程看似随意，底层其实有充足的数学理论支撑， `regex NFA DFA` 的同义转化，最终用代码方式呈现。
这一点远有更专业的书来讲解，具体细节就不再赘述。

lexer 内部的核心方法就是 llex。

{{< highlight c "linenos=table, linenostart=334" >}}
static int llex (LexState *ls, SemInfo *seminfo) {
  luaZ_resetbuffer(ls->buff);
  for (;;) {
    switch (ls->current) {
      case '\n':
      case '\r': {
	inclinenumber(ls);
	continue;
      }
      case '-': {
	next(ls);
	if (ls->current != '-') return '-';
	/* else is a comment */
	next(ls);
	if (ls->current == '[') {
	  int sep = skip_sep(ls);
	  luaZ_resetbuffer(ls->buff);  /* `skip_sep' may dirty the buffer */
	  if (sep >= 0) {
	    read_long_string(ls, NULL, sep);  /* long comment */
	    luaZ_resetbuffer(ls->buff);
	    continue;
	  }
	}
	/* else short comment */
	while (!currIsNewline(ls) && ls->current != EOZ)
	  next(ls);
	continue;
      }
      case '[': {
	int sep = skip_sep(ls);
	if (sep >= 0) {
	  read_long_string(ls, seminfo, sep);
	  return TK_STRING;
	}
	else if (sep == -1) return '[';
	else luaX_lexerror(ls, "invalid long string delimiter", TK_STRING);
      }
      case '=': {
	next(ls);
	if (ls->current != '=') return '=';
	else { next(ls); return TK_EQ; }
      }
      case '<': {
	next(ls);
	if (ls->current != '=') return '<';
	else { next(ls); return TK_LE; }
      }
      case '>': {
	next(ls);
	if (ls->current != '=') return '>';
	else { next(ls); return TK_GE; }
      }
      case '~': {
	next(ls);
	if (ls->current != '=') return '~';
	else { next(ls); return TK_NE; }
      }
      case '"':
      case '\'': {
	read_string(ls, ls->current, seminfo);
	return TK_STRING;
      }
      case '.': {
	save_and_next(ls);
	if (check_next(ls, ".")) {
	  if (check_next(ls, "."))
	    return TK_DOTS;   /* ... */
	  else return TK_CONCAT;   /* .. */
	}
	else if (!isdigit(ls->current)) return '.';
	else {
	  read_numeral(ls, seminfo);
	  return TK_NUMBER;
	}
      }
      case EOZ: {
	return TK_EOS;
      }
      default: {
	if (isspace(ls->current)) {
	  lua_assert(!currIsNewline(ls));
	  next(ls);
	  continue;
	}
	else if (isdigit(ls->current)) {
	  read_numeral(ls, seminfo);
	  return TK_NUMBER;
	}
	else if (isalpha(ls->current) || ls->current == '_') {
	  /* identifier or reserved word */
	  TString *ts;
	  do {
	    save_and_next(ls);
	  } while (isalnum(ls->current) || ls->current == '_');
	  ts = luaX_newstring(ls, luaZ_buffer(ls->buff),
				  luaZ_bufflen(ls->buff));
	  if (ts->tsv.reserved > 0)  /* reserved word? */
	    return ts->tsv.reserved - 1 + FIRST_RESERVED;
	  else {
	    seminfo->ts = ts;
	    return TK_NAME;
	  }
	}
	else {
	  int c = ls->current;
	  next(ls);
	  return c;  /* single-char tokens (+ - / ...) */
	}
      }
    }
  }
}
{{< /highlight >}}


<div class="src-block-caption">
  <span class="src-block-number">Code Snippet 7</span>:
  llex.c
</div>

它的功能非常纯粹，从字符流的开始，进行模式匹配，找到相应的 token，并返回相应的类型和内容。

{{< figure src="lexer-matching-process-0.png" >}}

{{< figure src="lexer-matching-process-1.png" >}}

{{< figure src="lexer-matching-process-2.png" >}}

llex 的具体过程不再赘述，读者可以打开调试器，用一些代码示例来针对性的阅读。

这里只略微提几个值得关注的点。


#### keyword {#keyword}

关键字的匹配过程，和 `<name>` 的匹配过程统一在一起。

不过是在最终得到匹配结果时，通过 reserved 字段来判断，是否是关键字。
之所以可以做到这一点是因为，所有 string 在全局表中都是唯一的，
而且 `luaX_init` 已经提前设置了所有的关键字。

{{< highlight c "linenos=table, linenostart=422" >}}
else if (isalpha(ls->current) || ls->current == '_') {
  /* identifier or reserved word */
  TString *ts;
  do {
    save_and_next(ls);
  } while (isalnum(ls->current) || ls->current == '_');
  ts = luaX_newstring(ls, luaZ_buffer(ls->buff),
			  luaZ_bufflen(ls->buff));
  if (ts->tsv.reserved > 0)  /* reserved word? */
    return ts->tsv.reserved - 1 + FIRST_RESERVED;
  else {
    seminfo->ts = ts;
    return TK_NAME;
  }
}
{{< /highlight >}}


<div class="src-block-caption">
  <span class="src-block-number">Code Snippet 8</span>:
  llex.c
</div>

这个巧妙的过程，意味着关键字的优先级高于标识符。

定义与关键字同名的变量是不可能的，因为它会被辨别为是关键字，引发语法错误。

```lua
local end = 1
```


#### number {#number}

理想情况下，token 类型的识别在前，类型确定后，再来提取相应的内容。

但是对于 `<number>` 并不是这样来处理的。

{{< highlight c "linenos=table, linenostart=193" >}}
/* LUA_NUMBER */
static void read_numeral (LexState *ls, SemInfo *seminfo) {
  lua_assert(isdigit(ls->current));
  do {
    save_and_next(ls);
  } while (isdigit(ls->current) || ls->current == '.');
  if (check_next(ls, "Ee"))  /* `E'? */
    check_next(ls, "+-");  /* optional exponent sign */
  while (isalnum(ls->current) || ls->current == '_')
    save_and_next(ls);
  save(ls, '\0');
  buffreplace(ls, '.', ls->decpoint);  /* follow locale for decimal point */
  if (!luaO_str2d(luaZ_buffer(ls->buff), &seminfo->r))  /* format error? */
    trydecpoint(ls, seminfo); /* try to update decimal point separator */
}
{{< /highlight >}}


<div class="src-block-caption">
  <span class="src-block-number">Code Snippet 9</span>:
  llex.c
</div>

如果用 regex 来表示这个过程，则是 `[\.[:digit:]]+[Ee[+-]?]?[[:alnum:]_]*` ，
这个模式并不能完全匹配数字。

```lua
local i = .3.3.3
```

`.3.3.3` 可以匹配相应模式，但是并不是数字。

庆幸的是 lua 依旧发现这个错误，

```text
malformed number near '.3.3.3'
```

lua 内部使用 `<stdlib.h>` 中的 strtod 来尝试进行 string 到 number 的转换。
如果发生错误，则说明不是数字。

{{< highlight c "linenos=table, linenostart=525" >}}
#define lua_str2number(s,p)	strtod((s), (p))
{{< /highlight >}}


<div class="src-block-caption">
  <span class="src-block-number">Code Snippet 10</span>:
  luaconf.h
</div>

看起来这并不合常规，因为 lua 只是粗略匹配了一段“像是 number”的内容，通过 strtod 来做最终判断，
感觉有些取巧。


#### long string {#long-string}

lua 中可以用 `[[]]` 来表示长字符串，但是存在一种变体，比较少见，
形式如 `[===[ ]===]` 也是长字符串， `=` 的数量要完全相同。

长字符串的规则，加上 `--` 就可以扩充到长注释。

```lua
local long_str = [[
this is a long string.
]]

local another_str = [===[
another long string.
]===]

--[[
comment this line
]]

--[====[
comment this line
]====]
```

这一点在阅读代码时要注意。


#### builtin {#builtin}

`next, require` 等不是关键字，而是运行环境中提供的函数，它们的功能是在 VM 中实现的。

这一点在后续 api 章节会讲到。


### `luaX_lookahead` {#luax-lookahead}

在语法分析的过程中，存在少数情况，需要下一个 token 来去除多个模式间的歧义。

`luaX_lookahead` 就是在这个时候使用，

{{< highlight c "linenos=table, linenostart=459" >}}
void luaX_lookahead (LexState *ls) {
  lua_assert(ls->lookahead.token == TK_EOS);
  ls->lookahead.token = llex(ls, &ls->lookahead.seminfo);
}
{{< /highlight >}}


<div class="src-block-caption">
  <span class="src-block-number">Code Snippet 11</span>:
  llex.c
</div>

过程很简单，使用 `llex` 方法，将 token 存储在 LexState.lookahead 中。

{{< figure src="lexer-lookahead.png" >}}


### `luaX_next` {#luax-next}

`luaX_next` 和 `luaX_lookahead` 相同，不过是将 token 存储在 LexState.t 中。

如果 lookahead 中存在 token，则直接拿过来使用，并重置 lookahead。

{{< highlight c "linenos=table, linenostart=448" >}}
void luaX_next (LexState *ls) {
  ls->lastline = ls->linenumber;
  if (ls->lookahead.token != TK_EOS) {  /* is there a look-ahead token? */
    ls->t = ls->lookahead;  /* use this one */
    ls->lookahead.token = TK_EOS;  /* and discharge it */
  }
  else
    ls->t.token = llex(ls, &ls->t.seminfo);  /* read next token */
}
{{< /highlight >}}


<div class="src-block-caption">
  <span class="src-block-number">Code Snippet 12</span>:
  llex.c
</div>

{{< figure src="lexer-next.png" >}}

{{< figure src="lexer-next-next.png" >}}


## a little lexer {#a-little-lexer}

根据对 lex 模块的理解，可以做一个简单的 lexer 分析器。

它不是一个独立的程序，而是一段 gdb 脚本，gdb 可以在 lua 在运行时进行 inspect。

在 `luaX_next` 方法加上断点，每次触发的时候，就输出相应的 token，就可以实现一个简单的 lexer 工具。

```bash
$ make -s lex source=./test/co.lua
```

这种做法有些许弱点，如果中途出现语法错误，过程就会中断，所以它只能分析语法分析正确的代码。


## practice {#practice}

| 文件   | 建议                                                       |
|------|----------------------------------------------------------|
| lzio.h | zio 模块中实现了 zio 和 mbuffer 结构，对字符流和 buffer 进行了封装，感兴趣的读者可仔细阅读 |
| lzio.c | 同上                                                       |
| llex.h | 仔细阅读                                                   |
| llex.c | 浏览阅读，配合调试器会更轻松                               |

[^fn:1]: : <http://lua-users.org/lists/lua-l/2005-12/msg00091.html>
