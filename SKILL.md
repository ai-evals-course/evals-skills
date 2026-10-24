---
name: error-discovery
description: Run error analysis on a dataset. Build a review UI, select diverse samples, monitor annotations, and organize failure modes.
---

# Error Discovery Skill

You are running an interactive error analysis session. The user has a dataset (JSONL, CSV, JSON, etc.) of LLM outputs or traces and wants to discover failure modes by reviewing samples.

This skill has three parts:
- This file covers phases 1 through 4. You read the data, design the UI, build it, and select samples.
- [review-loop.md](review-loop.md) covers phase 5. You run the interactive review session.
- [query-tab.md](query-tab.md) covers the Ask tab and Quail on Modal. You answer the reviewer's questions over the whole dataset with AI SQL, and you search for failure mode instances.

Read this file first to build everything. Once the app is running and the human starts reviewing, follow [review-loop.md](review-loop.md).

## Progress updates

Each phase takes time, especially building the interface. Tell the user what you are doing at each step. Before starting a phase, say what you are about to do and why. When a step finishes, say what you did and what comes next. For example: "Reading 10 sample records to understand the data shape", "Building the HTML app with three views: article, map, and progress", "Clustering on 5 features to select diverse samples." Do not go silent for long stretches.

## Phase 1: Understand the domain and data

Before building anything, study the dataset thoroughly.

### 1a: Read and inventory the data

Load the file. Examine 5 to 10 records across the distribution. For each record, identify:
- All fields, their types, and what they represent
- Which fields are the primary content the human needs to judge
- Which fields are metadata (context for understanding, but not the thing being judged)
- Which fields vary across records and which are constant

### 1b: Identify the content structure

The data could take many forms. Determine which pattern fits:

- Single text field, e.g., article, summary, email, essay, translation
- Input/output pair, e.g., prompt + completion, question + answer, instruction + result
- Multi-turn trace, e.g., a sequence of messages with different roles (system, human, assistant, tool calls, tool results, thinking/reasoning blocks). This is common for agent traces, chatbot logs, and agentic workflows.
- Code, e.g., source files, patches, diffs, with or without surrounding context
- Structured output, e.g., JSON, function calls, extracted entities, classifications
- Composite, e.g., a task description + an agent trace + a final output

For multi-turn traces specifically, identify:
- What roles or authors exist (system, user, assistant, tool, thinking, etc.)
- Whether there are tool call / tool result pairs
- Whether there are thinking/reasoning blocks
- What the logical grouping of turns is, e.g., one "step" = thinking + tool call + tool result

### 1c: Identify dimensions of variation

Think about what differs between data points and within each data point. You will use these dimensions to decide the visual design.

Between data points (vary across records):
- Metadata, e.g., topic, model, difficulty, source, label, task type
- Structural, e.g., length, number of turns, number of tool calls
- Outcome, e.g., success/failure, score

Within each data point (vary across parts of one record):
- Author/role of each segment (human vs agent vs system vs tool)
- Content type of each segment (natural language vs code vs JSON vs thinking)
- Importance/relevance of each segment (boilerplate system prompt vs the actual response)

### 1d: Think about what "bad" means

Think of a few plausible failure categories in this domain. Expect the human to discover most of them during review.

## Phase 2: Design the visual encoding

Before writing any code, design how every dimension of variation maps to a visual property. Use Gestalt principles and information visualization fundamentals.

### Core Gestalt principles to apply

- Similarity (color, shape). Viewers perceive things that share a visual property as related. Use this for categorical dimensions. Give different message roles different colors, and different labels different badge colors.
- Proximity (spacing). Viewers perceive things that are close together as grouped. Use this for logical units. Place turns in a conversation step close together, and separate steps by more space.
- Common region (containers, backgrounds). Viewers perceive things inside a shared boundary as grouped. Use this for multi-part content, e.g., a tool call and its result share a container.
- Figure/ground (opacity, contrast). Important content should be high-contrast (figure). Less important content should recede (ground). Use this for emphasis. Show boilerplate at low opacity.

### Visual encoding rules

Map each dimension of variation to exactly one visual channel. Do not use the same channel for two different things.

Color hue. Use for the categorical dimension with the most important distinction.
- For multi-turn traces, use color for message role. Each role (human, assistant, system, tool, thinking) gets its own distinct hue at full saturation. Pick 3 to 5 easily distinguishable hues.
- For single-content, use color for label or source category.
- Do not use color hue for quantitative data.

