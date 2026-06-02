"""Craft: generate resume + cover letter for a qualifying role.

ADR-001 Tension 4: two backends.

* **Cowork (primary):** the SKILL.md pipeline invokes the resume-customizer skill
  directly, producing finished .docx/.pdf files. That path lives in the skill,
  not here.
* **CLI (secondary):** this module calls the Anthropic API with a simplified
  prompt and writes **markdown drafts**. Deliberately lower-fidelity — the full
  XML-editing pipeline requires Cowork's tooling.

In both cases the resulting file paths are recorded via the tracker so the data
contract is identical.
"""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path
from typing import Optional

from .config import Config
from .models import CraftedMaterial, Evaluation
from .tracker import save_materials


class CraftError(Exception):
    """Raised when material generation fails."""


def _slug(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", text).strip("_") or "role"


def build_resume_prompt(evaluation: Evaluation, config: Config, profile_narrative: str) -> str:
    return f"""Tailor a resume for this role using only true facts from the profile.
Return clean markdown. Mirror the JD's language where the profile genuinely supports it.

PROFILE (structured): {config.profile}
PROFILE (narrative): {profile_narrative or "(none)"}

ROLE: {evaluation.role} at {evaluation.company}
JOB DESCRIPTION:
\"\"\"{evaluation.raw_jd}\"\"\""""


def build_cover_letter_prompt(evaluation: Evaluation, config: Config, profile_narrative: str) -> str:
    return f"""Write a cover letter in the user's authentic voice for this role.
Specific, concise, no clichés or corporate filler. Return markdown.

PROFILE (narrative): {profile_narrative or "(none)"}
ROLE: {evaluation.role} at {evaluation.company}
JOB DESCRIPTION:
\"\"\"{evaluation.raw_jd}\"\"\""""


def craft_cli(
    evaluation: Evaluation,
    config: Config,
    *,
    app_id: int,
    out_dir: str | Path,
    profile_narrative: str = "",
    conn: Optional[sqlite3.Connection] = None,
    model: str = "claude-sonnet-4-5",
    api_key: Optional[str] = None,
) -> CraftedMaterial:
    """Generate markdown resume + cover letter drafts via the Anthropic API.

    Writes two files to ``out_dir`` named by company/role and, if ``conn`` is
    given, records their paths in ``crafted_materials``.
    """
    try:
        import anthropic
    except ImportError as exc:
        raise CraftError(
            "CLI crafting requires the anthropic SDK (`pip install applykit[standalone]`). "
            "For production-quality .docx output, use Cowork mode."
        ) from exc

    client = anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()

    def _generate(prompt: str) -> str:
        msg = client.messages.create(
            model=model, max_tokens=2000, messages=[{"role": "user", "content": prompt}]
        )
        return "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")

    resume_md = _generate(build_resume_prompt(evaluation, config, profile_narrative))
    cover_md = _generate(build_cover_letter_prompt(evaluation, config, profile_narrative))

    base = f"{_slug(evaluation.company)}_{_slug(evaluation.role)}"
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    resume_path = out / f"{base}_resume.md"
    cover_path = out / f"{base}_cover_letter.md"
    resume_path.write_text(resume_md, encoding="utf-8")
    cover_path.write_text(cover_md, encoding="utf-8")

    material = CraftedMaterial(
        app_id=app_id,
        resume_path=str(resume_path),
        cover_letter_path=str(cover_path),
    )
    if conn is not None:
        save_materials(conn, material)
    return material
