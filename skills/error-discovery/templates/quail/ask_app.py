"""Warm Quail engine on Modal for the review UI's Ask tab.

Deploy:  uv run --with modal python ask.py --deploy
The container loads the model and the tables once, then answers SQL until it
sits idle for SCALEDOWN seconds. ask.py calls it.
"""
import json, os, time
import modal

from quail_env import quail_image

MODEL = os.environ.get("QUAIL_MODEL", "qwen3-4b-fp8")
APP = os.environ.get("QUAIL_APP", "error-discovery-quail")
SCALEDOWN = 1800
HERE = os.path.dirname(os.path.abspath(__file__))

# tables.json: {"messages": {"id_col": "message_id", "rows": [...]}, ...}, written by the agent
image = quail_image().add_local_file(os.path.join(HERE, "tables.json"), "/root/tables.json")
app = modal.App(APP)
VOLUMES = {"/root/.cache/huggingface": modal.Volume.from_name("quail-hf-cache", create_if_missing=True),
           "/root/.cache/kernels": modal.Volume.from_name("quail-kernel-cache", create_if_missing=True)}


@app.cls(image=image, gpu="H100!", secrets=[modal.Secret.from_dict({"QUAIL_MODEL": MODEL})],
         memory=32768, timeout=1800, scaledown_window=SCALEDOWN, volumes=VOLUMES)
class Ask:
    @modal.enter()
    def load(self):
        import pyarrow as pa
        import quail
        t0 = time.time()
        config = quail.EngineConfig(gpus=1, model=os.environ["QUAIL_MODEL"], backend="quail", device="h100-sxm")
        self.session = quail.Session(config).__enter__()
        for name, t in json.load(open("/root/tables.json")).items():
            self.session.register(name, quail.DocumentProvider.from_table(pa.Table.from_pylist(t["rows"]), id_col=t["id_col"]))
        self.load_s = time.time() - t0

    @modal.method()
    def run(self, sql):
        t0 = time.time()
        try:
            rows = self.session.sql(sql, dialect="bq").run().collect().to_pylist()
        except Exception as e:
            # return the message as text: the local side cannot unpickle quail's exception types
            return {"error": f"{type(e).__name__}: {e}"}
        return {"rows": rows, "query_s": time.time() - t0, "model": os.environ["QUAIL_MODEL"]}

    @modal.method()
    def ping(self):
        return {"load_s": self.load_s, "model": os.environ["QUAIL_MODEL"]}
