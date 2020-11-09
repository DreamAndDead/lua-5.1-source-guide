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
  Table *h;                              // global 表？
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







fs->f->sizek 和 fs->nk 是有区别的

nk 是随着实际情况准确的在变化，而 sizek 准确的说，更像是在记录扩容的空间大小

如 length 和 capacity 的区别

当然，最终分析完成之后，会使用赋值 sizek = nk，作为最终的生成结果






官方的描述

 Here is the complete syntax of Lua in extended BNF. (It does not describe operator precedences.)

```
	chunk ::= {stat [`;´]} [laststat [`;´]]

	block ::= chunk

	stat ::=  varlist `=´ explist | 
		 functioncall | 
		 do block end | 
		 while exp do block end | 
		 repeat block until exp | 
		 if exp then block {elseif exp then block} [else block] end | 
		 for Name `=´ exp `,´ exp [`,´ exp] do block end | 
		 for namelist in explist do block end | 
		 function funcname funcbody | 
		 local function Name funcbody | 
		 local namelist [`=´ explist] 

	laststat ::= return [explist] | break

	funcname ::= Name {`.´ Name} [`:´ Name]

	varlist ::= var {`,´ var}

	var ::=  Name | prefixexp `[´ exp `]´ | prefixexp `.´ Name 

	namelist ::= Name {`,´ Name}

	explist ::= {exp `,´} exp

	exp ::=  nil | false | true | Number | String | `...´ | function | 
		 prefixexp | tableconstructor | exp binop exp | unop exp 

	prefixexp ::= var | functioncall | `(´ exp `)´

	functioncall ::=  prefixexp args | prefixexp `:´ Name args 

	args ::=  `(´ [explist] `)´ | tableconstructor | String 

	function ::= function funcbody

	funcbody ::= `(´ [parlist] `)´ block end

	parlist ::= namelist [`,´ `...´] | `...´

	tableconstructor ::= `{´ [fieldlist] `}´

	fieldlist ::= field {fieldsep field} [fieldsep]

	field ::= `[´ exp `]´ `=´ exp | Name `=´ exp | exp

	fieldsep ::= `,´ | `;´

	binop ::= `+´ | `-´ | `*´ | `/´ | `^´ | `%´ | `..´ | 
		 `<´ | `<=´ | `>´ | `>=´ | `==´ | `~=´ | 
		 and | or

	unop ::= `-´ | not | `#´
```



EBNF

```
chunk -> { stat [ `;' ] }
stat -> ifstat | whilestat | dostat | forstat | repeatstat | funcstat | localstat | retstat | breakstat | exprstat





localstat -> LOCAL FUNCTION NAME funcbody | LOCAL NAME {`,' NAME} [`=' explist1]



# exprstat -> primaryexp
# primaryexp -> prefixexp {`.' NAME | `[' expr `]' | : NAME funcargs | funcargs }



exprstat -> primaryexp
primaryexp -> functioncall | assignstat
functioncall -> prefixexp {: NAME funcargs | funcargs }
assignstat -> prefixexp {`.' NAME | `[' expr `]'} assignment


prefixexp -> NAME | `(' expr `)'

assignment -> `,' primaryexp assignment | `=' explist1


explist1 -> expr {`,' expr}
expr -> subexpr
subexpr -> (simpleexp | unop subexpr) {binop subexpr}
simpleexp -> NUMBER | STRING | NIL | true | false | ... | constructor | FUNCTION body | primaryexp



```




## opcode

### move

move code 发生在 assignment 环节

在这里要进行值的迁移


luaK_storevar 生成了 move 指令

exp2reg?

对于赋值，= 后是 exp，前是存储空间

后面的 exp 要经过解析，才能向前赋值


### loadnil

luaK_nil


### loadk



### loadbool




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

将 10 存入 k 表，将 a 存入 locvars 表中（其中存储了名字 "a"）。
使用 loadk 指令，将 k 中的 10 加载入 reg 中。



如果是

```lua
a = 1
```

则直接将名字 "a" 和 1 都保存在 k 表。

需要通过 "a" 来索引全局变量。这一点和 local var 完全不同。




通过 numberK 和 stringK 方法

每个 function 都有一个 k 表，而且可以去重存储。



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








lua 在进行解析时，没有进行关系运算的实时解析，但是对 constant 算法运算有编译时执行

如 `local a = 5 > 2` 和 `local a = 1 + 2` 的区别

前者需要生成 jmp 指令，但是后者，直接是 loadk 0 0 ; 3







upval

在 pascal 中，在 outer scope 的变量，可以通过 frame stack 去查找

但是在 lua 中，函数也是一种值，可以四处流转，说不定在什么地方调用
所以其 upvalue 不一定出现在 stack frame 上





gettable 中，之所以使用 RK(C) 这种方法，是因为索引值未必是 constant，也可能是
一个表，一个函数，等其它值，这种值只能由 寄存器 存储

同时，加上了 k，也可以节省临时寄存器的使用

如果超出了 k 表的范围，大于 256，需要临时先加载入 寄存器







如何调度寄存器？






for loop 特别开发了底层指令来处理，而 repeat 和 while 则没有相应的指令。
依然是通过 jmp 来实现的。

