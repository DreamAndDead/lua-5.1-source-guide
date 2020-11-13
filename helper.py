from gdb.printing import PrettyPrinter
from gdb.printing import register_pretty_printer
import gdb
from tabulate import tabulate


TABLE_STYLE = 'simple'


class TValuePrinter:
    def __init__(self, val):
        self.val = val
        self.val_ref = val.address

    def to_string(self):
        t = self.val['tt']
        v = self.val['value']

        if t == gdb.parse_and_eval("LUA_TNIL"):
            return "nil"
        elif t == gdb.parse_and_eval("LUA_TNUMBER"):
            return f"{v['n']}"
        elif t == gdb.parse_and_eval("LUA_TSTRING"):
            return TStringPrinter(v['gc']['ts'].address).to_string()
        elif t == gdb.parse_and_eval("LUA_TBOOLEAN"):
            return "true" if v['b'] > 0 else "false"

        # todo: the rest type
        return "*"


class TStringPrinter:
    def __init__(self, val_ref):
        self.ts_ref = val_ref

    def to_string(self):
        const_char_ptr = gdb.lookup_type("char").const().pointer()
        return (self.ts_ref + 1).cast(const_char_ptr).string()


class ProtoPrinter:
    def __init__(self, val):
        self.f = val
        self.f_ref = val.address
        self.fs = None
        self.fs_ref = None

    def set_fs(self, fs):
        self.fs = fs
        self.fs_ref = fs.address
        return self

    def get_k(self):
        k = self.f['k']
        nk = self.fs['nk'] if self.fs else self.f['sizek']

        res = ""
        for i in range(nk):
            res += TValuePrinter(k[i]).to_string() + ', '

        return f"[{res}]"

    def get_locvars(self):
        locvars = self.f['locvars']
        n = self.fs['nlocvars'] if self.fs else self.f['sizelocvars']

        res = ""
        for i in range(n):
            res += TStringPrinter(locvars[i]['varname']).to_string() + ', '

        return f"[{res}]"

    def get_upval(self):
        arr = self.f['upvalues']
        n = self.f['nups']

        res = ""
        for i in range(n):
            e = arr[i]
            res += TStringPrinter(e).to_string() + ', '

        return f"[{res}]"

    def get_p(self):
        n = self.fs['np'] if self.fs else self.f['sizep']
        arr = self.f['p']

        res = ""
        for i in range(n):
            e = arr[i]
            res += ProtoPrinter(e).to_string() + '\n\n'

        return res

    def to_string(self):
        table = [
            # ['sizek', self.f['sizek'], 'size k'],
            ['k', self.get_k(), 'k table'],
            # ['sizecode', self.f['sizecode'], 'size code'],
            # ['code', str(self.f['code']), 'code'],
            # ['sizep', self.f['sizep'], 'size p'],
            # ['p', str(self.f['p']), 'proto of closure functions'],
            # ['sizelineinfo', self.f['sizelineinfo'], 'size lineinfo'],
            # ['lineinfo', str(self.f['lineinfo']), 'opcode -> lineno map'],
            # ['sizelocvars', self.f['sizelocvars'], 'size locvars'],
            ['locvars', self.get_locvars(), 'local vars'],
            # ['sizeupvalues', self.f['sizeupvalues'], 'size upvalues'],
            ['upvalues', self.get_upval(), 'upvalue names'],
            ['nups', int(self.f['nups']), 'upvalue number'],
            # ['source', TStringPrinter(self.f['source']).to_string(), 'source name'],
            # ['gclist', str(self.f['gclist']), 'gc list start'],
            ['numparams', int(self.f['numparams']), 'param number'],
            ['is_vararg', int(self.f['is_vararg']), 'is vararg?'],
            # ['maxstacksize', self.f['maxstacksize'], 'max stack size'],
            # ['linedefined', self.f['linedefined'], 'line start'],
            # ['lastlinedefined', self.f['lastlinedefined'], 'line end'],
        ]
        return f"Proto {self.f_ref} \n" + \
            tabulate(table, tablefmt=TABLE_STYLE) + "\n" + \
            "Proto->p \n" + self.get_p()


