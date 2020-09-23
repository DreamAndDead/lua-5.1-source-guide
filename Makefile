test:
	gcc -g -I$(CURDIR)/install/include -I$(CURDIR)/install/lib -ldl -lm -o test/test.out test/test.c $(CURDIR)/install/lib/liblua.a
	(cd test;./test.out test.lua;cd ..)


spy:
	$(CURDIR)/install/bin/lua $(CURDIR)/ChunkSpy-0.9.8/5.1/ChunkSpy.lua --interact


lua:
	(cd lua-5.1.5; make linux clean; make linux; make install; cd ..)

.PHONY:	test