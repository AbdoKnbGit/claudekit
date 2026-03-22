"""Comparison result from prompt A/B testing."""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class ComparisonResult:
    """Result of comparing multiple prompt versions across inputs.

    Attributes
    ----------
    versions:
        List of version identifiers that were compared.
    inputs:
        List of input strings used as test cases.
    outputs:
        Mapping of version → list of outputs (one per input).
    token_counts:
        Mapping of version → list of output token counts.
    costs:
        Mapping of version → total estimated cost.
    """

    versions: List[str] = field(default_factory=list)
    inputs: List[str] = field(default_factory=list)
    outputs: Dict[str, List[str]] = field(default_factory=dict)
    token_counts: Dict[str, List[int]] = field(default_factory=dict)
    costs: Dict[str, float] = field(default_factory=dict)

    def print(self) -> None:
        """Print a formatted comparison table to stdout."""
        header = ["Input"] + self.versions
        rows: list[list[str]] = []
        for i, inp in enumerate(self.inputs):
            row = [inp[:60]]
            for v in self.versions:
                out = self.outputs.get(v, [])
                row.append(out[i][:60] if i < len(out) else "")
            rows.append(row)

        # Column widths
        widths = [max(len(header[j]), *(len(r[j]) for r in rows)) for j in range(len(header))]
        fmt = " | ".join(f"{{:{w}}}" for w in widths)
        sep = "-+-".join("-" * w for w in widths)

        print(fmt.format(*header))
        print(sep)
        for row in rows:
            print(fmt.format(*row))

        print()
        for v in self.versions:
            print(f"  {v}: ${self.costs.get(v, 0):.4f}")

    def to_csv(self) -> str:
        """Export the comparison to CSV format.

        Returns:
            CSV string with headers and data rows.
        """
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(["Input"] + self.versions)
        for i, inp in enumerate(self.inputs):
            row = [inp]
            for v in self.versions:
                out = self.outputs.get(v, [])
                row.append(out[i] if i < len(out) else "")
            writer.writerow(row)
        return buf.getvalue()


__all__ = ["ComparisonResult"]
