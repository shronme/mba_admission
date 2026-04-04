/** Maps `grad_program_focus` slug to which score groups we emphasize (aligned with backend program types). */
export type IntakeScoreCategory = "mba" | "masters" | "phd" | "other";

export function intakeScoreCategory(gradProgramFocus: string): IntakeScoreCategory {
  if (
    gradProgramFocus === "mba_full_time" ||
    gradProgramFocus === "mba_part_time" ||
    gradProgramFocus === "executive_mba" ||
    gradProgramFocus === "online_mba" ||
    gradProgramFocus === "deferred_mba" ||
    gradProgramFocus === "dual_mba"
  ) {
    return "mba";
  }
  if (gradProgramFocus.startsWith("phd_")) {
    return "phd";
  }
  if (
    gradProgramFocus === "other_graduate" ||
    gradProgramFocus === "still_deciding" ||
    gradProgramFocus === "jd" ||
    gradProgramFocus === "md" ||
    gradProgramFocus === "llm" ||
    gradProgramFocus === "dental" ||
    gradProgramFocus === "pharmd" ||
    gradProgramFocus === "postbac_premed" ||
    gradProgramFocus === "bs_ba_undergraduate" ||
    gradProgramFocus === "transfer_undergraduate" ||
    gradProgramFocus === "other_undergraduate"
  ) {
    return "other";
  }
  return "masters";
}

export const INTAKE_SCORE_CATEGORY_HINT: Record<IntakeScoreCategory, string> = {
  mba: "MBA programs typically accept GMAT, GRE, or Executive Assessment (EA).",
  masters: "Many master’s programs use GRE; some also accept GMAT.",
  phd: "Doctoral programs often use GRE; some departments waive it.",
  other: "Enter any scores that apply to your program.",
};
