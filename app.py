"""
app.py

Gradio interface for FitFindr.

Run with:
    python app.py

Then open the localhost URL shown in your terminal.
"""

import warnings
warnings.filterwarnings("ignore", message=".*HTTP_422_UNPROCESSABLE_ENTITY.*")

import gradio as gr

from agent import run_agent
from utils.data_loader import get_example_wardrobe, get_empty_wardrobe
from utils.profile_store import load_profile, save_profile


# ── query handler ─────────────────────────────────────────────────────────────

def handle_query(
    user_query: str, wardrobe_choice: str, profile_name: str
) -> tuple[str, str, str]:
    """
    Called by Gradio when the user submits a query.

    Args:
        user_query:      Text the user typed into the search box.
        wardrobe_choice: "Example wardrobe" or "Empty wardrobe (new user)".
        profile_name:    Optional profile name for style memory. If a saved
                         profile exists, its size/price/keywords are merged
                         into the query automatically.

    Returns:
        (listing_text, outfit_suggestion, fit_card) — one string per panel.
    """
    if not user_query or not user_query.strip():
        return "Please enter a search query.", "", ""

    # Load profile and enrich the query with saved preferences
    profile = None
    name = profile_name.strip() if profile_name else ""
    if name:
        profile = load_profile(name)

    effective_query = user_query.strip()
    if profile:
        # Append saved size if the query doesn't already specify one
        if profile.get("size") and "size" not in effective_query.lower():
            effective_query += f" size {profile['size']}"
        # Append saved price ceiling if the query doesn't already specify one
        if profile.get("max_price") and "under" not in effective_query.lower():
            effective_query += f" under ${profile['max_price']:.0f}"

    wardrobe = (
        get_example_wardrobe()
        if wardrobe_choice == "Example wardrobe"
        else get_empty_wardrobe()
    )

    session = run_agent(effective_query, wardrobe)

    # Persist preferences for future sessions if a name was given
    if name and not session["error"]:
        parsed = session.get("parsed", {})
        keywords = [
            w for w in parsed.get("description", "").lower().split() if len(w) > 2
        ][:8]
        save_profile(
            name=name,
            size=parsed.get("size"),
            max_price=parsed.get("max_price"),
            style_keywords=keywords,
        )

    if session["error"]:
        return session["error"], "", ""

    item = session["selected_item"]
    listing_text = (
        f"Title:     {item['title']}\n"
        f"Price:     ${item['price']}\n"
        f"Platform:  {item['platform']}\n"
        f"Size:      {item['size']}\n"
        f"Condition: {item['condition']}\n"
        f"Colors:    {', '.join(item['colors'])}\n"
        f"Style:     {', '.join(item['style_tags'])}\n\n"
        f"{item['description']}"
    )

    return listing_text, session["outfit_suggestion"], session["fit_card"]


# ── interface ─────────────────────────────────────────────────────────────────

EXAMPLE_QUERIES = [
    "vintage graphic tee under $30",
    "90s track jacket in size M",
    "flowy midi skirt under $40",
    "black combat boots size 8",
    "designer ballgown size XXS under $5",
]


def build_interface():
    with gr.Blocks(title="FitFindr") as demo:
        gr.Markdown("""
# FitFindr 🛍️
Find secondhand pieces and get outfit ideas based on your wardrobe.
Describe what you're looking for — include size and price if you want to filter.
        """)

        with gr.Row():
            query_input = gr.Textbox(
                label="What are you looking for?",
                placeholder="e.g. vintage graphic tee under $30, size M",
                lines=2,
                scale=3,
            )
            wardrobe_choice = gr.Radio(
                choices=["Example wardrobe", "Empty wardrobe (new user)"],
                value="Example wardrobe",
                label="Wardrobe",
                scale=1,
            )

        with gr.Row():
            profile_input = gr.Textbox(
                label="Style profile name (optional)",
                placeholder="e.g. alex — saves your size & price preferences for next time",
                lines=1,
                scale=2,
            )
            gr.Markdown(
                "**Profile memory:** enter a name to save your size and budget "
                "preferences. On your next search, they'll be applied automatically.",
                elem_classes=["profile-hint"],
            )

        submit_btn = gr.Button("Find it", variant="primary")

        with gr.Row():
            listing_output = gr.Textbox(
                label="🛍️ Top listing found",
                lines=8,
                interactive=False,
            )
            outfit_output = gr.Textbox(
                label="👗 Outfit idea",
                lines=8,
                interactive=False,
            )
            fitcard_output = gr.Textbox(
                label="✨ Your fit card",
                lines=8,
                interactive=False,
            )

        gr.Examples(
            examples=[[q, "Example wardrobe", ""] for q in EXAMPLE_QUERIES],
            inputs=[query_input, wardrobe_choice, profile_input],
            label="Try these queries",
        )

        submit_btn.click(
            fn=handle_query,
            inputs=[query_input, wardrobe_choice, profile_input],
            outputs=[listing_output, outfit_output, fitcard_output],
        )
        query_input.submit(
            fn=handle_query,
            inputs=[query_input, wardrobe_choice, profile_input],
            outputs=[listing_output, outfit_output, fitcard_output],
        )

    return demo


if __name__ == "__main__":
    demo = build_interface()
    demo.launch()
