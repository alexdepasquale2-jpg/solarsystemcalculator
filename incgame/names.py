"""
Word pools for procedural naming.

Names are the cheapest way to make two runs feel like different games, so the
pools are deliberately large and thematically loose. Everything here is data
only -- no logic, no randomness. `rng.py` does the picking.
"""

# Adjectives used across resources, actions, generators, and upgrades.
ADJECTIVES = [
    "Luminous", "Fractal", "Hollow", "Verdant", "Gilded", "Umbral", "Crystalline",
    "Sundered", "Woven", "Placid", "Feral", "Latent", "Radiant", "Quiet", "Molten",
    "Frozen", "Drifting", "Ancient", "Nascent", "Eternal", "Restless", "Silent",
    "Vivid", "Pale", "Deep", "Wild", "Tame", "Bright", "Dim", "Vast", "Brittle",
    "Supple", "Errant", "Patient", "Sullen", "Tidal", "Vagrant", "Wakeful",
    "Cindered", "Glassen", "Riven", "Sodden", "Tempered", "Unbound", "Waning",
    "Waxing", "Hushed", "Keen", "Numb", "Opaline",
]

# Resource nouns -- mass nouns and substances work best.
RESOURCE_NOUNS = [
    "Essence", "Ember", "Filament", "Lumen", "Grain", "Chime", "Cinder", "Dust",
    "Echo", "Fragment", "Glyph", "Husk", "Ichor", "Kernel", "Lattice", "Mote",
    "Nectar", "Ore", "Pulse", "Quill", "Resin", "Sap", "Shard", "Silt", "Spark",
    "Tide", "Vein", "Whisper", "Yield", "Bloom", "Coil", "Drift", "Flux", "Gleam",
    "Haze", "Loam", "Murmur", "Rime", "Thread", "Brine", "Chaff", "Ash", "Marrow",
    "Vapour", "Sediment", "Static", "Tincture", "Verdure", "Wick", "Zephyr",
]

# Verbs for manual actions.
ACTION_VERBS = [
    "Gather", "Coax", "Sift", "Kindle", "Thresh", "Distill", "Fold", "Harvest",
    "Tap", "Whittle", "Draw", "Stir", "Weave", "Refine", "Temper", "Grind",
    "Siphon", "Nurture", "Prune", "Chase", "Sound", "Bind", "Unspool", "Quicken",
    "Scatter", "Anneal", "Winnow", "Rouse", "Steep", "Press", "Gild", "Cull",
    "Braid", "Leach", "Render", "Sluice", "Tease", "Knead", "Skim", "Provoke",
]

# Nouns for passive generators -- places and apparatus.
GENERATOR_NOUNS = [
    "Loom", "Kiln", "Orchard", "Cistern", "Rookery", "Foundry", "Glasshouse",
    "Aviary", "Mill", "Hearth", "Weir", "Apiary", "Grotto", "Spire", "Terrace",
    "Furnace", "Trellis", "Reliquary", "Conduit", "Vat", "Bellows", "Wellspring",
    "Nursery", "Garden", "Manifold", "Sluiceway", "Dovecote", "Smithy", "Cellar",
    "Refinery", "Colonnade", "Aqueduct", "Crucible", "Lantern", "Beacon", "Silo",
]

# Nouns for upgrades -- techniques and knowledge.
UPGRADE_NOUNS = [
    "Attunement", "Doctrine", "Insight", "Protocol", "Ritual", "Schema", "Sigil",
    "Technique", "Theorem", "Alignment", "Calibration", "Discipline", "Etching",
    "Grammar", "Habit", "Method", "Praxis", "Refrain", "Tuning", "Cadence",
    "Codex", "Gesture", "Lemma", "Mantra", "Notation", "Ordinance", "Precept",
    "Rubric", "Stanza", "Treatise",
]

# Upgrade families. Owning many upgrades from one family is what synergy
# mechanics key off, so the names need to read like schools of thought.
FAMILY_NAMES = [
    "Husbandry", "Metallurgy", "Cartography", "Rhetoric", "Alchemy", "Masonry",
    "Astronomy", "Botany", "Horology", "Cryptography", "Acoustics", "Optics",
    "Ceramics", "Navigation", "Taxonomy", "Rheology", "Glassblowing", "Falconry",
]

# Prestige currency names -- things left behind.
PRESTIGE_NOUNS = [
    "Ascendance", "Continuum", "Legacy", "Remnant", "Testament", "Afterglow",
    "Palimpsest", "Residue", "Inheritance", "Keepsake", "Sediment", "Watermark",
    "Patina", "Vestige", "Relic",
]

# Two-part world titles: "The {adjective} {noun}".
TITLE_NOUNS = [
    "Foundry", "Orchard", "Archive", "Meridian", "Threshold", "Confluence",
    "Reliquary", "Aviary", "Terrace", "Observatory", "Estuary", "Bastion",
    "Cloister", "Hollow", "Expanse", "Waystation", "Menagerie", "Conservatory",
]

# Flavour sentence fragments, assembled into the run's opening line.
FLAVOUR_OPENINGS = [
    "Nothing here remembers the last attempt.",
    "The ledgers are blank and the machines are cold.",
    "You arrive before the first measurement is taken.",
    "Everything is still potential, which is to say: nothing works yet.",
    "The place was built by someone with different priorities.",
    "It has been quiet for a long time.",
    "The inventory is a rumour and the tools are unfamiliar.",
    "Whatever ran this before left no instructions.",
]

FLAVOUR_CLOSINGS = [
    "Begin with your hands.",
    "Start small; the rest compounds.",
    "Find out what feeds what.",
    "The order of operations is yours to discover.",
    "Some of it will be worth automating.",
    "Learn the ratios before you commit.",
    "Waste is only waste if nothing downstream wants it.",
]

# Description templates. `{n}` = the thing's own name, `{a}`/`{b}` = related
# resource names, `{v}` = a verb.
RESOURCE_DESCRIPTIONS = [
    "Accumulates in the low places. Everything else starts here.",
    "Fine enough to slip through a closed hand.",
    "Cold to the touch and faintly reluctant.",
    "Worth more once it has been through something.",
    "Measured by volume, valued by clarity.",
    "Keeps its shape only while you are watching.",
    "The residue of work already done.",
    "Dense, patient, and slow to give anything up.",
    "Bright at first. Less so by morning.",
    "Refuses to be stored for long.",
]

ACTION_DESCRIPTIONS = [
    "Slow work, but it needs no equipment.",
    "Repetitive. Effective. Unglamorous.",
    "The yield depends mostly on your patience.",
    "A conversion anyone can perform badly.",
    "Costs something. Returns something better.",
    "Best done in batches, if you can afford them.",
    "The first thing you learn and the last thing you stop doing.",
]

GENERATOR_DESCRIPTIONS = [
    "Runs without supervision, which is the entire point.",
    "Noisy, but it never asks for a break.",
    "Pays for itself eventually. Eventually is doing a lot of work here.",
    "Wants feeding. Produces more than it eats.",
    "Each one you add makes the next one dearer.",
    "Built once, tended never.",
]

UPGRADE_DESCRIPTIONS = [
    "A better way of doing what you already do.",
    "Obvious in hindsight.",
    "Someone worked this out before you and wrote it down badly.",
    "Marginal on its own. Not on its own for long.",
    "Changes the arithmetic, not the work.",
    "Trades understanding for throughput.",
]
