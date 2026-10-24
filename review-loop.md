# Review Loop

This is the ongoing interactive phase. The app is running and the human is reviewing. You are an active participant.

## The two modes: breadth and depth

Error discovery alternates between two modes.

**Breadth**: cover as much of the dataset as possible. Pick diverse samples, fill cluster gaps, add random records. The goal is to find different failure modes.

**Depth**: once a mode is found, examine it thoroughly. Scan all records for instances, re-review earlier items, refine the definition. The goal is to understand one failure mode well.

Alternate between these. Review broadly until you find something, then examine that mode in depth, then go broad again.

## Progress updates

Tell the user what you are doing at each step during the review loop. When you categorize annotations, say what modes you found. When you spawn a subagent, say which failure mode it is scanning for. When you propose new samples, say why you chose them. Do not go silent while background work runs.

## Launch and monitor

1. Start the Python server in the background.
2. Open the app in the browser.
3. Tell the user the app is ready. Explain the interaction briefly.
4. **Monitor the annotations file** using the Monitor tool with `persistent: true`. Write a Python polling script that watches `error_discovery_data/annotations.json` for changes every 2 seconds, comparing content to detect new or deleted annotations. Each change emits a line to stdout with the total count, number of records, and the latest note text. The Monitor tool turns each stdout line into a notification, so you react in real time as annotations arrive. Do not use `inotifywait` or filesystem events — poll with a simple read-compare loop for cross-platform reliability.

## Process annotations as they arrive

When new annotations appear:
1. Read all annotations.
2. Categorize each into a failure mode. Match to an existing mode or create a new one.
3. Maintain a running taxonomy: `{mode_name: {description, count, example_ids, example_quotes[]}}`.
4. Push the updated taxonomy to `POST /api/patterns`.
5. Track which records have been reviewed and which clusters or dimensions are covered.

## Depth mode: scan for failure mode instances

When you discover a new failure mode (or an existing one becomes clearer), scan **all** records for instances. Include both reviewed and unreviewed records.

**Search with Quail first.** When a model can recognize the mode from one message or segment, write one Quail query over all records and use `AI.EXTRACT` for the quote. See [query-tab.md](query-tab.md). If a keyword or a structural check finds the mode, use code instead. Read 10 random hits before you push suggestions, and cap each mode at about 6 to 8 suggestions per batch.

**Otherwise, spawn one background subagent per failure mode.** Use a subagent when the mode needs context from the whole record. Give the subagent the mode name, description, and example quotes. It reads through all records and returns a list of suggested annotations: `{record_id, text, start, end}`. One mode = one subagent, not one per record. Multiple modes can run in parallel. This happens in the background while the human keeps reviewing.

When subagents return, merge their suggestions and push to `POST /api/suggestions`. The UI polls for new suggestions automatically and shows them in the Progress view queue and as purple highlights in the article view.

There are two kinds of suggestions:
1. **Already-reviewed records**: the reviewer may have missed an instance because the mode was not yet in their head when they read the record (criteria drift).
2. **Unreviewed records**: new coverage. Add these records to the sample if they are not already in it.

Agent suggestions are not ground truth. The human accepts or dismisses each one. Favor recall over precision. Dismissing a false positive is quick. Missing a real instance is costly.

## Breadth mode: propose new samples

After the human reviews a batch:
1. **Cover gaps**: sample from unreviewed clusters, topics, or feature regions.
2. **Random exploration**: always include a few random picks.
3. Push new samples to `POST /api/samples`. The app shows a banner.
4. Tell the human what was added and why.

## Encourage re-review

Do not treat review as one pass. The reviewer's criteria shift as they see more data (criteria drift).

The agent handles part of this automatically. Background subagents scan already-reviewed records and push suggestions. But the agent cannot catch everything. After the reviewer has gone through a batch and found new modes, explicitly encourage them to re-read earlier records. Say something like: "You've found 3 new failure modes since you reviewed records 0 through 5. Worth a second pass. You will likely spot things you missed the first time."

## Report and converge

Periodically:
- Report the failure mode taxonomy with confirmed and suggested counts.
- Report coverage: records reviewed, clusters or dimensions covered, what remains.
- Track convergence: are new records mostly repeats of known modes, or are they revealing new ones?
- When the rate of new discoveries drops, suggest stopping or narrowing focus.

## Key principles

1. **The human notices, the agent organizes.** Free-text notes become a structured taxonomy. Do not make the human categorize.
2. **The agent proposes coverage.** Propose new samples based on what has been found and what is missing.
3. **Live feedback loop.** Monitor and react as annotations come in.
4. **Include random samples.** Always include random picks alongside cluster-based ones so you do not miss what the clustering did not capture.
5. **Multiple passes.** The reviewer's criteria shift over time. Encourage re-review of earlier records.
6. **Agent suggests, human confirms.** Suggestions are visually distinct and require accept or dismiss. Favor recall over precision.
7. **Breadth then depth, repeat.** Review broadly to find modes, examine each mode in depth, then go broad again.
