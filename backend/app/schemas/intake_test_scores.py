"""Optional standardized test scores collected during intake (stored in profile.attributes)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator


class IntakeTestScores(BaseModel):
    """GMAT / GRE / EA / English scores — all optional except logical consistency via UI."""

    model_config = ConfigDict(extra="forbid")

    scores_not_final_yet: bool = False
    gmat_total: int | None = Field(default=None, ge=0, le=850)
    gre_verbal: int | None = Field(default=None, ge=0, le=180)
    gre_quant: int | None = Field(default=None, ge=0, le=180)
    ea_total: int | None = Field(default=None, ge=0, le=200)
    gre_waived: bool = False
    toefl_total: int | None = Field(default=None, ge=0, le=120)
    ielts_overall: float | None = Field(default=None, ge=0, le=9.5)
    native_english_speaker: bool | None = None

    @field_validator("ielts_overall")
    @classmethod
    def round_ielts(cls, v: float | None) -> float | None:
        if v is None:
            return None
        return round(float(v), 1)
