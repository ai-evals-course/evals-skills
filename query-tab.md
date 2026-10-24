# Ask tab: AI SQL queries with Quail on Modal

The Ask tab lets the reviewer ask a question about the whole dataset in plain English, e.g., "When did the agent change a reservation without an explicit yes from the customer?" You write SQL with AI functions, run it with [Quail](https://github.com/fsdatalab/quail) on a Modal GPU, and post the rows back to the tab. Each row links to its record.

Use the same engine for depth mode in the review loop. When a failure mode needs a model to recognize it, search all records with one Quail query instead of a subagent that reads every record.

## Setup

Use Quail on Modal. Do not run the model locally, and do not clone the Quail repo.

- Install Quail with uv, from GitHub main: `uv pip install "quail-engine @ git+https://github.com/fsdatalab/quail.git@main"`. PyPI 0.1.0 is older and rejects plain `WHERE` predicates. The Modal image in `templates/quail/quail_env.py` already does this.
- Run Modal through uv: `uv run --with modal python ask.py ...`. Nothing needs to be installed locally.
- Read the AI function reference before writing SQL: `docs/content/docs/user-guide/sql/ai-functions.mdx` in the Quail repo. Fetch it with `gh api` or a raw GitHub URL.

Copy `templates/quail/` next to the server, then:

1. Write `tables.json`. Use one row per message (or per segment), not one row per record. Shape: `{"messages": {"id_col": "message_id", "rows": [...]}}`. Give each row `record_id`, `turn`, `role`, and `text`, plus context columns that later queries need, e.g., `prev_user_id` or the next tool call. Quail joins need an AI predicate, so store context as columns instead of joining.
2. `uv run --with modal python ask.py --deploy`
3. `uv run --with modal python ask.py --warm`. The model loads on the first query, then queries take about 5 to 15 seconds. The container shuts down after 30 idle minutes and costs GPU time while warm.

## Server and app

Add to the server:
- `POST /api/ask {text}` appends `{id, text, status: "pending", asked_at}` to `questions.json` and prints `ASK <id>: <text>` to stdout.
- `POST /api/answer {id, ...}` merges fields into that question: `status` (`running`, `done`, `error`), `sql`, `rows`, `model`, `query_s`, `error`, `note`.
- `GET /api/questions`.

Guard both writes with a lock. The app and `ask.py` write to the same file.

Add an Ask view to the app:
- A text box and an Ask button (Cmd+Enter sends).
- One card per question, newest first: question, status badge ("waiting for Claude", "running on Quail", "done", "error"), collapsible SQL, an optional note, and a result table.
- Each result row shows the record, turn, and text, plus the query's own columns. Clicking a row opens the record and scrolls to that turn.
- Poll `/api/questions` every 2 seconds.

## Answer a question

1. Start the server with unbuffered output written to a log file. Watch it with the Monitor tool: `tail -F server.log | grep --line-buffered "^ASK "`.
2. When a question arrives, write the SQL to `asks/<id>.sql`. Run it with `--probe` first and read the rows.
3. If the rows look right, run `ask.py <id> asks/<id>.sql`. It posts `running`, then the rows.
4. If the result is only partly right, post a `note` through `/api/answer` that says what is wrong. Tell the user too.
5. If the question is a count or a structural check, e.g., "which conversations took more than 5 turns to find the order", compute it in Python and post the rows with a note. Do not use a model for it.

## Writing queries

- `AI.CLASSIFY(PROMPT(...), ARRAY[('label', 'description'), ...])` with two or three labels works better than `AI.IF` on small models. Each label gets a description of at most 25 words. Filter on the alias: `WHERE label_alias = 'x'`.
- `AI.SCORE` returns 0 to 1. To favor precision, ask a positive question ("does the message give a go-ahead?") and keep rows below a low cutoff, e.g., `< 0.05`. Pick the cutoff against a few hand labels.
- `AI.EXTRACT(text, {'field': 'question?'})` copies a span from the text. Use it to get the quote for a suggestion.
- Use plain `LIKE` and `=` predicates for exclusions that keywords can catch, e.g., `text NOT LIKE '%delay%'`.

Small models (Qwen3 4B) have known limits:
- Scores cluster near 0 and 1. A cutoff helps only when the question is worded precisely.
- A broad label like "asks for a human" can match a third of all messages. Read 10 random rows before trusting any result.
- A second classify label used as an extra filter often removes almost everything.

When precision matters, test on 20 to 50 hand-labeled rows. If 4B falls short, deploy a 27B model as a second app: `QUAIL_APP=error-discovery-quail-27b QUAIL_MODEL=qwen3.5-27b-fp8 uv run --with modal python ask.py --deploy`, with the same variables set when you run queries.
