"""FourCast style contracts + every prompt in the pipeline.

The four styles are treated as executable contracts: a prompt block the
stylist must satisfy and a validator the judge (and regex firewall) enforces.
"""
import re

STYLES = ["formal", "sarcastic", "humorous_tech", "humorous_non_tech"]

# Words that instantly break the humorous_non_tech contract.
TECH_JARGON = re.compile(
    r"\b(algorithm|API|server|code|coding|program(?:ming|mer)?|software|hardware|"
    r"CPU|GPU|RAM|cloud|database|debug|deploy|frontend|backend|javascript|python|"
    r"AI|LLM|neural|robot(?:ic)?s?|bandwidth|wifi|wi-fi|internet|browser|app|"
    r"startup|crypto|blockchain|pixel|render|compile|kernel|linux|byte|bit|"
    r"machine learning|data|upload|download|stream(?:ing)?|buffer(?:ing)?|"
    r"low.?latency|latency|404|glitch|firmware|update|patch|version|beta)\b",
    re.IGNORECASE,
)

STYLE_CONTRACTS = {
    "formal": (
        "FORMAL: Professional, objective, factual tone. One or two sentences, "
        "max ~35 words. No contractions, no slang, no emoji, no exclamation "
        "marks, no first person, no jokes. Precise verbs. Read like a news "
        "agency photo caption or a corporate report line."
    ),
    "sarcastic": (
        "SARCASTIC: Dry, ironic, lightly mocking. The humour comes from "
        "deadpan overstatement or faux-praise of something mundane that is "
        "ACTUALLY VISIBLE in the video. No meanness toward real people, no "
        "profanity. No 'haha', no emoji. One or two sentences. Think tired "
        "narrator who has seen it all."
    ),
    "humorous_tech": (
        "HUMOROUS_TECH: Funny, with technology or programming references. "
        "Map something ACTUALLY VISIBLE in the video onto a tech concept "
        "(deploys, standups, merge conflicts, load balancing, caching, "
        "low battery...). The joke must land for a software crowd but still "
        "describe the actual video. One or two sentences, no profanity."
    ),
    "humorous_non_tech": (
        "HUMOROUS_NON_TECH: Funny, everyday humour with ZERO technical "
        "vocabulary — no computers, apps, internet, AI, phones, or work-tech "
        "references of any kind. Use everyday life (food, weather, naps, "
        "Mondays, chores) as COMPARISONS or similes for what is visible — e.g. "
        "'moving with all the urgency of a Monday morning'. Do NOT claim those "
        "things are happening: never invent people, relatives, backstories, "
        "places, or events that are not in the video. The joke describes what "
        "is ACTUALLY VISIBLE. One or two sentences, no profanity."
    ),
}

PERCEIVER_SYSTEM = (
    "You are a meticulous video analyst. You receive timestamped frames "
    "sampled from ONE video clip. Report ONLY what is visibly present — "
    "never guess, never embellish. Describe any people generically by role or "
    "appearance (e.g. 'an office worker', 'a cyclist') — never identify them. "
    "English only. Reply with the requested JSON object and nothing else."
)

PERCEIVER_USER = """Analyse these {n} frames (timestamps given) from one video clip.

Be concise: total response under 220 words. Summary max 3 short sentences.
Return STRICT JSON, no markdown fences, matching exactly:
{{
  "summary": "2-3 sentences describing what happens across the clip",
  "setting": "where this takes place",
  "subjects": ["main visible subjects"],
  "actions": ["main visible actions/events in order"],
  "on_screen_text": ["any readable text, else empty"],
  "camera": "static/panning/handheld/aerial etc.",
  "mood": "one phrase",
  "distinctive_details": ["3-6 small concrete visible details that make this clip unique"]
}}"""

STYLIST_SYSTEM = (
    "You are FourCast, an award-winning caption writer. You write captions "
    "STRICTLY grounded in the provided scene report — if a fact is not in "
    "the report, it does not exist. English only."
)

STYLIST_USER = """SCENE REPORT (ground truth, do not contradict or invent):
{scene_report}

Write {k} DIFFERENT candidate captions for this video in the following style.

STYLE CONTRACT — {style_name}:
{contract}

Rules:
- Ground EVERY candidate strictly in the scene report. Do NOT invent settings,
  backstories, locations, objects, numbers, distances, or events that are not in
  the report — not even to make a joke land. Humour must come from how you
  describe what is ACTUALLY visible, never from fictional context.
- Each candidate must reference concrete visible content (subjects/actions/details).
- Write ONE self-contained caption per candidate (one or two sentences). Never put
  multiple captions, lists, or numbered options inside a single candidate string.
- Vary the angle between candidates.
Return STRICT JSON, no fences: {{"candidates": ["...", "...", "..."]}}"""

JUDGE_SYSTEM = (
    "You are the official evaluation judge for a video captioning contest. "
    "You are strict, consistent, and immune to flattery. English only."
)

JUDGE_USER = """SCENE REPORT (what is actually in the video):
{scene_report}

STYLE CONTRACT:
{contract}

CANDIDATE CAPTIONS:
{candidates_block}

Score EVERY candidate on:
- accuracy (0.0-1.0): does it faithfully reflect the scene report? Penalise
  invented facts hard (anything not in the report).
- style (0.0-1.0): does it fulfil the style contract? Penalise contract
  violations hard (e.g. tech words in humorous_non_tech, jokes in formal).

Return STRICT JSON, no fences:
{{"scores": [{{"i": 0, "accuracy": 0.0, "style": 0.0, "note": "one line"}}, ...],
 "best": <index of best candidate>,
 "critique_for_retry": "one sentence on how to beat the best candidate"}}"""

REFINE_USER = """Your previous best candidate for style {style_name} scored
accuracy={acc:.2f}, style={sty:.2f}. Judge critique: {critique}

SCENE REPORT (unchanged ground truth):
{scene_report}

STYLE CONTRACT:
{contract}

Write {k} NEW candidates that fix the critique while staying grounded.
Return STRICT JSON, no fences: {{"candidates": ["...", "..."]}}"""


def jargon_violations(text: str) -> list[str]:
    """Tech words that would sink a humorous_non_tech caption."""
    return sorted({m.group(0).lower() for m in TECH_JARGON.finditer(text)})


def fallback_caption(scene: dict, style: str) -> str:
    """Deterministic last-resort caption if all generation fails.

    A plain grounded sentence scores far better than a missing style (zero).
    """
    summary = (scene or {}).get("summary") or "A short video clip."
    base = summary.split(". ")[0].rstrip(".")
    if style == "formal":
        return f"{base}."
    if style == "sarcastic":
        return f"Ah yes, {base[0].lower() + base[1:]} — truly groundbreaking stuff."
    if style == "humorous_tech":
        return f"{base}. Basically a live production deploy, but with better lighting."
    return f"{base}. Somewhere, a grandmother is still unimpressed."
