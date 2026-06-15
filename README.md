# FitFindr

A multi-tool AI agent that helps users find secondhand clothing and figure out how to wear it. FitFindr searches a mock thrift listings dataset, suggests outfit combinations using the user's wardrobe, and generates a shareable fit card — all from a single natural-language query.

---

## Running the App

```bash
pip install -r requirements.txt
# add GROQ_API_KEY=your_key to .env
python app.py
```

Open the URL shown in your terminal (usually `http://localhost:7860`).

---

## Tool Inventory

### `search_listings(description: str, size: str | None, max_price: float | None) → list[dict]`

**Purpose:** Searches the 40-item mock listings dataset and returns matching items ranked by relevance.

**Inputs:**
- `description` (str) — keywords describing the item (e.g., "vintage graphic tee")
- `size` (str | None) — size to filter by, case-insensitive partial match; `None` skips size filtering
- `max_price` (float | None) — maximum price inclusive; `None` skips price filtering

**Output:** A list of listing dicts sorted by relevance score (highest first). Each dict has: `id`, `title`, `description`, `category`, `style_tags` (list[str]), `size`, `condition`, `price` (float), `colors` (list[str]), `brand`, `platform`. Returns `[]` if nothing matches — never raises an exception.

**Relevance scoring:** Keywords from `description` are matched against each listing's title (+3 pts), style_tags (+2 pts), category (+2 pts), and description text (+1 pt). Listings with a score of 0 are dropped before sorting.

---

### `suggest_outfit(new_item: dict, wardrobe: dict) → str`

**Purpose:** Calls the Groq LLM to suggest 1–2 complete outfit combinations using the thrifted item and the user's wardrobe.

**Inputs:**
- `new_item` (dict) — a listing dict for the item the user is considering
- `wardrobe` (dict) — a wardrobe dict with an `items` key; each item has `id`, `name`, `category`, `colors` (list[str]), `style_tags` (list[str]), `notes` (str | None)

**Output:** A non-empty string. If the wardrobe has items, the response names specific wardrobe pieces by name. If the wardrobe is empty, it offers general styling advice instead of crashing.

---

### `create_fit_card(outfit: str, new_item: dict) → str`

**Purpose:** Calls the Groq LLM at temperature 1.0 to generate a casual 2–4 sentence Instagram/TikTok outfit caption.

**Inputs:**
- `outfit` (str) — the outfit suggestion from `suggest_outfit`
- `new_item` (dict) — the listing dict (used for item name, price, and platform)

**Output:** A caption that mentions the item name, price, and platform naturally (once each), captures the outfit vibe in specific terms, and sounds like a real person posting. Returns an error string (not an exception) if `outfit` is empty.

---

### `save_profile` / `load_profile` (Stretch: Style Profile Memory)

**Purpose:** Persists user style preferences (size, max price, description keywords) across sessions in `profiles/{name}.json`.

**`save_profile(name: str, size: str | None, max_price: float | None, style_keywords: list[str]) → None`**

**`load_profile(name: str) → dict | None`** — returns the saved dict or `None` if no file exists.

---

## Planning Loop

`run_agent()` in `agent.py` uses the following conditional logic:

1. **Parse the query** with regex — extracts `size` (`\bsize\s+([A-Za-z0-9/]+)`), `max_price` (`under\s*\$?(\d+\.?\d*)`), and `description` (everything remaining).

2. **Call `search_listings`** with the parsed parameters.

3. **Check the result.** If the list is empty, `session["error"]` is set to a message that names the exact constraints that failed (e.g., *"No listings found for 'designer ballgown' in size XXS under $5. Try removing the size filter..."*) and the function returns immediately. `suggest_outfit` and `create_fit_card` are **not called**.

4. **Select the top result** — `session["selected_item"] = results[0]`.

5. **Call `suggest_outfit`** with the selected item and wardrobe.

6. **Call `create_fit_card`** with the outfit suggestion and selected item.

7. **Return the session.**

The agent does not call all tools unconditionally. The branch at Step 3 means the agent's behavior changes based on what `search_listings` returns — an empty result short-circuits the loop entirely, skipping both LLM calls.

---

## State Management

All state lives in a single session dict initialized by `_new_session()`. Each step reads from the dict and writes its output back into it:

| Step | Field written | Read by |
|------|--------------|---------|
| Parse query | `session["parsed"]` → `{description, size, max_price}` | `search_listings` call |
| `search_listings` | `session["search_results"]` → list of dicts | empty check + item selection |
| Item selection | `session["selected_item"]` → single listing dict | `suggest_outfit` |
| `suggest_outfit` | `session["outfit_suggestion"]` → string | `create_fit_card` |
| `create_fit_card` | `session["fit_card"]` → string | returned to caller |

