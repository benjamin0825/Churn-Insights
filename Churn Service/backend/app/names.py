"""Display names for demo customers.

Demo data has no names, so each demo customer gets an invented one, derived from the customer id
so it never changes. Uploaded (real) data is never given invented names.
"""

from __future__ import annotations

FIRST = ["Sarah", "James", "Priya", "Tom", "Elena", "Anna", "Michael", "Aisha", "Daniel", "Sofia", "David", "Mei",
         "Lucas", "Fatima", "Noah", "Grace", "Ethan", "Hannah", "Mateo", "Olivia", "Arjun", "Chloe", "Ryan", "Isabella",
         "Kenji", "Amara", "Jonas", "Laura", "Omar", "Emma", "Leo", "Nina", "Samuel", "Zara", "Victor", "Julia", "Ben",
         "Maya", "Adam", "Lena", "Hugo", "Rosa", "Felix", "Ines", "Marcus", "Yuki", "Diego", "Clara", "Ali", "Ruth"]
LAST = ["Mitchell", "Carter", "Shah", "Becker", "Garcia", "Kowalski", "Brooks", "Rahman", "Novak", "Rossi", "Kim",
        "Lin", "Silva", "Haddad", "Williams", "Thompson", "Martin", "Okafor", "Patel", "Dubois", "O'Connor", "Watanabe",
        "Schmidt", "Nguyen", "Johnson", "Moreau", "Andersen", "Costa", "Fischer", "Murphy", "Ivanova", "Lopez", "Hughes",
        "Sato", "Bianchi", "Walker", "Jensen", "Romero", "Kaur", "Evans", "Petrov", "Clarke", "Mendes", "Hoffmann",
        "Reyes", "Larsen", "Ahmed", "Bennett", "Ortiz", "Young"]


def demo_name(customer_id: int) -> str:
    """A stable invented name for a demo customer."""
    h = (int(customer_id) * 2654435761 + 97) & 0xFFFFFFFF
    return f"{FIRST[h % len(FIRST)]} {LAST[(h // len(FIRST)) % len(LAST)]}"
