# parse




lua 中的 parse 过程使用 lazy 加载 token 的方式


按需加载 token










非 i 模式下，parse 将所有 tokne 生成了全部的 bytecode
最后再开始执行


这样就避免


```lua
local a = 1
print(a)

a
```

这种语法错误的情况，但是前面的代码已经执行的情况







parse 生成 bytecode，关于寄存器的使用，只是从表面上生成相应的索引
因为 parser 知道自己使用了哪些寄存器，还有哪些可以使用，这些信息是 运行时的 vm 所不知道的

move a b

但是并不分配寄存器的空间，只是用来调试使用哪个寄存器

因为这是编译时，而不是运行时






如此的情况下，运行 bytecode 的 vm 就很简单，完全按照 bytecode 的吩咐来执行就行了

就像物理机执行二进制指令一样。








递归下降法与 LL 1 的关系？








核心结构
- FuncState 每个层次的函数信息，只用来辅助生成 Proto
- Proto 最终生成的 bytecode 与相关环境





```c
typedef struct FuncState {
  Proto *f;                              // 存储生成的 bytecode
  Table *h;                              // k 表？
  struct FuncState *prev;                // 函数闭包的上层，同为 FuncState，仅在编译期存在
  struct LexState *ls;                   // 指向 LexState，获取 token
  struct lua_State *L;                   // lua_State，作用？
  struct BlockCnt *bl;                   // 和 prev 不冲突吗？
  int pc;                                // 下一个存储 bytecode 的索引，因为索引从 0 开始，所以此值等同于 ncode
  int lasttarget;                        // 上一个 jump target 的 pc 值
  int jpc;                               // ？ /* list of pending jumps to `pc' */
  int freereg;                           // 第一个空闲寄存器的索引
  int nk;                                // f 中 k 表的元素个数，也可做下一个可存储的 k 值索引
  int np;                                // 嵌套 proto 的个数？
  short nlocvars;                        // 存储在 f->locvars 中的数量
  lu_byte nactvar;                       // active local var 的个数
  upvaldesc upvalues[LUAI_MAXUPVALUES];  // 存储 upvalues？
  unsigned short actvar[LUAI_MAXVARS];   // 存储 active local vars，值是 locvar 在 f->locvars 中的索引
};
```

为什么 local var 和 active local var 存储在两个部分？
proto 和 funcstate


因为 active 状态只能在 parse 过程分辨。
离开作用域自然不是 active 的。

而是否 active 对于 bytecode 并不重要。

active 状态用于辅助 funcstate 生成 bytecode。






```c
typedef struct Proto {
  CommonHeader;
  TValue *k;               // k 表，数组实现，存储函数所有使用的常量
  Instruction *code;       // 存储字节码
  struct Proto **p;        // 函数内嵌套的函数
  int *lineinfo;           // opcode 与源代码行号的对应
  struct LocVar *locvars;  // local vars 的信息？
  TString **upvalues;      // ？
  TString  *source;        // 源代码的文件名
  int sizeupvalues;        // ？
  int sizek;               // k 表的大小，有可能会比实际 k 表中元素多
  int sizecode;            // code 指令个数
  int sizelineinfo;        // lineinfo 数组大小
  int sizep;               // 嵌套函数的个数？
  int sizelocvars;         // local vars 的个数？
  int linedefined;         // ？
  int lastlinedefined;     // 源码中函数的起点和终点？
  GCObject *gclist;        // ？
  lu_byte nups;            // ？ /* number of upvalues */
  lu_byte numparams;       // 参数的个数？
  lu_byte is_vararg;       // 是否可变参数？
  lu_byte maxstacksize;    // 栈的最大大小？
};
```








discharge vars
意思是解析变量，比如

```
a = 1
```

在赋值之间，要先解析 1，从 k 表中将 1 加载到栈中，
然后再设置到全局表。

解析 1 的过程就是 discharge。

生成的 bytecode 也就在 assignment 的前面。









lexical scoping 和 syntax scoping 的区别？
影响闭包的实现。










### frontend

#### global assignment

```lua
a = 1
```

```
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



singlevar，在 funcState 的结构搜索 var 的来源，是 local upvalue 还是 global。

通过 fs->prev 不断向上查找


from fs->nactvar -> 0，对比 varname




#### ref global








#### local assignment


```lua
local a = 10
```

将 10 存入 k 表，将 "a" 存入 k 表，locvars 表中。（10 是值，可以直接引用；a 是符号，需要一层解析，才可得到值）
使用 loadk 指令，将 k 中的 10 加载入 reg 中。



通过 numberK 和 stringK 方法





#### ref local






---

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




