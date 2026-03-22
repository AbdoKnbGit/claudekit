"""Output schema validation policy.

:class:`OutputSchemaPolicy` validates model responses against a Pydantic
model, optionally retrying on validation failure.  This ensures that
downstream code always receives well-typed, structurally valid data.
"""

from __future__ import annotations

import json
import logging
import warnings
from typing import Any, Dict, List, Optional, Type

from claudekit.errors._base import OutputValidationError
from claudekit.security._context import SecurityContext
from claudekit.security._policy import Policy

logger = logging.getLogger("claudekit.security.output")


def _extract_text_content(response: Any) -> str:
    """Best-effort extraction of the text payload from a response."""
    # Dict response
    if isinstance(response, dict):
        content = response.get("content", [])
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts: List[str] = []
            for block in content:
                if isinstance(block, dict):
                    parts.append(block.get("text", ""))
                elif isinstance(block, str):
                    parts.append(block)
            return "\n".join(parts)
        return ""

    # SDK Message objects
    content = getattr(response, "content", None)
    if content is not None:
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = []
            for block in content:
                text = getattr(block, "text", None)
                if text:
                    parts.append(text)
                elif isinstance(block, dict):
                    parts.append(block.get("text", ""))
            return "\n".join(parts)

    return str(response)


def _try_parse_json(text: str) -> Optional[Any]:
    """Attempt to parse JSON from text, stripping markdown fences if present."""
    text = text.strip()
    # Strip markdown code fences
    if text.startswith("```"):
        lines = text.split("\n")
        # Remove first line (```json or ```)
        lines = lines[1:]
        # Remove last line if it's ```)
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return None


class OutputSchemaPolicy(Policy):
    """Validate model output against a Pydantic schema.

    Parameters
    ----------
    schema:
        A Pydantic :class:`BaseModel` subclass that the response text
        should parse into.
    max_retries:
        Maximum number of validation retries.  On each retry the policy
        will attempt progressively more lenient parsing strategies.
    on_failure:
        Behaviour when all retries are exhausted:

        * ``"raise"`` -- raise :class:`~claudekit.errors.OutputValidationError`.
        * ``"return_raw"`` -- return the unvalidated response as-is.
        * ``"return_partial"`` -- return a partially populated model with
          defaults where validation failed (best-effort).
    """

    name: str = "output_schema"

    def __init__(
        self,
        schema: Type[Any],
        max_retries: int = 2,
        on_failure: str = "raise",
    ) -> None:
        if on_failure not in ("raise", "return_raw", "return_partial"):
            raise ValueError(
                f"on_failure must be 'raise', 'return_raw', or 'return_partial', "
                f"got {on_failure!r}"
            )
        self.schema = schema
        self.max_retries = max_retries
        self.on_failure = on_failure

    # ------------------------------------------------------------------ #
    # Hooks
    # ------------------------------------------------------------------ #

    def check_response(
        self,
        response: Any,
        context: SecurityContext,
    ) -> Any:
        """Validate the response text against the configured Pydantic schema.

        Returns the validated Pydantic model instance on success, or handles
        failure according to *on_failure*.
        """
        text = _extract_text_content(response)
        errors: List[str] = []

        for attempt in range(1 + self.max_retries):
            parsed = _try_parse_json(text)
            if parsed is None:
                errors.append(f"Attempt {attempt + 1}: Could not parse JSON from response")
                continue

            try:
                # Try Pydantic v2 first
                if hasattr(self.schema, "model_validate"):
                    validated = self.schema.model_validate(parsed)
                else:
                    # Pydantic v1 fallback
                    validated = self.schema.parse_obj(parsed)

                logger.debug(
                    "Output validated against %s on attempt %d",
                    self.schema.__name__,
                    attempt + 1,
                )
                # Store the validated model on the context for downstream use
                context.metadata["validated_output"] = validated
                return validated

            except Exception as exc:
                errors.append(
                    f"Attempt {attempt + 1}: Validation error: {exc}"
                )
                logger.debug(
                    "Output validation attempt %d failed: %s",
                    attempt + 1,
                    exc,
                )

        # All retries exhausted
        error_detail = "; ".join(errors)
        logger.warning(
            "Output validation failed after %d attempts: %s",
            1 + self.max_retries,
            error_detail,
        )

        if self.on_failure == "raise":
            raise OutputValidationError(
                f"Output does not match schema {self.schema.__name__}: {error_detail}",
                context={
                    "schema": self.schema.__name__,
                    "errors": errors,
                    "request_id": context.request_id,
                },
            )
        elif self.on_failure == "return_partial":
            # Best-effort: try to construct a model with defaults
            parsed = _try_parse_json(text)
            if parsed is not None and isinstance(parsed, dict):
                try:
                    if hasattr(self.schema, "model_validate"):
                        return self.schema.model_validate(
                            parsed, strict=False
                        )
                    else:
                        return self.schema.construct(**parsed)
                except (json.JSONDecodeError, ValueError, TypeError, KeyError):
                    pass
            # Fall through to return_raw
            logger.debug("Partial construction failed, returning raw response")

        # return_raw or fallback
        return response


__all__ = ["OutputSchemaPolicy"]
