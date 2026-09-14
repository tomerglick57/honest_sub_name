"""Keyword screen for political post titles.

The pre-LLM measure, kept as a cross-check on the model labels. Its vocabulary
is denser for 2016+ politics (trump, maga, gaza...) than for earlier eras, so
early-era shares are more likely under- than overstated.
"""
import re

POL = re.compile(r"\b(trump|biden|harris|obama|romney|mccain|palin|clinton|hillary|sanders|"
    r"bush|cheney|pelosi|mcconnell|vance|musk|maga|tea party|occupy|president|congress|senate|"
    r"election|vote[rd]?s?|voting|ballot|democrat\w*|republican\w*|gop|liberal\w*|conservativ\w*|"
    r"protest\w*|rally|politic\w*|immigra\w*|deport\w*|\bice\b|border|abortion|obamacare|"
    r"gaza|israel\w*|palestin\w*|ukrain\w*|putin|zelensk\w*|epstein|luigi|mangione|iraq|afghanistan|"
    r"fascis\w*|nazi\w*|white house|supreme court|impeach\w*|tariff\w*|executive order|snowden|nsa)\b", re.I)
