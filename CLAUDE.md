# CLAUDE.md

Guidance for AI assistants and developers working on the Creativity Engine.

## Project Overview

**Creativity Engine** — an AI-powered system for generating, refining, and exploring creative ideas across multiple domains (writing, visual concepts, music composition, game design, etc.).

The engine combines:
- **Prompt engineering** — carefully crafted system prompts and few-shot examples
- **Multi-stage workflows** — idea generation → refinement → cross-pollination → evaluation
- **Style and technique libraries** — creative constraints and methods (SCAMPER, lateral thinking, constraint-based generation)
- **Output formatting** — structured exports (JSON, markdown, images, audio metadata)

This is a **Python-first project** building toward a web interface. Start with the CLI and API, then wrap it in a UI.

## Core Principles

1. **Creativity over constraint** — The engine should surprise and delight, not limit thinking.
2. **Iterative exploration** — Users should be able to refine, remix, and recombine outputs.
3. **Domain-agnostic core** — The prompting and refinement logic should work across writing, visual, music, and other domains.
4. **Reproducibility** — Seed control and version tracking so users can replicate and build on previous ideas.
5. **Extensibility** — Easy to add new creative techniques, domains, and evaluation methods.

## Architecture (Planned)

```
creativity_engine/
  __init__.py              Public API surface
  core/
    generator.py           Main CreativityEngine class; orchestrates workflows
    prompt_library.py      Domain-specific prompts and system messages
    techniques.py          SCAMPER, lateral thinking, morphological analysis, etc.
    refinement.py          Polish, expand, constraint-apply modules
    evaluator.py           Quality scoring, coherence checks, novelty metrics
  models/
    base.py                Base classes for creative outputs
    idea.py                Idea dataclass; metadata, generations, lineage
    project.py             Project management; track related ideas
  formats/
    json_export.py         Serialize to JSON with full lineage
    markdown_export.py     Human-readable markdown output
    image_prompt.py        Generate image prompts for visual AI (DALL-E, Midjourney)
    music_metadata.py      Compose music metadata for synthesis
  integrations/
    openai_client.py       GPT-4 and GPT-3.5 via OpenAI API
    anthropic_client.py    Claude via Anthropic API (this session's model)
    local_llm.py           Optional: Ollama, LLaMA, etc.
  cli.py                   Command-line interface
  server.py                FastAPI web server (future)

tests/
  unit/
  integration/
```

## Development Workflows

### Setup

```bash
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -e .
pip install -e ".[dev]"    # pytest, black, ruff, mypy, ipython
```

### Run locally

```bash
# CLI
python -m creativity_engine --help
python -m creativity_engine generate --prompt "A time-traveling baker" --technique scamper

# Python API
from creativity_engine import CreativityEngine
engine = CreativityEngine(model="gpt-4")
ideas = engine.generate(prompt="...", technique="lateral_thinking", count=5)
```

### Testing

```bash
pytest -v
pytest tests/unit/test_generator.py
pytest --cov=creativity_engine
```

### Code quality

```bash
black .
ruff check . --fix
mypy creativity_engine
```

## Key Concepts

### Idea (dataclass)

Every output is an `Idea`:
```python
@dataclass
class Idea:
    id: str                    # UUID
    prompt: str                # Original user prompt
    technique: str             # e.g., "scamper", "constraint_based"
    domain: str                # e.g., "writing", "visual", "music"
    generations: List[str]     # The actual creative outputs
    metadata: Dict[str, Any]   # Model, temperature, seed, etc.
    parent_id: Optional[str]   # If refined from another idea
    created_at: datetime
    version: int               # Track refinements
```

**Important:** Every idea must be reproducible. Store the random seed, model version,
temperature, and exact prompt. This is the lineage.

### CreativityEngine (main class)

```python
class CreativityEngine:
    def __init__(self, model: str = "gpt-4", api_key: Optional[str] = None):
        # model: "gpt-4", "gpt-3.5-turbo", "claude-opus", "local"
        pass
    
    def generate(self, prompt: str, technique: str = "random", 
                 domain: str = "writing", count: int = 3, 
                 temperature: float = 0.9, seed: int = None) -> List[Idea]:
        # High-level: call the right prompt, parse outputs, return Ideas
        pass
    
    def refine(self, idea: Idea, direction: str = "expand") -> Idea:
        # Expand, polish, constrain, remix
        pass
    
    def cross_pollinate(self, ideas: List[Idea]) -> Idea:
        # Combine ideas into something new
        pass
    
    def evaluate(self, idea: Idea) -> Dict[str, float]:
        # Novelty, coherence, feasibility scores
        pass
```

### Technique Library

- **SCAMPER** — Substitute, Combine, Adapt, Modify, Put to another use, Eliminate, Reverse
- **Random Word** — Force association with a random word
- **Constraint-based** — Generate under explicit constraints (no nouns, must rhyme, etc.)
- **Morphological** — Decompose into dimensions, recombine
- **Lateral Thinking** — Six thinking hats, provocation, random entry
- **Mashup** — Combine two unrelated domains
- **Worst Possible Idea** — Invert and find value in the opposite

Each technique is a function or class that:
1. Takes a prompt and constraint dict
2. Builds a specialized system message
3. Calls the LLM
4. Parses and structures the output
5. Returns one or more `Idea` objects

### Domain-Specific Behavior

- **Writing** — Genres (flash fiction, poetry, screenplay, etc.), style, tone
- **Visual** — Description → image-prompt (DALL-E/Midjourney format)
- **Music** — Key, tempo, instrumentation, mood metadata → music software input
- **Game Design** — Mechanics, setting, target audience

Store domain handlers as separate modules in `formats/` or as strategy objects inside `Idea`.

## Code Conventions

