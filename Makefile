test:
	gcc -m32 -g -I$(CURDIR)/install/include -I$(CURDIR)/install/lib -ldl -lm -o test/test.out test/test.c $(CURDIR)/install/lib/liblua.a
	(cd test;./test.out test.lua;cd ..)

spy:
	$(CURDIR)/install/bin/lua $(CURDIR)/ChunkSpy-0.9.8/5.1/ChunkSpy.lua --interact

lua:
	(cd lua-5.1.5; make linux clean; make linux; make install; cd ..)

tags:
	gtags -C lua-5.1.5/ .

hex:
	xxd luac.out

compile:
	$(CURDIR)/install/bin/luac test/compile.lua

inspect:
	$(CURDIR)/install/bin/lua $(CURDIR)/ChunkSpy-0.9.8/5.1/ChunkSpy.lua --source test/compile.lua

debug:
	cgdb -ex 'source luagdb.txt' --args ./install/bin/lua test/test.lua

.PHONY:	test
