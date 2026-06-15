# FitFindr — planning.md

> Complete this document before writing any implementation code.
> Your spec and agent diagram are what you'll use to direct AI tools (Claude, Copilot, etc.) to generate your implementation — the more specific they are, the more useful the generated code will be.
> Your planning.md will be reviewed as part of your submission.
> Update it before starting any stretch features.

---

## Tools

List every tool your agent will use. For each tool, fill in all four fields.
You must have at least 3 tools. The three required tools are listed — add any additional tools below them.

### Tool 1: search_listings

**What it does:**
Searches the mock listings dataset for items that match a natural-language description, an optional size, and an optional price ceiling. Returns a ranked list of matching listing dicts, sorted by relevance score from highest to lowest.

**Input parameters:**
- `description` (str): Keywords describing what the user wants (e.g., "vintage graphic tee"). Used to score keyword overlap against listing titles, descriptions, style_tags, and categories.
- `size` (str | None): Size string to filter by, or None to skip size filtering. Matching is case-insensitive and partial (e.g., "M" matches "S/M").
- `max_price` (float | None): Maximum price inclusive, or None to skip price filtering.

**What it returns:**
A list of listing dicts sorted by relevance score (highest first). Each dict contains: `id`, `title`, `description`, `category`, `style_tags` (list[str]), `size`, `condition`, `price` (float), `colors` (list[str]), `brand`, `platform`. Returns an empty list if nothing matches — never raises an exception.

**What happens if it fails or returns nothing:**
If the returned list is empty, the planning loop sets `session["error"]` to a specific message that names the description, size, and price constraints used, and suggests the user try broadening the search (e.g., remove size filter or try different keywords). The agent returns early without calling `suggest_outfit` or `create_fit_card`.

---

### Tool 2: suggest_outfit

**What it does:**
Given a thrifted listing dict and the user's wardrobe dict, calls the Groq LLM (llama-3.3-70b-versatile) to suggest 1–2 complete outfit combinations. If the wardrobe is empty, returns general styling advice for the item instead of crashing.

**Input parameters:**
- `new_item` (dict): A listing dict — the item the user is considering buying.
- `wardrobe` (dict): A wardrobe dict with an `items` key containing a list of wardrobe item dicts. Each wardrobe item has: `id`, `name`, `category`, `colors` (list[str]), `style_tags` (list[str]), `notes` (str | None).

**What it returns:**
A non-empty string with outfit suggestions. If the wardrobe has items, the response names specific pieces from the wardrobe by name. If the wardrobe is empty, it offers general styling ideas (what kinds of items pair well, what vibe suits the piece).

**What happens if it fails or returns nothing:**
If `wardrobe['items']` is empty, the LLM is called with a general styling prompt — the function does not raise an exception or return an empty string. The returned suggestion is stored in `session["outfit_suggestion"]` regardless of whether the wardrobe was populated.

---

### Tool 3: create_fit_card

**What it does:**
Calls the Groq LLM (llama-3.3-70b-versatile) with a high temperature to generate a 2–4 sentence casual, shareable outfit caption — the kind of thing someone would post as an Instagram/TikTok OOTD. Outputs must vary across runs for different inputs.

**Input parameters:**
- `outfit` (str): The outfit suggestion string from `suggest_outfit`.
- `new_item` (dict): The listing dict for the thrifted item (used to pull title, price, and platform for the caption).

**What it returns:**
A 2–4 sentence string that mentions the item name, price, and platform naturally (once each), captures the outfit vibe in specific terms, and sounds like a real person posting — not a product description.

**What happens if it fails or returns nothing:**
If `outfit` is empty or whitespace-only, the function returns the string `"Error: No outfit suggestion available — cannot generate a fit card."` without calling the LLM and without raising an exception.

---

### Additional Tools

#### Style Profile Memory (Stretch Feature)

**What it does:**
Persists user style preferences (size, max price, description keywords) to a JSON file keyed by profile name. On subsequent runs with the same profile name, automatically merges saved preferences into the query so the user does not have to re-enter their size or budget.

**Functions:**
- `save_profile(name, size, max_price, style_keywords)` → None: writes `profiles/{name}.json`
- `load_profile(name)` → dict | None: reads `profiles/{name}.json`, returns None if not found

**What it returns:**
`save_profile` returns nothing. `load_profile` returns a dict with keys `name`, `size`, `max_price`, `style_keywords` (list[str]), or None if no profile file exists for that name.

