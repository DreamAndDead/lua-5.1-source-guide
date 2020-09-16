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

- what is lua_State




## idea


阅读的顺序是重要的，提纲挈领


查看 bytecode 和 source code 的联系
luac -l



https://www.zhihu.com/question/20617406

http://mosswang.com/tags/Lua/

https://jin-yang.github.io/post/lua-sourcecode.html

https://github.com/lichuang/Lua-Source-Internal

https://blog.csdn.net/yuanlin2008/category_1307277.html



tools

https://github.com/mkottman/lua-gdb-helper

https://stackoverflow.com/questions/8528503/how-can-i-get-the-lua-stack-trace-from-a-core-file-using-gdb



## how to debug

CFLAGS -> -g -O0

make echo check




https://stackoverflow.com/questions/8528503/how-can-i-get-the-lua-stack-trace-from-a-core-file-using-gdb

https://zeux.io/2010/11/07/lua-callstack-with-c-debugger/
