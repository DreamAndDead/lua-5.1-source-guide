example:
	gcc -m32 -g -I$(CURDIR)/install/include -I$(CURDIR)/install/lib -ldl -lm -o example/cclosure.out example/cclosure.c $(CURDIR)/install/lib/liblua.a
	(cd example;./cclosure.out cclosure.lua;cd ..)

	gcc -m32 -g -I$(CURDIR)/install/include -I$(CURDIR)/install/lib -ldl -lm -o example/lclosure.out example/lclosure.c $(CURDIR)/install/lib/liblua.a
	(cd example;./lclosure.out lclosure.lua;cd ..)

registry:
	(cd ./example; ../install/bin/lua ./registry.lua; cd ..)

spy:
	$(CURDIR)/install/bin/lua $(CURDIR)/tool/ChunkSpy-0.9.8/5.1/ChunkSpy.lua --interact

inspect:
	cat -n $(source)
	$(CURDIR)/install/bin/lua $(CURDIR)/tool/ChunkSpy-0.9.8/5.1/ChunkSpy.lua --brief --source $(source)

compile:
	(cd lua-5.1.5; make linux clean; make linux; make install; cd ..)

clean:
	(cd lua-5.1.5; make linux clean; cd ..)

lua:
	./lua-5.1.5/src/lua

run:
	cat -n $(source)
	./lua-5.1.5/src/lua $(source)

debug:
	gdb -x init.gdb --args ./lua-5.1.5/src/lua $(source)

lex:
	gdb -batch -x lex.gdb --args ./lua-5.1.5/src/luac $(source)
	rm luac.out

serve:
	xdg-open http://localhost:1313/lua-5.1-source-guide/
	(cd site; hugo server -D; cd ..)

draw:
	asy -f pdf -pdfviewer="okular" -batchView -tex xelatex

.PHONY:	clean test publish example
