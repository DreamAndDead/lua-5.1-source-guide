all:
	flex lex.l
	gcc -DYYMAIN lex.yy.c

clean:
	rm -rf a.out lex.yy.c

.PHONY: clean
