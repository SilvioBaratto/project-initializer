<%!
    # Everything below exists so a generated revision needs no editing before it
    # passes `ruff format` and the import-order check.
    FIRST_PARTY_ROOTS = ("alembic", "app")
    AUTOGENERATE_BANNER = "# ###"

    def literal(value):
        if value is None:
            return "None"
        if isinstance(value, (tuple, list)):
            items = [literal(item) for item in value]
            trailing_comma = "," if len(items) == 1 else ""
            return "(" + ", ".join(items) + trailing_comma + ")"
        return '"%s"' % value

    def import_blocks(extra_imports):
        lines = {"import sqlalchemy as sa", "from alembic import op"}
        lines.update(line for line in extra_imports.splitlines() if line.strip())
        def root(line):
            return line.split()[1].split(".")[0]
        def order(line):
            return (line.startswith("from "), line.split()[1])
        first_party = sorted((l for l in lines if root(l) in FIRST_PARTY_ROOTS), key=order)
        third_party = sorted((l for l in lines if root(l) not in FIRST_PARTY_ROOTS), key=order)
        return "\n\n".join(
            ["\n".join(block) for block in (["from collections.abc import Sequence"], third_party, first_party) if block]
        )

    def body(code):
        kept = [
            line for line in (code or "").splitlines()
            if not line.strip().startswith(AUTOGENERATE_BANNER)
        ]
        return "\n".join(kept).strip()
%>\
<%
    upgrade_body = body(context.get("upgrades"))
    downgrade_body = body(context.get("downgrades"))
%>\
"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}

"""

${import_blocks(context.get("imports") or "")}

# revision identifiers, used by Alembic.
revision: str = ${literal(up_revision)}
down_revision: str | Sequence[str] | None = ${literal(down_revision)}
branch_labels: str | Sequence[str] | None = ${literal(branch_labels)}
depends_on: str | Sequence[str] | None = ${literal(depends_on)}


def upgrade() -> None:
    """Upgrade schema."""
    ${upgrade_body if upgrade_body else "pass"}


def downgrade() -> None:
    """Downgrade schema."""
% if downgrade_body and downgrade_body != "pass":
    ${downgrade_body}
% else:
    raise NotImplementedError("This revision has no downgrade")
% endif