Opacity / saturation. Use to show whether the human needs to read this content carefully.
- Reduce opacity only for content the human genuinely does not need to read, e.g., repeated boilerplate that is identical across records, verbose tool schemas, auto-generated headers. Ask yourself: "if I removed this, would the human miss anything?"
- Do not mute content by role. System messages, tool results, and thinking blocks can all contain the actual bug. Mute only specific content that is redundant or mechanical, regardless of which role produced it.
- Normal content gets full opacity.

Spacing. Use for hierarchical structure.
- Tight spacing (4 to 8px) between items within a logical group, e.g., consecutive messages in one "step" of an agent trace.
- Medium spacing (16 to 24px) between logical groups, e.g., between steps.
- Large spacing (32 to 48px) between major sections.

Typography. Use for content type.
- Natural language prose: proportional font, normal size.
- Code: monospace font, slightly smaller.
- Metadata: small, muted, compact.
- Thinking/reasoning: italic or a distinct font treatment to signal "internal."

Border / container. Use for grouping related parts.
- Put a tool call and its tool result in a shared container with a subtle border.
- Separate an input/output pair with a clear divider, or place them side by side.

Structural outlier flags. Show in the header only, not inline.
- Pre-compute dataset-level averages for key structural features (length, heading count, paragraph count, etc.).
- For each record, flag dimensions where it is a clear statistical outlier (e.g., top/bottom 10%).
- Show these as small, compact badges in the header, e.g., "6 headings (more than 89%)" or "shorter than 95%."
- Keep it minimal. Most records should have zero or one flag. Do not annotate inline content.

## Phase 3: Build the review interface

### Architecture

- Python HTTP server (stdlib `http.server`, no dependencies):
  - `GET /` serves the HTML app
  - `GET /api/samples` returns the current sample set
  - `POST /api/samples` lets the agent push new samples
  - `GET /api/annotations` returns the current annotations
  - `POST /api/annotations` lets the app save annotations on every change
  - `GET /api/graph` returns the 2D projection of all records for the cluster map
  - `GET /api/patterns` returns the agent's current failure mode taxonomy
  - `POST /api/patterns` lets the agent push the updated taxonomy
  - `GET /api/suggestions` returns agent-suggested annotations
  - `POST /api/suggestions` lets the agent push suggestions
  - `POST /api/ask`, `POST /api/answer`, and `GET /api/questions` run the Ask tab. See [query-tab.md](query-tab.md).
- On-disk files in an `error_discovery_data/` directory:
  - `samples.json`, `annotations.json`, `graph.json`, `patterns.json`, `suggestions.json`, `questions.json`
- The HTML app auto-saves to the server on every annotation. It polls for new samples and suggestions.

### HTML app structure

Four views, toggled from the top bar:

1. Article/content view. The main review interface where the human reads and annotates.
2. Map view. A 2D scatter plot (PCA or UMAP projection) of all records. It shows clusters, which items are in the sample, and which have been annotated. The reviewer can click a sample node to go to its content view.
3. Progress view. Two sections:
   - Failure modes: a treemap of modes the agent has categorized so far. Each block is a failure mode, sized by annotation count. Inside each block, list the notes. The reviewer can click a note to go to that annotation in the content view.
   - Agent suggestions to review: a list of pending suggestions with checkboxes. Each row shows the failure mode, quoted text, and source record. The reviewer can click the text to go to that spot in the article. At the top, a "Select all" checkbox and "Accept selected" / "Dismiss selected" buttons. This lets the reviewer select all, uncheck the few they disagree with, and accept the rest in one click.
4. Ask view. The reviewer types a question about the whole dataset. You answer it with a Quail query on Modal, and the rows link back to records. See [query-tab.md](query-tab.md).

Content view design. Apply the visual encoding from Phase 2:

- Header: title + label + topic. Keep it minimal. Add structural outlier flags (from Phase 2) only when the record is a genuine outlier. Do not add cluster IDs, sampling method, percentile bars, or other pipeline metadata.
- Body: render the primary content using the appropriate treatment per content type.

  For multi-turn traces (agent logs, conversations, chat):
  - Each message/turn is a block. Left-align all blocks but use a colored left-border or background tint per role.
  - Role label (small, bold) at the top of each block, e.g., "System", "User", "Assistant", "Tool Call", "Tool Result", "Thinking".
  - Assign a distinct hue to each role. Be consistent across all records. All roles at full opacity by default.
  - Render thinking/reasoning blocks in a visually distinct way (e.g., lighter background, italic, or slightly indented) to show that they are internal monologue, while keeping full readability.
  - Show tool call function names prominently. Put parameters in collapsible formatted JSON.
  - Make tool results collapsible by default if they are long, with a summary line visible.
  - Only reduce opacity for content that is literally identical across records, e.g., the same system prompt repeated verbatim in every trace. If system messages vary, keep them fully visible.
  - Group related turns: a thinking block + the tool call it produces + the tool result, visually grouped with tight spacing and a shared container.

  For single text content (articles, summaries, etc.):
  - Render markdown as formatted HTML (use marked.js or similar).
  - Render plain text with paragraph breaks.

  For code / diffs:
  - Use syntax highlighting (highlight.js or Prism via CDN).
  - Show additions with green background and deletions with red background.
  - Show line numbers.

  For input/output pairs:
  - Stack them with a clear divider, or place them side by side if both are short.
  - Label each section.

- Inline annotation: the reviewer selects text, a floating popover appears with a text input, they press Enter to save, and the span is highlighted. When the popover appears and the input is focused, the browser clears the native text selection. To prevent this, wrap the selected range in a temporary highlight span (e.g., class "pending-highlight" with a visible background) BEFORE focusing the input. Remove the temporary highlight when the annotation is saved, cancelled, or the popover is dismissed by clicking outside. This way the reviewer always sees what text they are annotating.
- Margin notes: annotations and suggestions must appear as side notes in a right margin column, aligned vertically with their corresponding highlighted text. Use a two-column layout: the article body on the left (flex: 1, max-width ~720px) and a margin-notes column on the right (width ~240px). Each margin note is position: absolute inside the margin column, with its top offset calculated from the highlight element's position relative to the margin container (use getBoundingClientRect on both the highlight and the margin container, take the difference — do NOT add scrollTop, as that double-counts the scroll offset). Stack notes with a minimum gap so they do not overlap. Include hover linking: hovering a margin note outlines its highlight, and hovering a highlight outlines its margin note. Each margin note shows the quoted text, the reviewer's note, and edit/delete buttons (visible on hover). Do NOT use hover tooltips as the primary way to show annotation content — margin notes replace tooltips.
- Agent suggestions: visually distinct from human annotations in both the inline highlight (dashed border, muted tint) and the margin note (different left-border color, an "agent suggestion" tag). The margin note shows accept/dismiss buttons (always visible, not hover-gated). The reviewer can accept (which promotes it to an annotation) or dismiss.
- No quality labels, no dropdowns, no structured forms. Free-text notes only.
- Auto-save to server on every change. Keep a localStorage backup.
- Poll for new samples and suggestions periodically. Show a banner or toast when new ones arrive.

Map view:
- 2D scatter of all records from PCA/UMAP projection.
- Color by cluster (match hull colors), not by label.
- Use shape to distinguish categories, e.g., circles for AI and squares for human.
- Show sample items as larger nodes with a dark border.
- Show annotated items in a distinct color, e.g., orange.
- Draw cluster hulls or convex boundaries as subtle background shapes.
- On hover, show a tooltip with title, metadata, and annotation count.
- On click (sample nodes only), go to the content view for that item.

## Phase 4: Cluster and select initial samples

1. Extract features appropriate to the content type (see Phase 1c for the dimensions).
2. Cluster using KMeans or similar on normalized features. Target 6 to 10 clusters.
3. Build the initial sample (15 to 25 items for datasets over 50):
   - Cluster representatives (about 60 to 70%): 1 to 2 items closest to each centroid, mixing categories/labels.
   - Random samples (about 30 to 40%): from the full dataset regardless of cluster. The clustering may not capture every important dimension, so random picks help cover what it misses.
   - Remove duplicates.
4. Prioritize diversity. The goal is discovering failure modes, not estimating how common they are.

## Phase 5: Run the interactive review loop

Once the app is running and the human starts reviewing, follow [review-loop.md](review-loop.md) for the ongoing interactive session. Note that it's important to use the Monitor Tool during the interactive review process.