**What happens if it fails:**
If the profiles directory does not exist, `save_profile` creates it. If `load_profile` cannot find the file, it returns None and the agent proceeds without profile enrichment.

---

## Planning Loop

**How does your agent decide which tool to call next?**

The planning loop in `run_agent()` follows this conditional logic:

1. **Parse the query** using regex to extract `description`, `size`, and `max_price`. Size is matched by `\bsize\s+([A-Za-z0-9/]+)`; price is matched by `under\s*\$?(\d+\.?\d*)`. The remainder after stripping those patterns becomes `description`. Store in `session["parsed"]`.

2. **Call `search_listings`** with the parsed parameters. Store results in `session["search_results"]`.

3. **Check if results is empty.** If `len(session["search_results"]) == 0`: set `session["error"]` to a message naming the exact constraints that failed and what the user can try (e.g., "No listings found for 'designer ballgown' in size XXS under $5. Try removing the size filter or raising the price limit."). Return the session immediately. Do NOT proceed to Step 4.

4. **Select the top result.** Set `session["selected_item"] = session["search_results"][0]`.

5. **Call `suggest_outfit`** with `session["selected_item"]` and the `wardrobe` passed into `run_agent`. Store the return value in `session["outfit_suggestion"]`.

6. **Call `create_fit_card`** with `session["outfit_suggestion"]` and `session["selected_item"]`. Store the return value in `session["fit_card"]`.

7. **Return the session.**

The agent's behavior branches at Step 3 — it does not call all three tools unconditionally. An empty search result short-circuits the loop before any LLM calls are made.

---

## State Management

**How does information from one tool get passed to the next?**

All state lives in a single session dict initialized by `_new_session()`. The fields written and read at each step are:

| Step | Written to session | Read by next step |
|------|--------------------|-------------------|
| Parse | `session["parsed"]` → `{description, size, max_price}` | search_listings call |
| search_listings | `session["search_results"]` → list of dicts | empty-check, item selection |
| Item selection | `session["selected_item"]` → single listing dict | suggest_outfit call |
| suggest_outfit | `session["outfit_suggestion"]` → string | create_fit_card call |
| create_fit_card | `session["fit_card"]` → string | returned to caller |

No tool is called with re-entered data. `selected_item` is the exact same dict object that came out of `search_listings` — it's stored in the session and passed directly into `suggest_outfit`. The outfit string from `suggest_outfit` is stored and passed directly into `create_fit_card`.

---

## Error Handling

For each tool, describe the specific failure mode you're handling and what the agent does in response.

| Tool | Failure mode | Agent response |
|------|-------------|----------------|
| search_listings | No listings match the query (empty results list) | Sets `session["error"]` to a message naming the exact constraints (description, size, max_price) and suggests specific adjustments: "Try removing the size filter or raising the price limit." Returns the session early without calling suggest_outfit or create_fit_card. |
| suggest_outfit | `wardrobe['items']` is empty (new user with no wardrobe) | Calls the LLM with a general styling prompt asking for styling ideas, what kinds of items pair well, and what vibe the piece suits. Returns a non-empty string. Does not raise an exception or return an empty string. |
| create_fit_card | `outfit` parameter is empty or whitespace-only | Returns the string `"Error: No outfit suggestion available — cannot generate a fit card."` without calling the LLM. Does not raise an exception. |

---

## Architecture

```
User query
    │
    ▼
handle_query() in app.py
    │  (load profile if profile_name given)
    │  (enrich query with saved size/price from profile)
    │
    ▼
run_agent(query, wardrobe)  ← Planning Loop
    │
    ├─► _parse_query(query)
    │       regex extracts: description, size, max_price
    │       stored in session["parsed"]
    │
    ├─► search_listings(description, size, max_price)
    │       │
    │       │ results = []  ──────────────────────────────────────┐
    │       │                                                     │
    │       │ results = [item1, item2, ...]                       │
    │       ▼                                                     │
    │   session["search_results"] = results                      │
    │   session["selected_item"] = results[0]                    │
    │                                                             │
    ├─► suggest_outfit(selected_item, wardrobe)                  │
    │       │                                                     │
    │       ├─ wardrobe empty? ──► LLM: general styling advice   │
    │       └─ wardrobe has items? ──► LLM: specific outfit      │
    │       stored in session["outfit_suggestion"]               │
    │                                                             │
    └─► create_fit_card(outfit_suggestion, selected_item)        │
            │                                                     │
            ├─ outfit empty? ──► return error string             │
            └─ LLM: generate Instagram caption (temp=1.0)        │
            stored in session["fit_card"]                        │
            │                                                     │
            ▼                                          [ERROR]◄──┘
        Return session              session["error"] set, fit_card=None


Session dict (single source of truth):
  query → parsed → search_results → selected_item
                                         │
                                  outfit_suggestion → fit_card
```

