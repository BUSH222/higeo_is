"""The titles of the academies of the Soviet republics became "другое" (issue #87)."""

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from helper import ACADEMIC_DEGREE_OTHER, ACADEMIC_DEGREE_TO_LIST, MULTIPLE_CHOICE_FIELDS
from helper.cleanup.republic_academy_titles import migrate
from helper.db import initialise_database as db


@pytest.mark.parametrize(
    "list_type",
    ["acad_full_members_azssr", "acad_corresponding_members_uassr", "acad_corresponding_members_azssr"],
)
def test_republic_lists_are_gone(client, list_type):
    assert client.get(f"/list_custom?type={list_type}").status_code == 404


def test_other_is_a_choice_without_a_list():
    assert MULTIPLE_CHOICE_FIELDS["academic_degree"][-1] == ACADEMIC_DEGREE_OTHER
    assert ACADEMIC_DEGREE_OTHER not in ACADEMIC_DEGREE_TO_LIST


def test_migrate_moves_the_title_to_the_comment_and_links_the_academy():
    with Session(db.engine) as session:
        azssr = db.Organization(name="Академия наук Азербайджанской ССР", org_type="Академии")
        ussr_ua = db.Organization(name="Академия наук Украинской ССР", org_type="Академии")
        linked = db.Person(surname="Султанов", name="Азаль", academic_degree="Действительный член АН АзСССР")
        unlinked = db.Person(
            surname="Новик",
            name="Екатерина",
            academic_degree="Член-корреспондент АН Украинской ССР",
            comment="<p>x</p>",
        )
        session.add_all([azssr, ussr_ua, linked, unlinked])
        session.flush()
        session.add(db.OrganizationMembership(person_id=linked.id, organization_id=azssr.id))
        session.flush()

        assert len(migrate(session)) == 2
        session.flush()

        assert linked.academic_degree == unlinked.academic_degree == ACADEMIC_DEGREE_OTHER
        assert linked.comment == "<p>Действительный член АН АзСССР</p>"
        assert unlinked.comment == "<p>x</p>\n<p>Член-корреспондент АН Украинской ССР</p>"
        memberships = session.scalars(
            select(db.OrganizationMembership.organization_id).where(
                db.OrganizationMembership.person_id.in_([linked.id, unlinked.id])
            )
        ).all()
        assert sorted(memberships) == sorted([azssr.id, ussr_ua.id])  # no duplicate link for the linked one
        assert migrate(session) == []  # running it again changes nothing
        session.rollback()
