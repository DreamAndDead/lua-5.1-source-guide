
from gdb.printing import PrettyPrinter
from gdb.printing import register_pretty_printer

import gdb
from tabulate import tabulate








class LexStatePrinter:
    def __init__(self, val):
        self.ls = val
        self.ls_ref = val.address.cast(val.type.pointer())

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
        getstr = gdb.parse_and_eval('getstr')

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
        
        return "LexState \n" + tabulate(table, headers='firstrow', tablefmt='fancy_grid')




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


register_pretty_printer(None, CustomPrettyPrinterLocator(), replace=True)
