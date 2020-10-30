# read lua source code

https://www.reddit.com/r/programming/comments/63hth/ask_reddit_which_oss_codebases_out_there_are_so/c02pxbp/

Recommended reading order:

    lmathlib.c, lstrlib.c: get familiar with the external C API. Don't bother with the pattern matcher though. Just the easy functions.

    lapi.c: Check how the API is implemented internally. Only skim this to get a feeling for the code. Cross-reference to lua.h and luaconf.h as needed.

    lobject.h: tagged values and object representation. skim through this first. you'll want to keep a window with this file open all the time.

    lstate.h: state objects. ditto.

    lopcodes.h: bytecode instruction format and opcode definitions. easy.

    lvm.c: scroll down to luaV_execute, the main interpreter loop. see how all of the instructions are implemented. skip the details for now. reread later.

    ldo.c: calls, stacks, exceptions, coroutines. tough read.

    lstring.c: string interning. cute, huh?

    ltable.c: hash tables and arrays. tricky code.

    ltm.c: metamethod handling, reread all of lvm.c now.

    You may want to reread lapi.c now.

    ldebug.c: surprise waiting for you. abstract interpretation is used to find object names for tracebacks. does bytecode verification, too.

    lparser.c, lcode.c: recursive descent parser, targetting a register-based VM. start from chunk() and work your way through. read the expression parser and the code generator parts last.

    lgc.c: incremental garbage collector. take your time.

    Read all the other files as you see references to them. Don't let your stack get too deep though.

If you're done before X-Mas and understood all of it, you're good. The information density of the code is rather high.



https://github.com/italomaia/read-lua-source-code
 


## questions


## idea

阅读的顺序是重要的，提纲挈领

https://www.zhihu.com/question/20617406

http://mosswang.com/tags/Lua/

https://jin-yang.github.io/post/lua-sourcecode.html

https://github.com/lichuang/Lua-Source-Internal

https://blog.csdn.net/yuanlin2008/category_1307277.html




tools

https://github.com/mkottman/lua-gdb-helper

https://stackoverflow.com/questions/8528503/how-can-i-get-the-lua-stack-trace-from-a-core-file-using-gdb



### lua lexical analyzer

https://github.com/LoganDark/lua-lexer

how to use lua internal func to build a lexer?

how to use flex to parse lua token?


### parser

EBNF 语法描述

描述全都写在 lparser.c 的 function comment 中，after luaY_parser ?


```
chunk -> { stat [;] }
stat -> 
```

## how to debug

CFLAGS -> -ggdb3 -O0  (debug macros)

make echo check

https://stackoverflow.com/questions/8528503/how-can-i-get-the-lua-stack-trace-from-a-core-file-using-gdb

https://zeux.io/2010/11/07/lua-callstack-with-c-debugger/

http://lua-users.org/wiki/SimpleLuaApiExample



```
$ ./install/bin/luac -l test/test.lua

main <test/test.lua:0,0> (5 instructions, 20 bytes at 0x556a47004860)
0+ params, 3 slots, 0 upvalues, 1 local, 2 constants, 0 functions
        1       [1]     LOADK           0 -1    ; 1
        2       [2]     GETGLOBAL       1 -2    ; print
        3       [2]     MOVE            2 0
        4       [2]     CALL            1 2 1
        5       [2]     RETURN          0 1
```




## modify

makefile -m32


chunkspy, add is_vararg

```
+    BriefLine(string.format("; %d upvalues, %d params, %d is_vararg, %d stacks",
+      func.nups, func.numparams, func.is_vararg, func.maxstacksize))
```

## step

- front end
  - lex -> parse -> bytecode
- back end
  - vm run
  - c api

- gc
- debug



### data structure

```c
struct LexState {
    int current;              // 当前 token 之后，在代码中，下一个即将读入的字符
    int linenumber;           // 当前 token 所处的源代码行号
    int lastline;             // 上一个 token 所处的源代码行号
    Token t;                  // 当前 token
    Token lookahead;          // 下一个 token
    struct FuncState *fs;     // 当前的 FuncState
    struct lua_State *L;      // 当前 lua_State
    ZIO *z;                   // 源代码输入流的封装
    Mbuffer *buff;            // 临时存储 token 的地方？
    TString *source;          // 源代码的文件名
    char decpoint;            // 小数点的格式？国际化？
}
```



### frontend

global assignment

```lua
a = 1
```

```
; source chunk: (interactive mode)
; x86 standard (32-bit, little endian, doubles)

; function [0] definition (level 1)
; 0 upvalues, 0 params, 2 is_vararg, 2 stacks
.function  0 0 2 2
.const  "a"  ; 0
.const  4  ; 1
[1] loadk      0   1        ; 4
[2] setglobal  0   0        ; a
[3] return     0   1      
; end of function
```

```
#0  singlevar (ls=0xffffab64, var=0xffffaab8) at lparser.c:249
#1  0x56564e50 in prefixexp (ls=0xffffab64, v=0xffffaab8) at lparser.c:679
#2  0x56564eab in primaryexp (ls=0xffffab64, v=0xffffaab8) at lparser.c:694
#3  0x565665a1 in exprstat (ls=0xffffab64) at lparser.c:1228
#4  0x565668f1 in statement (ls=0xffffab64) at lparser.c:1318
#5  0x5656692d in chunk (ls=0xffffab64) at lparser.c:1330
```


ref global


local assignment


ref local


8 basic type
nil
bool
number
string
table
function
thread
userdata


multi var assignment

```lua
```

```lua
```


### backend

## features

- 8 basic types
  - nil
  - bool
  - number
  - string
  - function
  - table
    - metatable
  - thread
  - userdata

- function def
- function call
  - lexical scoping? static or dynamic?
  - closure and upvalue
  
- coroutine
  - semi or symmetric
  
- if else
- while
- for

- local
- global

- assignment
- uniop
- binop


- dofile, loadfile, load



## prefix

|prefix|module|
|:-:|:-:|
|luaX|lex|
|luaK|code|




