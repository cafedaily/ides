"""Store/API acceptance benchmark with exact full/incremental comparison."""
import copy
import json
from pathlib import Path
import statistics
import sys
import tempfile
import time
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from yang import api, db, demo, store


def corpus(size):
    seeds=demo.state()['ideas'];rows=[]
    for index in range(size):
        row=copy.deepcopy(seeds[index%len(seeds)])
        row['id']=f'bench-{index:04d}'
        row['grew'].append({'kind':'note','q':'实验标记','a':f'experiment{index}','at':int(time.time()*1000)})
        rows.append(row)
    return rows


def main():
    results=[]
    with tempfile.TemporaryDirectory() as folder:
        for size in (300,500):
            full_times=[];inc_times=[]
            for repeat in range(3):
                c=db.connect(Path(folder)/f'{size}-{repeat}.db')
                rows=corpus(size);store.load_state(c,{'ideas':rows},'replace')
                api.graph(c,{},None)
                new=copy.deepcopy(rows[repeat]);new['id']='new';new['now']+='新的观察记录'
                store.load_state(c,{'ideas':[new]})
                start=time.perf_counter();incremental=api.graph(c,{},None);inc_times.append(time.perf_counter()-start)
                real=store.graph
                with patch.object(store,'graph',side_effect=lambda conn:real(conn,force=True)):
                    start=time.perf_counter();reference=api.graph(c,{},None);full_times.append(time.perf_counter()-start)
                assert incremental==reference
                c.close()
            full=statistics.median(full_times);inc=statistics.median(inc_times)
            results.append({'documents':size,'trials':3,'full_seconds':full,'incremental_seconds':inc,
                            'ratio':inc/full,'exact_match':True,'layer':'SQLite store + API graph dispatch; excludes HTTP serialization'})
    print(json.dumps(results,indent=2))
    if len(sys.argv)>1: Path(sys.argv[1]).write_text(json.dumps(results,indent=2)+'\n',encoding='utf-8')
    return 0 if all(row['ratio']<0.3 for row in results) else 1

if __name__=='__main__': raise SystemExit(main())
