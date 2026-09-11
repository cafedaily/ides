PY ?= python3
DB ?= yang.db

.PHONY: help test web demo serve graph bridges clean

help:
	@echo "make test     跑测试（零依赖；跨语言对照要 node，没有就报跳过）"
	@echo "make web      把 web/src 拼成 web/index.html"
	@echo "make demo     建库 + 灌演示语料 + 建图"
	@echo "make serve    起服务 http://localhost:8730"
	@echo "make graph    打印图谱概况"
	@echo "make bridges  列出跨维度的桥"

test:
	$(PY) tests/run.py

web:
	$(PY) web/build.py

demo: web
	$(PY) -c "from yang import db,store,demo; c=db.connect('$(DB)'); \
	store.load_state(c, demo.state(), 'replace'); g=store.rebuild(c); \
	print('灌好了：%d 篇，%d 条桥' % (len(g['terms']), len(g['bridges'])))"

serve: web
	$(PY) -m yang --db $(DB) serve

graph:
	$(PY) -m yang --db $(DB) graph

bridges:
	$(PY) -m yang --db $(DB) bridges -n 8

clean:
	rm -f $(DB) $(DB)-wal $(DB)-shm
	rm -rf .pytest_cache **/__pycache__