---

## AI Tool Plan

**Milestone 3 — Individual tool implementations:**

For `search_listings`: I will give Claude the Tool 1 spec block from planning.md (inputs with types, return value description, failure mode) and ask it to implement the function in tools.py using `load_listings()` from `utils/data_loader.py`. Before running it, I will check that the generated code: (a) filters by both `max_price` and `size` before scoring, (b) uses keyword overlap against title, description, style_tags, and category, (c) drops zero-score listings, (d) returns an empty list (not an exception) when nothing matches. I will test it against three queries: "vintage graphic tee" (expect results), "designer ballgown XXS under $5" (expect empty), and "jacket under $10" (expect all results priced ≤ $10).

For `suggest_outfit`: I will give Claude the Tool 2 spec block and the Groq client setup in tools.py, and ask it to implement the function using `llama-3.3-70b-versatile`. I will verify the generated code checks `wardrobe['items']` before building the prompt, uses a different prompt for empty vs. non-empty wardrobes, and calls `client.chat.completions.create()` with temperature 0.7. I will test it with both `get_example_wardrobe()` and `get_empty_wardrobe()`.

For `create_fit_card`: I will give Claude the Tool 3 spec block, including the variability requirement, and ask it to implement the function with temperature 1.0. I will verify the guard against an empty `outfit` string is in place before the LLM call. I will run it three times on the same input and confirm the outputs differ.

**Milestone 4 — Planning loop and state management:**

I will give Claude the Architecture diagram and the Planning Loop + State Management sections from planning.md, and ask it to implement `run_agent()` in agent.py. I will review that the generated code: (a) branches on the search result being empty, (b) does not call suggest_outfit or create_fit_card when search returns [], (c) stores each result in the correct session field. I will run both CLI test cases in agent.py (`__main__` block) and verify the happy path shows a fit card and the no-results path shows an error message with `session["fit_card"]` equal to None.

---

## A Complete Interaction (Step by Step)

**Example user query:** "vintage graphic tee under $30"

**Step 1:**
The planning loop calls `_parse_query("vintage graphic tee under $30")`. Regex matches `under $30` → `max_price=30.0`. No size pattern found → `size=None`. Remaining text → `description="vintage graphic tee"`. Stored in `session["parsed"] = {description: "vintage graphic tee", size: None, max_price: 30.0}`.

**Step 2:**
`search_listings("vintage graphic tee", size=None, max_price=30.0)` is called. All 40 listings are loaded. Listings priced above $30 are dropped. Remaining listings are scored: each keyword in "vintage graphic tee" is checked against each listing's title, description, style_tags, and category. Listings with score 0 are dropped. Results are sorted by score descending. The function returns a list — e.g., `[{id: "lst_006", title: "Faded Band Tee — Graphic Print", price: 22.0, ...}, ...]`. This list is stored in `session["search_results"]`.

**Step 3:**
Results list is non-empty, so the agent does NOT return early. `session["selected_item"] = results[0]` → the Faded Band Tee at $22 on Depop.

**Step 4:**
`suggest_outfit(selected_item, get_example_wardrobe())` is called. The wardrobe has 10 items, so the non-empty branch runs. A prompt is built listing all wardrobe items and asking the LLM to suggest specific outfit combinations using the band tee. The LLM responds: "Pair this with your baggy straight-leg jeans and chunky white sneakers for a classic 90s streetwear look. Alternatively, layer it under your vintage black denim jacket with the wide-leg khakis for a more put-together grunge vibe." Stored in `session["outfit_suggestion"]`.

**Step 5:**
`create_fit_card(outfit_suggestion, selected_item)` is called. `outfit_suggestion` is non-empty so the LLM is called with temperature 1.0. The LLM returns: "thrifted this faded band tee off depop for $22 and it was literally made for my wide-legs 🖤 classic 90s streetwear energy, full look in my stories". Stored in `session["fit_card"]`.

**Final output to user:**
The Gradio UI displays three panels:
- **Top listing found:** "Title: Faded Band Tee — Graphic Print | Price: $22.0 | Platform: depop | Size: M | Condition: good | ..."
- **Outfit idea:** The full LLM-generated outfit suggestion.
- **Your fit card:** The Instagram-style caption.
