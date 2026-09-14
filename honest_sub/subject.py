"""Subject labels for titles already labeled political (honest_sub.topic).

One primary subject per title. Same throughput settings as topic.py
(reasoning off, temperature 0, keyed schema).
"""
from __future__ import annotations

LABELS = {
    "T": "Trump, his family, cabinet and appointees, White House actions, Musk/DOGE",
    "I": "immigration, ICE, deportations, the border",
    "E": "elections, campaigns, candidates, voting, Congress and other US politicians (Biden, Harris, Vance, senators, governors) when the title is about them",
    "P": "protests, marches, rallies, political violence or unrest inside the US",
    "F": "politics or war outside the US: Ukraine, Gaza/Israel, other countries' leaders and conflicts, US military abroad",
    "S": "a policy or social issue: healthcare, economy, prices, tariffs, abortion, guns, LGBTQ, race, education, climate, courts",
    "H": "a historical political photo or event from before 2000",
    "O": "other political subject",
}
MODEL_TAG = "gemma-4-31b-qat/no-reasoning/t0/subject-v1"

SYSTEM = "You sort political Reddit r/pics post titles by primary subject. For each numbered title output exactly one label:\n" + \
    "\n".join(f" {k} = {v}" for k, v in LABELS.items()) + \
    "\nWhen a title fits several, choose the one the photo is about: a photo of Trump at a tariff signing is T; a photo of egg prices is S; " \
    "a protest against ICE is P; ICE agents arresting someone is I. Judge only the title. Label every item."


def schema(n: int) -> dict:
    return {"type": "object",
            "properties": {str(i): {"type": "string", "enum": list(LABELS)} for i in range(n)},
            "required": [str(i) for i in range(n)],
            "additionalProperties": False}


def label_batch(lm, titles: list[str], max_tokens: int = 3000) -> list[str]:
    listing = "\n".join(f"{i}. {' '.join((t or '').split())[:220]}" for i, t in enumerate(titles))
    out = lm.chat_json(SYSTEM, listing, schema(len(titles)), max_tokens=max_tokens,
                       temperature=0.0, extra={"reasoning_effort": "none"})
    labs = [out.get(str(i)) for i in range(len(titles))]
    if any(l not in LABELS for l in labs):
        raise ValueError(f"schema violated: {labs}")
    return labs
