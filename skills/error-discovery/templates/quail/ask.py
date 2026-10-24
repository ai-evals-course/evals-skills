"""Run SQL for an Ask-tab question on the warm Quail app and post the rows to the review UI.

uv run --with modal python ask.py --deploy        # deploy ask_app.py with tables.json
uv run --with modal python ask.py --warm          # start the container, load the model
uv run --with modal python ask.py q3 q3.sql       # run q3.sql for question q3
uv run --with modal python ask.py --probe x.sql   # run SQL and print rows, without posting
"""
import json, os, subprocess, sys, time, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
UI = os.environ.get("REVIEW_UI", "http://localhost:8000")
APP = os.environ.get("QUAIL_APP", "error-discovery-quail")


def post(path, body):
    req = urllib.request.Request(UI + path, json.dumps(body).encode(), {"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req))


def engine():
    import modal
    return modal.Cls.from_name(APP, "Ask")()


def enrich(rows):
    """Drop table prefixes ("u.text" -> "text") and copy record_id, turn, and text from the
    row's source table so the UI can link each row to its record."""
    tables = json.load(open(os.path.join(HERE, "tables.json")))
    by_id = {t["id_col"]: {r[t["id_col"]]: r for r in t["rows"]} for t in tables.values()}
    out = []
    for r in rows:
        r = {k.split(".", 1)[-1]: v for k, v in r.items()}
        for col, index in by_id.items():
            src = index.get(r.get(col))
            if src:
                for k in ("record_id", "turn", "text"):
                    if k in src:
                        r.setdefault(k, src[k])
        out.append(r)
    return out


def main():
    cmd = sys.argv[1]
    if cmd == "--deploy":
        subprocess.run(["modal", "deploy", "ask_app.py"], cwd=HERE, check=True)
        return
    if cmd == "--warm":
        t = time.time()
        print(engine().ping.remote(), "wall", round(time.time() - t), "s")
        return
    if cmd == "--probe":
        res = engine().run.remote(open(sys.argv[2]).read())
        if "error" in res:
            sys.exit(res["error"])
        rows = enrich(res["rows"])
        print(len(rows), "rows | query", round(res["query_s"], 1), "s")
        for r in rows[:50]:
            print(json.dumps(r, default=str)[:300])
        return
    qid, sql = cmd, open(sys.argv[2]).read()
    post("/api/answer", {"id": qid, "status": "running", "sql": sql})
    t = time.time()
    res = engine().run.remote(sql)
    if "error" in res:
        post("/api/answer", {"id": qid, "status": "error", "error": res["error"][:2000]})
        sys.exit(res["error"])
    rows = enrich(res["rows"])
    post("/api/answer", {"id": qid, "status": "done", "rows": rows, "model": res["model"],
                         "query_s": round(res["query_s"], 1), "wall_s": round(time.time() - t, 1)})
    print(f"{qid}: {len(rows)} rows | query {res['query_s']:.0f} s | wall {time.time() - t:.0f} s")


if __name__ == "__main__":
    main()