class FuncStatePrinter:
    def __init__(self, val):
        self.fs = val
        self.fs_ref = val.address

    def get_actvar(self):
        n = self.fs['nactvar']
        arr = self.fs['actvar']

        res = ""
        for i in range(n):
            res += str(arr[i]) + ', '

        return f"[{res}]"

    def get_upval(self):
        n = self.fs['f'].dereference()['nups']
        arr = self.fs['upvalues']

        res = ""
        for i in range(n):
            e = arr[i]
            k = e['k']

            kind = 'unknown'
            if k == gdb.parse_and_eval('VUPVAL'):
                kind = 'upval'
            elif k == gdb.parse_and_eval('VLOCAL'):
                kind = 'local'

            res += f"{kind} {int(e['info'])}" + ', '

        return f"[{res}]"

    def to_string(self):
        table = [
            # ['f', str(self.fs['f']), 'proto pointer'],
            # ['h', str(self.fs['h']), 'global table?'],
            ['prev', str(self.fs['prev']), 'enclosing FuncState *'],
            # ['ls', str(self.fs['ls']), 'LexState *'],
            # ['L', str(self.fs['L']), 'lua_State *'],
            ['BlockCnt', str(self.fs['bl']), 'chain of blocks?'],
            ['pc', self.fs['pc'], 'next pos to save code (= ncode)'],
            ['lasttarget', self.fs['lasttarget'], 'pc of last jump target?'],
            ['jpc', self.fs['jpc'], 'list of pendding jumps'],
            ['freereg', self.fs['freereg'], 'first free register'],
            ['nk', self.fs['nk'], 'len fs->f->k'],
            ['np', self.fs['np'], 'len fs->f->p'],
            ['nlocvars', self.fs['nlocvars'], 'len fs->f->locvars'],
            ['nactvar', int(self.fs['nactvar']), 'len fs->actvar'],
            ['actvar', self.get_actvar(), 'active local vars, save index to fs->f->locvars'],
            ['upvalues', self.get_upval(), 'upvalue desc'],
        ]

        f = ProtoPrinter(self.fs['f'].dereference()).set_fs(self.fs).to_string()

        return f"FuncState {self.fs_ref} \n" +\
            tabulate(table, tablefmt=TABLE_STYLE) + "\n" + f


class LexStatePrinter:
    def __init__(self, val):
        self.ls = val
        self.ls_ref = val.address

    def get_current(self, cur):
        if cur == -1:
            return 'EOF'
        else:
            return f"'{chr(cur)}'"

    def get_token(self, token):
        token2str = gdb.parse_and_eval('luaX_token2str')
        indicator = token2str(self.ls_ref, token['token']).string()

        TK_NAME = gdb.parse_and_eval('TK_NAME')
        TK_STRING = gdb.parse_and_eval('TK_STRING')
        TK_NUMBER = gdb.parse_and_eval('TK_NUMBER')

        content = ''
        if token['token'] == TK_NAME or token['token'] == TK_STRING:
            content = TStringPrinter(token['seminfo']['ts']).to_string()
        elif token['token'] == TK_NUMBER:
            content = str(token['seminfo']['r'])

        return indicator + ' ' + content

    def to_string(self):
        table = [
            ['current',
             self.get_current(self.ls['current']),
             'next char after current token'],
            ['linenumber',
             self.ls['linenumber'],
             'line number where current token lives'],
            ['lastline',
             self.ls['lastline'],
             'line number where last token lives'],
            ['t', self.get_token(self.ls['t']), 'current token'],
            ['lookahead',
             self.get_token(self.ls['lookahead']),
             'next token'],
            # ['fs', str(self.ls['fs']), 'pointer to current FuncState'],
            ['L', str(self.ls['L']), 'pointer to lua_State'],
            # ['z', str(self.ls['z']), 'pointer to ZIO input stream'],
            # ['buff', str(self.ls['buff']), 'buffer for token'],
            # ['source',
            #  TStringPrinter(self.ls['source']).to_string(),
            #  'current source name'],
            # ['decpoint',
            #  f"\'{chr(self.ls['decpoint'])}\'",
            #  'locale decimal point'],
        ]

        return f"LexState {self.ls.address}\n" +\
            tabulate(table, tablefmt=TABLE_STYLE) + "\n" +\
            FuncStatePrinter(self.ls['fs'].dereference()).to_string()


class CustomPrettyPrinterLocator(PrettyPrinter):
    def __init__(self):
        super(CustomPrettyPrinterLocator, self).__init__(
            "lua_printers", []
        )

    def __call__(self, val):
        typename = val.type.tag

        if typename is None:
            typename = val.type.name

        if typename is None:
            typename = str(val.type)

        if typename == "LexState":
            return LexStatePrinter(val)
        elif typename == "FuncState":
            return FuncStatePrinter(val)
        elif typename == "Proto":
            return ProtoPrinter(val)
        elif typename == "TString *":
            return TStringPrinter(val)


register_pretty_printer(None, CustomPrettyPrinterLocator(), replace=True)


class LexStateCmd(gdb.Command):
    def __init__(self):
        super(LexStateCmd, self).__init__("llex", gdb.COMMAND_USER)

    def complete(self, text, word):
        return gdb.COMPLETE_SYMBOL

    def invoke(self, args, from_tty):
        print(gdb.execute("print *ls", from_tty, True))
        print("Proto->code")
        print(gdb.execute("call PrintCode(ls->fs->f)", from_tty, True))


LexStateCmd()


class FuncStateCmd(gdb.Command):
    def __init__(self):
        super(FuncStateCmd, self).__init__("lfunc", gdb.COMMAND_USER)

    def complete(self, text, word):
        return gdb.COMPLETE_SYMBOL

    def invoke(self, args, from_tty):
        fs = args if args else 'fs'
        print(gdb.execute(f"print *({fs})", from_tty, True))
        print("Proto->code")
        print(gdb.execute(f"call PrintCode(({fs})->f)", from_tty, True))


FuncStateCmd()
