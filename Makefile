test:
	gcc -m32 -g -I$(CURDIR)/install/include -I$(CURDIR)/install/lib -ldl -lm -o test/test.out test/test.c $(CURDIR)/install/lib/liblua.a
	(cd test;./test.out test.lua;cd ..)

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

publish:
	emacs -u "$(id -un)" --batch --eval '(load user-init-file)' --load publish.el --funcall org-publish-all

server:
	python -m http.server -d docs 8000

.PHONY:	clean test publish
