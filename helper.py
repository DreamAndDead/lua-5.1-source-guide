from gdb.printing import PrettyPrinter
from gdb.printing import register_pretty_printer

import gdb
from tabulate import tabulate

TABLE_STYLE = 'rst'


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

    def to_string(self):
        table = [
            ['sizek', self.f['sizek'], 'size k'],
            ['k', str(self.f['k']), 'k table'],
            ['sizecode', self.f['sizecode'], 'size code'],
            ['code', str(self.f['code']), 'code'],
            ['sizep', self.f['sizep'], 'size p'],
            ['p', str(self.f['p']), 'proto of closure functions'],
            ['sizelineinfo', self.f['sizelineinfo'], 'size lineinfo'],
            ['lineinfo', str(self.f['lineinfo']), 'opcode -> lineno map'],
            ['sizelocvars', self.f['sizelocvars'], 'size locvars'],
            ['locvars', str(self.f['locvars']), 'local vars'],
            ['sizeupvalues', self.f['sizeupvalues'], 'size upvalues? vs nups?'],
            ['upvalues', str(self.f['upvalues']), 'upvalue names?'],
            # ['source', TStringPrinter(self.f['source']).to_string(), 'source name'],
            # ['gclist', str(self.f['gclist']), 'gc list start'],
            ['nups', self.f['nups'], 'upvalues number'],
            ['numparams', self.f['numparams'], 'param number'],
            ['is_vararg', self.f['is_vararg'], 'is vararg?'],
            ['maxstacksize', self.f['maxstacksize'], 'max stack size'],
            ['linedefined', self.f['linedefined'], 'line start'],
            ['lastlinedefined', self.f['lastlinedefined'], 'line end'],
        ]
        return f"Proto {self.f_ref} \n" + \
            tabulate(table, tablefmt=TABLE_STYLE)


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

    def to_string(self):
        table = [
            ['f', str(self.fs['f']), 'proto pointer'],
            ['h', str(self.fs['h']), 'global table?'],
            ['prev', str(self.fs['prev']), 'enclosing FuncState *'],
            ['ls', str(self.fs['ls']), 'LexState *'],
            ['L', str(self.fs['L']), 'lua_State *'],
            ['BlockCnt', str(self.fs['bl']), 'chain of blocks?'],
            ['pc', self.fs['pc'], 'next pos to save code (= ncode)'],
            ['lasttarget', self.fs['lasttarget'], 'pc of last jump target'],
            ['jpc', self.fs['jpc'], 'list of pendding jumps?'],
            ['freereg', self.fs['freereg'], 'first free register'],
            ['nk', self.fs['nk'], 'len fs->f->k'],
            ['np', self.fs['np'], 'len fs->f->p'],
            ['nlocvars', self.fs['nlocvars'], 'len fs->f->locvars'],
            ['nactvar', self.fs['nactvar'], 'len fs->actvar'],
            ['actvar', self.get_actvar(), 'active local vars, save index to fs->f->locvars'],
            # ['upvalues', str(self.fs['upvalues']), 'upvalues? empty for now'],
            ['upvalues', '[]', 'upvalues? empty for now'],
        ]

        return f"FuncState {self.fs_ref} \n" + tabulate(table, tablefmt=TABLE_STYLE)


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
            ['t',
             self.get_token(self.ls['t']),
             'current token'],
            ['lookahead',
             self.get_token(self.ls['lookahead']),
             'next token'],
            ['fs',
             str(self.ls['fs']),
             'pointer to current FuncState'],
            ['L',
             str(self.ls['L']),
             'pointer to lua_State'],
            # ['z', str(self.ls['z']), 'pointer to ZIO input stream'],
            # ['buff', str(self.ls['buff']), 'buffer for token'],
            # ['source',
            #  TStringPrinter(self.ls['source']).to_string(),
            #  'current source name'],
            # ['decpoint',
            #  f"\'{chr(self.ls['decpoint'])}\'",
            #  'locale decimal point'],
        ]

        return f"LexState {self.ls.address}\n" + tabulate(table, tablefmt=TABLE_STYLE)


class CustomPrettyPrinterLocator(PrettyPrinter):
    def __init__(self):
        super(CustomPrettyPrinterLocator, self).__init__(
            "lua_printers", []
        )

    def __call__(self, val):
        typename = gdb.types.get_basic_type(val.type).tag

        if typename is None:
            typename = val.type.name

        if typename == "LexState":
            return LexStatePrinter(val)
        elif typename == "FuncState":
            return FuncStatePrinter(val)
        elif typename == "Proto":
            return ProtoPrinter(val)


register_pretty_printer(None, CustomPrettyPrinterLocator(), replace=True)