`selected_item` is the exact dict object from `search_results[0]` — it is stored in the session and passed directly into `suggest_outfit`. The outfit string from `suggest_outfit` is stored and passed directly into `create_fit_card`. The user never re-enters anything between steps.

---

## Error Handling

| Tool | Failure mode | Agent response |
|------|-------------|----------------|
| `search_listings` | No listings match all filters | Sets `session["error"]` to a message naming the specific constraints (description, size, price) and suggests concrete adjustments ("Try removing the size filter or raising the price limit"). Returns the session early — `suggest_outfit` and `create_fit_card` are never called. |
| `suggest_outfit` | `wardrobe['items']` is empty (new user) | Detects the empty list before building the prompt and sends the LLM a general-styling prompt instead of a wardrobe-specific one. Returns a non-empty string with styling ideas — no exception, no empty string. |
| `create_fit_card` | `outfit` is empty or whitespace-only | Returns the string `"Error: No outfit suggestion available — cannot generate a fit card."` before reaching the LLM call. No exception raised. |

**Concrete test examples:**

```bash
# search_listings — no results
python -c "from tools import search_listings; print(search_listings('designer ballgown', size='XXS', max_price=5))"
# → []

# suggest_outfit — empty wardrobe
python -c "
from tools import search_listings, suggest_outfit
from utils.data_loader import get_empty_wardrobe
results = search_listings('vintage graphic tee', size=None, max_price=50)
print(suggest_outfit(results[0], get_empty_wardrobe()))
"
# → general styling advice string

# create_fit_card — empty outfit
python -c "
from tools import search_listings, create_fit_card
results = search_listings('vintage graphic tee', size=None, max_price=50)
print(create_fit_card('', results[0]))
"
# → "Error: No outfit suggestion available — cannot generate a fit card."
```

---

## Style Profile Memory (Stretch Feature)

FitFindr can remember your size and budget across sessions. Enter a profile name in the Gradio UI alongside your query. On the first run, your parsed size, max price, and description keywords are saved to `profiles/{name}.json`. On subsequent runs with the same profile name, those preferences are automatically merged into the query — so if your profile has `size: M` saved, you don't need to type "size M" again.

**Storage approach:** One JSON file per profile in `profiles/`, managed by `utils/profile_store.py`. The file stores `name`, `size`, `max_price`, and up to 8 `style_keywords` from the last successful search.

---

## Spec Reflection

**One way the spec helped:** Writing the planning loop section of `planning.md` before any code forced a concrete decision about the empty-results branch early. Having the branch described in writing ("return early, do NOT call suggest_outfit with empty input") made it straightforward to verify the implementation matched — there was no ambiguity about what "error handling" meant for that tool.

**One way implementation diverged from the spec:** The initial plan described scoring keyword overlap against full description text word-by-word. During implementation, short words like "in", "a", and "for" were matching too broadly and inflating scores for unrelated listings. The final implementation filters out keywords shorter than 3 characters before scoring, which wasn't in the original spec but produced much cleaner results in testing.

---

## AI Usage

**Instance 1 — planning.md and all implementation files:**
I directed Claude (Sonnet 4.6) to fill in the full `planning.md` spec — including the tool descriptions, conditional logic for the planning loop, state management table, error handling table, architecture ASCII diagram, and the complete interaction walkthrough — using the project guidelines as input. I then directed it to implement `tools.py`, `agent.py`, `app.py`, `utils/profile_store.py`, and `tests/test_tools.py` according to the spec it had written. Before accepting the generated code I verified: (a) `search_listings` filters by both size and price before scoring, (b) the planning loop branches correctly on an empty results list and does not call LLM tools when search fails, (c) `create_fit_card` guards against an empty outfit string before the LLM call, and (d) all 9 pytest tests pass without a live API key.

**Instance 2 — query parser design decision:**
The spec left the parser approach open (regex vs. LLM). I asked Claude to evaluate both approaches given the constraint that the parser runs on every query (including the no-results path) and must be deterministic for tests. Claude recommended regex and implemented `_parse_query()` with two patterns: one for size and one for price. I verified the parser against all 5 example queries in `app.py` and both CLI test cases in `agent.py` before accepting it. I overrode one detail: the initial implementation used `\w+` for the size capture group, which would miss sizes like "S/M". I changed it to `[A-Za-z0-9/]+` to handle slash-separated sizes correctly.
