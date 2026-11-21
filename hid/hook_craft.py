#!/usr/bin/env python3
"""hook_craft.py — LLM-evaluation dimensions for opener strength, from Vyral viral-hooks craft (MIT, technique-only adoption).

Dimension scorecards; used by director/vision LLM passes as evaluation prompts.
Policy gates preserved: pentakewl = NO burned hooks/text overlays; 'text layer' here means what the TikTok uploader may add, not what we render.
"""
ANTIPATTERNS = [
    "welcome intro / greeting before value", "logo or branding animation first",
    "vague tease ('you won't believe this')", "bait-and-switch promise",
    "subscribe-before-value ask", "flat opening frame (visually dead first second)",
    "hook unresolved by ~3s", "story opener with no stakes on short-form",
]
ARCHETYPES = {
    "contrarian": "opens against common expectation",
    "investigator": "testing/ranking promise with specific count",
    "authority_gap": "credibility + unexpected insight",
    "cost_confession": "specific money/time spent for the payoff",
    "event_horizon": "imminent outcome visible in first frame",
    "mid_action": "clip starts mid-chaos, stakes readable",
    "reaction_lead": "genuine pre-laugh anticipation visible",
    "question_stake": "concrete question the gameplay answers",
}
CHECKLIST = [
    "specific concrete noun or number in first line",
    "payoff visible or clearly implied",
    "no throat-clearing",
    "resolves or escalates within ~3s",
    "first frame works with sound off",
    "promise matches what the clip delivers",
]
def scorecard():
    """Returns the evaluation brief for LLM passes (opener strength 0-10)."""
    return {
        "dims": [
            {"id": "hook_visual", "q": "Is the first frame visually alive (motion/faces/stakes) without sound?"},
            {"id": "hook_verbal", "q": "Does the first spoken line carry a specific noun/number/stake? No greeting?"},
            {"id": "hook_payoff", "q": "Is the payoff implied or visible within ~3s of the opener?"},
            {"id": "hook_match", "q": "Does the opener promise exactly what the clip delivers?"},
            {"id": "antipattern_hits", "q": "Which of the anti-patterns appear? (list; 2+ = automatic rewrite candidate)"},
        ],
        "anti_patterns": ANTIPATTERNS, "archetypes": ARCHETYPES, "checklist": CHECKLIST,
    }
