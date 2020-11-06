from gdb.printing import PrettyPrinter
from gdb.printing import register_pretty_printer

import gdb
from tabulate import tabulate


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

        return res
        

    def to_string(self):
        table = [
            ['key', 'val', 'desc'],
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
            ['actvar', self.get_actvar(), 'active local vars array, save index to fs->f->locvars'],
            # ['upvalues', str(self.fs['upvalues']), 'upvalues? empty for now'],
            ['upvalues', '', 'upvalues? empty for now'],
        ]

        return f"FuncState {self.fs_ref} \n" + tabulate(table, headers='firstrow', tablefmt='fancy_grid')


class LexStatePrinter:
    def __init__(self, val):
        self.ls = val
        self.ls_ref = val.address

    def get_current(self, cur):
        if cur == -1:
            return 'EOF'
        else:
            return f"'{chr(cur)}'"

    def get_tstring(self, ts):
        const_char_ptr = gdb.lookup_type("char").const().pointer()
        return (ts + 1).cast(const_char_ptr).string()

    def get_token(self, token):
        token2str = gdb.parse_and_eval('luaX_token2str')
        indicator = token2str(self.ls_ref, token['token']).string()

        TK_NAME = gdb.parse_and_eval('TK_NAME')
        TK_STRING = gdb.parse_and_eval('TK_STRING')
        TK_NUMBER = gdb.parse_and_eval('TK_NUMBER')

        content = ''
        if token['token'] == TK_NAME or token['token'] == TK_STRING:
            content = self.get_tstring(token['seminfo']['ts'])
        elif token['token'] == TK_NUMBER:
            content = str(token['seminfo']['r'])
        
        return indicator + ' ' + content

    def to_string(self):
        table = []
        table.append(['key', 'val', 'desc'])

        table.append(['current',
                      self.get_current(self.ls['current']),
                      'next char after current token'])
        
        table.append(['linenumber',
                      self.ls['linenumber'],
                      'line number where current token lives'])

        table.append(['lastline',
                      self.ls['lastline'],
                      'line number where last token lives'])

        table.append(['t',
                      self.get_token(self.ls['t']),
                      'current token'])
        
        table.append(['lookahead',
                      self.get_token(self.ls['lookahead']),
                      'next token'])

        table.append(['fs',
                      str(self.ls['fs']),
                      'pointer to current FuncState'])

        table.append(['L',
                      str(self.ls['L']),
                      'pointer to lua_State'])

        table.append(['z',
                      str(self.ls['z']),
                      'pointer to ZIO input stream'])

        table.append(['buff',
                      str(self.ls['buff']),
                      'buffer for token'])

        table.append(['source',
                      self.get_tstring(self.ls['source']),
                      'current source name'])

        table.append(['decpoint',
                      f"\'{chr(self.ls['decpoint'])}\'",
                      'locale decimal point'])

        return f"LexState {self.ls.address}\n" + tabulate(table, headers='firstrow', tablefmt='fancy_grid')




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


register_pretty_printer(None, CustomPrettyPrinterLocator(), replace=True)
