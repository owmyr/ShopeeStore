"""Migration script to update StoreLead themes in data/shopee.db.

Why: Historical store lead records had top_theme populated with a generic
placeholder ('camisetas estampadas'). This script updates all records using
the latest Trend Scout report clusters and keyword title heuristics.
"""

from sqlalchemy import func
from sqlmodel import select

from agents.lead_scout.agent import migrate_lead_themes
from core.db import session_scope
from core.models import StoreLead


def get_theme_breakdown() -> list[tuple[str | None, int]]:
    """Fetch current count of leads grouped by their top_theme."""
    with session_scope() as session:
        rows = session.exec(
            select(StoreLead.top_theme, func.count(StoreLead.id))
            .group_by(StoreLead.top_theme)
            .order_by(func.count(StoreLead.id).desc())
        ).all()
        return rows


def main() -> None:
    """Run StoreLead theme migration and log before/after distributions."""
    print("=== Starting StoreLead Theme Migration ===")

    print("\n--- Before Migration ---")
    before_breakdown = get_theme_breakdown()
    total_before = sum(count for _, count in before_breakdown)
    for theme, count in before_breakdown:
        print(f"  {theme or '<None>'}: {count}")
    print(f"Total leads: {total_before}")

    print("\nMigrating themes...")
    migrated = migrate_lead_themes()
    print(f"Updated {migrated} leads.")

    print("\n--- After Migration ---")
    after_breakdown = get_theme_breakdown()
    total_after = sum(count for _, count in after_breakdown)
    for theme, count in after_breakdown:
        print(f"  {theme or '<None>'}: {count}")
    print(f"Total leads: {total_after}")

    legacy_count = sum(
        count for theme, count in after_breakdown if theme == "camisetas estampadas"
    )
    if legacy_count > 0:
        print(f"\nWARNING: {legacy_count} leads still have 'camisetas estampadas'!")
    else:
        print("\nSUCCESS: No leads have 'camisetas estampadas'. Migration complete.")


if __name__ == "__main__":
    main()
