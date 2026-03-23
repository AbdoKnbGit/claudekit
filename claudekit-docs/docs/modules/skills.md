# Skills

**Module:** `claudekit.skills` · **Classes:** `Skill`, `SkillRegistry`, `SummarizerSkill`, `ClassifierSkill`, `DataExtractorSkill`, `CodeReviewerSkill`, `ResearcherSkill`

`claudekit.skills` provides `Skill` — a portable bundle of system prompt, model, tools, output validation, memory, and security. Skills are the primary unit of reuse and composition in claudekit.

## Skill

```python
from claudekit.skills import Skill

skill = Skill(
    name="summarizer",
    description="Summarize text to 1-2 sentences.",
    system="You are an expert summarizer. Be concise and accurate.",
    model="claude-haiku-4-5",
    tools=[],                          # list of @tool-decorated functions
    output_format=None,                # Pydantic model for structured output
    memory=None,                       # MemoryStore instance
    security=None,                     # SecurityLayer instance
    max_tokens=512,
)
```

### Constructor

```python
@dataclass
class Skill:
    name: str = ""
    description: str = ""
    system: str = ""
    model: str | None = None           # defaults to DEFAULT_FAST_MODEL
    tools: list = field(default_factory=list)
    output_format: type[BaseModel] | None = None
    memory: MemoryStore | None = None
    security: SecurityLayer | None = None
    max_tokens: int | None = None      # defaults to 4096
```

### run

`run` is an `async` method — must be awaited.

```python
result = await skill.run(
    input="The mitochondria is the powerhouse of the cell...",
    client=client,           # TrackedClient or AsyncTrackedClient
    context=None,            # optional dict for security checks
)
# Returns str, or a validated Pydantic model if output_format is set
```

**How it works:**
1. Builds `[{"role": "user", "content": input}]`.
2. Runs `security.check_request()` if security is attached.
3. Calls the client to create a message.
4. Runs `security.check_response()` if security is attached.
5. If `output_format` is set: strips markdown fences, validates JSON against the Pydantic model.
6. Returns the response text (or validated model).

### Structured output

```python
from pydantic import BaseModel

class Summary(BaseModel):
    title: str
    points: list[str]

skill = Skill(
    name="structured-summary",
    system="Reply with JSON only: {title: str, points: list[str]}",
    model="claude-haiku-4-5",
    output_format=Summary,
)
result = await skill.run(input="...", client=client)
result.title    # str
result.points   # list[str]
```

### to_agent

Convert a skill to an `Agent` definition:

```python
agent = skill.to_agent()
# Returns Agent(name="skill_summarizer", model=..., system=..., tools=..., ...)
```

### to_dict

```python
d = skill.to_dict()
# {"name": ..., "description": ..., "system": ..., "model": ..., "max_tokens": ...}
```

---

## SkillRegistry

Named skill lookup for dynamic composition.

```python
from claudekit.skills import Skill, SkillRegistry

registry = SkillRegistry()
registry.register(Skill(name="summarizer", system="Summarize."))
registry.register(Skill(name="classifier", system="Classify."))

skill = registry.get("summarizer")    # Skill | None
skills = registry.all()               # list[Skill]
registry.remove("summarizer")         # KeyError if not found
len(registry)                         # int
```

---

## Pre-built Skills

### SummarizerSkill

```python
from claudekit.skills import SummarizerSkill

skill = SummarizerSkill(
    style="bullet",      # "bullet" | "narrative" | "tldr"
    max_length=200,      # approximate character limit
    model="claude-haiku-4-5",
)
summary = await skill.run(input="Long text...", client=client)
# Returns str
```

### ClassifierSkill

```python
from claudekit.skills import ClassifierSkill

skill = ClassifierSkill(
    categories=["billing", "support", "sales"],
    multi_label=False,              # True: allow multiple categories
    confidence_threshold=0.7,       # minimum confidence to assign a label
    model="claude-haiku-4-5",
)
label = await skill.run(input="I need a refund", client=client)
# Returns str — one of the provided categories
```

### DataExtractorSkill

```python
from claudekit.skills import DataExtractorSkill
from pydantic import BaseModel

class Invoice(BaseModel):
    vendor: str
    amount: float
    date: str

skill = DataExtractorSkill(
    schema=Invoice,
    examples=[{"input": "...", "output": {...}}],   # optional few-shot examples
)
invoice = await skill.run(input="Invoice from Acme Corp, $1,200 on 2026-01-15", client=client)
invoice.vendor   # "Acme Corp"
invoice.amount   # 1200.0
```

### CodeReviewerSkill

```python
from claudekit.skills import CodeReviewerSkill, CodeReview

skill = CodeReviewerSkill(
    languages=["python", "typescript"],  # languages to focus on
    severity_threshold="medium",         # "low" | "medium" | "high"
    model="claude-sonnet-4-6",
)
review: CodeReview = await skill.run(input="def foo(): pass", client=client)
review.issues        # list[CodeReviewIssue]  — file, line, severity, message
review.suggestions   # list[CodeReviewSuggestion]
review.overall       # str — summary
```

### ResearcherSkill

```python
from claudekit.skills import ResearcherSkill, Research

skill = ResearcherSkill(
    depth="comprehensive",   # "quick" | "comprehensive"
    max_sources=5,
)
research: Research = await skill.run(input="Explain transformer attention", client=client)
research.findings       # list[ResearchFinding] — source, content, relevance
research.summary        # str
research.confidence     # float — 0..1
```
