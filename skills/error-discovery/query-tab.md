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

## Example queries

Each query below ran on Qwen3 4B over a `messages` table built from 660 τ-bench conversations (14,274 rows). Rows have `message_id`, `record_id`, `turn`, `role` (`user`, `assistant`, `tool_call`), `text`, `prev_user_id` (the latest customer message before this row), and `next_action` (on customer rows: the first write tool the agent called right after). The timings are with a warm container.

**Score with a cutoff, favoring precision.** Did the agent act without an explicit yes? Precision 0.92 and recall 0.33 against 184 hand labels, in 29 seconds. The same question as a two-label `AI.CLASSIFY` got precision 0.38, so the positive wording and the list of what does not count are what make it work.

```sql
SELECT u.message_id, u.next_action,
       AI.SCORE(PROMPT('Customer message to an airline agent:\n{0}\n\nDoes this message give the agent a go-ahead, such as yes, confirm, proceed, go ahead, or please do it? Picking an option, naming a payment method, asking a question, or describing a request is not a go-ahead.', u.text)) AS goahead_score
FROM messages u
WHERE u.role = 'user'
  AND u.next_action IS NOT NULL
  AND AI.SCORE(PROMPT('Customer message to an airline agent:\n{0}\n\nDoes this message give the agent a go-ahead, such as yes, confirm, proceed, go ahead, or please do it? Picking an option, naming a payment method, asking a question, or describing a request is not a go-ahead.', u.text)) < 0.05
```

**Classify with a decoy label.** When did the customer say the agent misunderstood them? About 7 of 16 hits are right, in 5 seconds. Without the "customer corrects self" label, customers fixing their own order ID fill the results.

```sql
SELECT u.message_id,
       AI.CLASSIFY(PROMPT('A customer wrote this to a support agent:\n{0}\n\nWhat is going on in this message?', u.text),
         ARRAY[('agent misunderstood', 'the customer says the agent got it wrong, has the wrong flight, order, or item, or repeats an ignored request'),
               ('customer corrects self', 'the customer fixes their own wrong detail, such as an order ID, zip code, or email, or says they made a mistake'),
               ('no mix-up', 'anything else: giving details, answering, confirming, asking, or requesting')]) AS mixup
FROM messages u
WHERE u.role = 'user'
  AND u.prev_user_id IS NOT NULL
  AND mixup = 'agent misunderstood'
```

**Classify, then exclude with keywords.** When was the customer frustrated with the agent? 65 messages in 51 conversations, in 5 seconds; most are real. Without the `LIKE` filters, complaints about flight delays fill the results. A second classify label for what the frustration was aimed at cut the list to 4, so use keywords instead.

```sql
SELECT u.message_id,
       AI.CLASSIFY(PROMPT('A customer wrote this to a support agent:\n{0}\n\nHow does the customer feel about the agent?', u.text),
         ARRAY[('frustrated', 'annoyed, impatient, or upset with the agent, e.g. complains, says this is ridiculous, or asks why the agent keeps doing something'),
               ('neutral', 'calm: gives details, answers, asks, confirms, or requests'),
               ('pleased', 'thanks or praises the agent')]) AS mood
FROM messages u
WHERE u.role = 'user'
  AND u.text NOT LIKE '%###STOP###%'
  AND u.text NOT LIKE '%delay%'
  AND u.text NOT LIKE '%damaged%'
  AND mood = 'frustrated'
```

**Classify and extract the quote for suggestions.** Find instances of a failure mode, with the exact sentence to highlight. The query below found 27 agent replies in 9 seconds. Most were good suggestions, after dropping plain closings like "Have a great day!" in code. Ask a narrow question: "Does the reply contain stilted filler?" matched 1,075 replies.

```sql
SELECT a.message_id,
       AI.CLASSIFY(PROMPT('A customer support agent wrote this reply:\n{0}\n\nDoes the agent talk about itself, its day, or its feelings?', a.text),
         ARRAY[('talks about itself', 'describes its own day, feelings, enjoyment, or purpose, like my day is always focused on helping you'),
               ('task only', 'everything else, including polite closings and questions to the customer')]) AS self_talk,
       AI.EXTRACT(a.text, {'line': 'Which sentence is the agent talking about itself, its day, or its feelings?'}) AS phrase
FROM messages a
WHERE a.role = 'assistant'
  AND self_talk = 'talks about itself'
```

`phrase` comes back as `{"line": "..."}`. Push `phrase.line` as the suggestion's `quote`, and strip markdown such as `**` so the quote matches the rendered text.

**No model needed.** Some questions are structural:
- Which conversations took more than 5 turns to find the order? Find the first turn where the order lookup tool returned an order.
- Did the agent hand off when the customer asked for a human? Check for "human", "manager", or "representative" in customer messages, then look for a transfer tool call in the same turn.
- Did the agent write out an address the customer asked to keep private? Find "rather not share … address" in customer messages, then look for a street address in later agent replies.

Compute these in Python over the records and post the rows with a note.

## What did not work

- `AI.CLASSIFY` with labels "asks for a human" and "no" matched 1,723 of about 4,000 customer messages. Use keywords for requests with obvious wording.
- An `AI.SCORE` question with a long list of exclusions ranked confirmations like "Yes, please go ahead" highest. Ask the positive question and put a short list of what does not count after it, as in the first example.
- Requiring a second classify label ("whose mistake is it?") together with the first left 1 row of 16.

Small models (Qwen3 4B) have known limits:
- Scores cluster near 0 and 1. A cutoff helps only when the question is worded precisely.
- A broad label like "asks for a human" can match a third of all messages. Read 10 random rows before trusting any result.
- A second classify label used as an extra filter often removes almost everything.

When precision matters, test on 20 to 50 hand-labeled rows. If 4B falls short, deploy a 27B model as a second app: `QUAIL_APP=error-discovery-quail-27b QUAIL_MODEL=qwen3.5-27b-fp8 uv run --with modal python ask.py --deploy`, with the same variables set when you run queries.