**Naming:**
- Public API: simple, verb-forward (`generate()`, `refine()`, `evaluate()`)
- Private/internal: `_helper()` prefix
- Constants: `UPPER_SNAKE` for module-level, `ClassName.CONSTANT` for class-level

**Type hints:**
- All public signatures must have type hints
- Use `Optional[X]` for nullable, `List[X]` / `Dict[K, V]` for collections
- Return types always explicit

**Docstrings:**
- Google style (Parameters, Returns, Raises)
- One-liner for module docstring at top
- Multi-line for classes and functions

**Error handling:**
- `CreativityEngineError` base exception
- `ModelError` — LLM call failed
- `PromptError` — Invalid or missing prompt
- `TechniqueError` — Unknown technique
- `DomainError` — Unsupported domain

Always catch and re-raise with context; do not swallow exceptions silently.

**Testing:**
- Unit tests in `tests/unit/`; integration tests in `tests/integration/`
- Mock LLM calls (don't hit the API in unit tests)
- Test reproducibility: same seed → same output
- Parametrize over techniques and domains

## Reproducibility & Seeding

**The entire engine must be reproducible.** If a user runs:
```bash
python -m creativity_engine generate --prompt "..." --seed 42
```

They must get **identical** outputs every time. This means:

1. Store `seed` in `Idea.metadata`
2. Pass `seed` to the LLM (OpenAI supports `seed` on newer models; Claude does not)
3. If the LLM does not support seeding, document this and note the limitation
4. Use Python's `random` module for non-LLM randomness (shuffling, selecting techniques) and seed it
5. Never rely on floating-point dict ordering or other non-deterministic behavior

Example:
```python
def generate(self, ..., seed: int = None):
    if seed is not None:
        random.seed(seed)
        # Also pass to LLM if supported
    # ... continue
```

## LLM Integration

### Supported Models

- **OpenAI** — GPT-4, GPT-3.5-turbo (via `openai` package)
- **Anthropic** — Claude (via `anthropic` package)
- **Local** — Ollama/LLaMA (via `ollama` package, optional)

Each has its own client file in `integrations/`.

### API Keys

Expect `OPENAI_API_KEY`, `ANTHROPIC_API_KEY` in environment. Do **not** hardcode.

### Prompt Templates

Store all system prompts and few-shot examples in `prompt_library.py`, organized by domain and technique:
```python
PROMPTS = {
    "writing": {
        "scamper": "You are a creative writing assistant...",
        "lateral_thinking": "Explore unconventional ideas...",
    },
    "visual": {
        "scamper": "You generate visual design concepts...",
    }
}
```

Make prompts **discoverable**: add a CLI command to list and inspect them:
```bash
python -m creativity_engine list-prompts
python -m creativity_engine show-prompt writing/scamper
```

## File Organization Rules

- **One class per file**, named `class_name.py` (e.g., `idea.py` contains `Idea`, `generator.py` contains `CreativityEngine`)
- **Exception classes** in a shared `errors.py`
- **Configuration** (API endpoints, defaults) in `config.py`
- **CLI entry point** is `cli.py`; server entry point is `server.py`
- **No circular imports** — if `module_a` imports `module_b`, `module_b` must not import `module_a`

## Testing Expectations

Before any feature ships:

1. Unit test the core logic (techniques, prompt building, idea validation)
2. Integration test the full workflow (generate → refine → evaluate)
3. Mock all LLM calls in unit/integration tests (use `responses` library or `unittest.mock`)
4. Test both happy path and error cases
5. Run `pytest --cov` and aim for ≥80% coverage on core modules

Example test structure:
```python
# tests/unit/test_generator.py
from unittest.mock import patch, MagicMock
from creativity_engine import CreativityEngine

def test_generate_with_seed_is_reproducible():
    with patch('creativity_engine.integrations.openai_client.OpenAIClient.call') as mock_call:
        mock_call.return_value = "Generated idea #1"
        
        engine = CreativityEngine(model="gpt-4")
        idea1 = engine.generate(prompt="Test", seed=42)[0]
        idea2 = engine.generate(prompt="Test", seed=42)[0]
        
        assert idea1.generations == idea2.generations
```

## Documentation

- **README.md** — Quick start, installation, one example
- **TECHNIQUES.md** — Detailed guide to each creative technique
- **API.md** — Full API reference (generated from docstrings if using Sphinx)
- **Examples/** — Jupyter notebooks or Python scripts showing workflows

Keep documentation **in sync with code**. If you add a technique or method, update the docs immediately.

## Deployment & Distribution

- **PyPI** — Publish `creativity_engine` as an installable package
- **Web server** — FastAPI wrapper in `server.py` (future)
- **CLI** — Fully functional via `python -m creativity_engine`

Version in `pyproject.toml` is the source of truth. Tag releases as `vX.Y.Z` in git.

## Working Agreements

1. **Branch naming** — Feature branches are `feature/short-description`, bug fixes are `fix/issue-name`, documentation is `docs/topic`.
2. **Commit messages** — Imperative mood, first line ≤60 chars, wrap body at 72 chars. Reference issues.
3. **Code review** — All non-trivial PRs require review before merging.
4. **Do not** commit API keys, `.env` files, or model binaries.
5. **Do** add a `.gitignore` for `__pycache__/`, `*.pyc`, `.venv/`, `dist/`, `build/`, `.egg-info/`, and `.env`.

## Next Steps

1. Set up `pyproject.toml` with dependencies (requests, openai, anthropic, fastapi, pydantic)
2. Build `core/generator.py` with a skeleton `CreativityEngine` class
3. Implement one technique (e.g., SCAMPER) end-to-end
4. Write tests
5. Iterate

The bar for "done" is: a user can run `python -m creativity_engine generate --prompt "..."` and get back a novel, coherent creative output. Everything else is refinement.
