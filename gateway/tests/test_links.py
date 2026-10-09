import json

from sarjy_gateway.links import tour_links
from sarjy_gateway.messages import TourLink


def search(*tours: tuple[str, str | None]) -> str:
    return json.dumps(
        {
            "tours": [
                {"name": name, "type": "ticket", "slug": name.lower(), "price": "from AED 100", "accessible": False}
                | ({} if link is None else {"link": link})
                for name, link in tours
            ],
            "total": len(tours),
        }
    )


ABU_DHABI = search(
    ("Ferrari World Abu Dhabi Tickets", "https://me.example/ferrari"),
    ("Warner Bros. World Abu Dhabi Tickets", "https://me.example/warner"),
    ("TeamLab Phenomena Ticket", "https://me.example/teamlab"),
    ("Qasr Al Watan Tickets", "https://me.example/qasr"),
    ("Louvre Abu Dhabi Ticket", "https://me.example/louvre"),
)


def test_only_the_tours_a_reply_names_are_linked_in_the_order_it_names_them() -> None:
    reply = "TeamLab Phenomena starts from 55 dirhams, and Warner Bros. World from 345. Skip the Louvre."

    links = tour_links(reply, [ABU_DHABI])

    assert links == [
        TourLink(name="TeamLab Phenomena Ticket", url="https://me.example/teamlab"),
        TourLink(name="Warner Bros. World Abu Dhabi Tickets", url="https://me.example/warner"),
        TourLink(name="Louvre Abu Dhabi Ticket", url="https://me.example/louvre"),
    ]


def test_a_word_two_tours_share_does_not_name_either() -> None:
    # "World" alone would name Ferrari World too; two distinctive words are needed.
    links = tour_links("Warner Bros. World is a fun day out.", [ABU_DHABI])

    assert [link.name for link in links] == ["Warner Bros. World Abu Dhabi Tickets"]


def test_a_single_tour_from_get_tour_is_linked_too() -> None:
    detail = json.dumps(
        {"name": "Buggy Dune Bashing Tour", "link": "https://me.example/buggy", "price": "price on request"}
    )

    links = tour_links("The Buggy Dune Bashing Tour is price on request.", [detail])

    assert links == [TourLink(name="Buggy Dune Bashing Tour", url="https://me.example/buggy")]


def test_nothing_is_linked_without_a_link_or_from_other_tools() -> None:
    weather = json.dumps({"date": "2026-10-10", "high_c": 36})
    failure = json.dumps({"error": "SayTech is unavailable"})

    links = tour_links("The Aquarium is lovely.", [search(("Aquarium and Underwater Zoo", None)), weather, failure])

    assert links == []
