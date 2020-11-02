# run






数据结构
- 将 Proto 封装为 Closure，记录运行时的信息









```c
struct lua_State {
  CommonHeader;
  lu_byte status;             // 状态？可能用于协程中
  StkId top;                  // 栈顶指针，（第一个空的位置）
  StkId base;                 // 栈基指针
  global_State *l_G;          // 指向 global state
  CallInfo *ci;               // 当前函数的 callinfo
  const Instruction *savedpc; // savedpc？
  StkId stack_last;           // 栈的最后？
  StkId stack;                // 栈基？
  CallInfo *end_ci;           // 指向 callinfo 数组的最后
  CallInfo *base_ci;          // callinfo 数组的开始
  int stacksize;              // 栈大小
  int size_ci;                // callinfo 数组大小
  unsigned short nCcalls;     // 嵌套函数调用的个数？（控制 LL 1 过程中递归层数，enterlevel, leavelevel）
  unsigned short baseCcalls;  // 协程 resume 时？
  lu_byte hookmask;           // ？
  lu_byte allowhook;          // ？
  int basehookcount;          // ？
  int hookcount;              // ？
  lua_Hook hook;              // ？
  TValue l_gt;                // 全局表？
  TValue env;                 // 临时存储环境？
  GCObject *openupval;        // upvalue 的链表？
  GCObject *gclist;           // ？
  struct lua_longjmp *errorJmp; // 错误回调？
  ptrdiff_t errfunc;            // 用栈索引表示的 error handling 函数？
};
```








## c api


c api 和 vm 是一样的

都是在操作 lua_State


这样就保证了和谐的与 c 语言集成的状态。

夸张的说，lua 代码不过是 c api 的一种符号表示
