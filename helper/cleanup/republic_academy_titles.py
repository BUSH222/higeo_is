"""Turn the retired titles of the academies of the Soviet republics into "другое" (issue #87).

Each person who still has one of these titles is linked to the academy as an organization, the exact title is
appended to the comment and the title becomes ACADEMIC_DEGREE_OTHER. Running it again changes nothing.

    uv run python -m helper.cleanup.republic_academy_titles [--dry-run]


!!!! REMOVE IN MAIN


"""

import argparse

from sqlalchemy import select
from sqlalchemy.orm import Session

from helper import ACADEMIC_DEGREE_OTHER
from helper.db.initialise_database import Organization, OrganizationMembership, Person, engine

# retired title -> name of the academy's organization
RETIRED_TITLES = {
    "Действительный член АН АзСССР": "Академия наук Азербайджанской ССР",
    "Член-корреспондент АН Украинской ССР": "Академия наук Украинской ССР",
    "Член-корреспондент Академии наук Азербайджанской ССР": "Академия наук Азербайджанской ССР",
}


def migrate(session: Session) -> list[str]:
    """Apply the change to every matching person in the session; return a line describing each one."""
    report = []
    people = session.scalars(select(Person).where(Person.academic_degree.in_(RETIRED_TITLES)).order_by(Person.id))
    for person in people:
        title = person.academic_degree
        academy = session.scalars(select(Organization).where(Organization.name == RETIRED_TITLES[title])).one()
        linked = any(membership.organization_id == academy.id for membership in person.organizations)
        if not linked:
            session.add(OrganizationMembership(person=person, organization=academy))
        person.comment = f"{person.comment}\n<p>{title}</p>" if person.comment else f"<p>{title}</p>"
        person.academic_degree = ACADEMIC_DEGREE_OTHER
        action = "already linked to" if linked else "linked to"
        report.append(f"{person.id} {person}: {title!r} -> comment; {action} {academy.id} {academy.name}")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dry-run", action="store_true", help="Show what would change without saving it.")
    args = parser.parse_args()
    with Session(engine) as session:
        report = migrate(session)
        print("\n".join(report) or "Nothing to change.")
        if args.dry_run:
            session.rollback()
            print("Dry run: nothing saved.")
        else:
            session.commit()


if __name__ == "__main__":
    main()
