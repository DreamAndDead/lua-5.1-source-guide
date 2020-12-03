test:
	gcc -m32 -g -I$(CURDIR)/install/include -I$(CURDIR)/install/lib -ldl -lm -o test/test.out test/test.c $(CURDIR)/install/lib/liblua.a
	(cd test;./test.out test.lua;cd ..)

spy:
	$(CURDIR)/install/bin/lua $(CURDIR)/ChunkSpy-0.9.8/5.1/ChunkSpy.lua --interact

inspect:
	cat -n $(source)
	$(CURDIR)/install/bin/lua $(CURDIR)/ChunkSpy-0.9.8/5.1/ChunkSpy.lua --brief --source $(source)

lua:
	(cd lua-5.1.5; make linux clean; make linux; make install; cd ..)

compile:
	$(CURDIR)/install/bin/luac $(source)

hex:
	xxd luac.out

debug:
	gdb -x init.gdb ./lua-5.1.5/src/lua

.PHONY:	test
