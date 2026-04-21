from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class SelectedSchool(BaseModel):
    """
    Confirmed school/program row.

    Mirrors the frontend contract and is stored under `profile.attributes.selected_schools`.
    """

    model_config = ConfigDict(extra="forbid")

    school: str = Field(..., min_length=1, max_length=256)
    program_slug: str = Field(..., min_length=1, max_length=128)
    program_display_name: str | None = Field(default=None, max_length=128)

    @field_validator("school", "program_slug")
    @classmethod
    def strip_non_empty(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("Must be non-empty")
        return s


class SchoolSelectionConfirmRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    selected_schools: list[SelectedSchool] = Field(..., max_length=10)

    @model_validator(mode="after")
    def dedupe_and_validate(self) -> "SchoolSelectionConfirmRequest":
        # Preserve order while deduping identical (school, program_slug) pairs.
        seen: set[tuple[str, str]] = set()
        out: list[SelectedSchool] = []
        for row in self.selected_schools:
            key = (row.school, row.program_slug)
            if key in seen:
                continue
            seen.add(key)
            out.append(row)
        self.selected_schools = out
        return self


class SchoolSelectionConfirmResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    selected_schools: list[SelectedSchool]
    stage: str = Field(..., description='Candidate stage after confirmation (expected "strategy").')

