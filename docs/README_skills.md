# claudekit · skills

Reusable AI capability bundles. A **Skill** packages a system prompt, model choice, tools, output validation (Pydantic), memory, and security into a single portable unit.

**Source files:** `_skill.py`, `_registry.py`, `prebuilt/*`

---

## Core Concept

A `Skill` is a higher-level abstraction than a simple function call. It defines a "personality" or "expert" that can be used standalone or attached to an Agent.

### `Skill` (Base Class)
**Source:** `_skill.py:39`
The fundamental building block.

- **`run(input, client, context=None)`**: Executes the skill as a one-shot task. 
  - Automatically cleans markdown code fences from JSON responses.
  - Validates output against `output_format` (Pydantic) if provided.
  - Triggers pre/post security checks if a `SecurityLayer` is attached.
- **`to_agent()`**: Instantiates a full `Agent` based on the skill's configuration.

### `SkillRegistry`
**Source:** `_registry.py:30`
A centralised store for named skills, enabling discovery and dynamic loading.

---

## Prebuilt Skills

`claudekit` provides high-quality, production-ready skills for common LLM use cases.

### `ClassifierSkill`
**Source:** `prebuilt/_classifier.py:33`
Classifies text into a fixed set of categories.
- **Features:** Case-insensitive matching, whitespace stripping, and up to 2 automatic retries if the model hallucinates an invalid category.
- **Default Model:** Claude Haiku.

### `DataExtractorSkill`
**Source:** `prebuilt/_extractor.py:70`
Extracts structured data from unstructured prose.
- **Features:** Dynamic system prompt generation from Pydantic schemas, including field descriptions and JSON Schema requirements.
- **Default Model:** Claude Haiku.

### `SummarizerSkill`
**Source:** `prebuilt/_summarizer.py:45`
Flexible text summarisation.
- **Styles:** `bullet` (list), `paragraph` (prose), or `executive` (bottom-line up front).
- **Control:** `max_length` parameter to guide the model's verbosity.
- **Default Model:** Claude Haiku.

### `CodeReviewerSkill`
**Source:** `prebuilt/_reviewer.py:91`
Expert code analysis.
- **Output:** Returns a `CodeReview` object containing:
  - `issues`: List of problems with severity (`critical`, `warning`, `info`).
  - `suggestions`: Improvement advice with optional code snippets.
  - `rating`: 1-5 quality score.
  - `summary`: Prose overview.
- **Default Model:** Claude Sonnet.

### `ResearcherSkill`
**Source:** `prebuilt/_researcher.py:99`
Autonomous information gathering.
- **Features:** Automatically attaches the `web_search` tool. Collects claims, evidence, and source URLs.
- **Output:** Returns a `Research` object with structured findings and a deduplicated list of sources.
- **Default Model:** Claude Sonnet.

---

## Technical Considerations

1. **Markdown Stripping.** The `Skill.run()` method specifically handles cases where Claude wraps JSON in ` ```json ` blocks, ensuring `model_validate_json` does not fail.
2. **Security Context.** When calling `Skill.run()`, the `context` dictionary is passed to the `SecurityLayer`. Use this to propagate `user_id` or `request_id` for policy enforcement.
3. **Model Selection.** Prebuilt skills select their default model based on task complexity (Haiku for classification/extraction/summary, Sonnet for code review/research). This can be overridden during instantiation.
4. **Retry Logic.** `ClassifierSkill` is currently the only prebuilt skill with internal retry loops. For other skills, use standard `claudekit.client` retry policies.
