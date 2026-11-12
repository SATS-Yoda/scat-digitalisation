from dataclasses import dataclass

from .queries import plant_for


class Forbidden(Exception):
    pass


@dataclass(frozen=True)
class User:
    id: str
    plants: frozenset[str]


def current_user() -> User:
    """Stand-in until Entra sign-in (build order step 5) supplies the real user and groups."""
    return User(id="dev-user", plants=frozenset({"ICC1", "ICC2"}))


def require_plant(user: User, airline: str) -> None:
    plant = plant_for(airline)
    if plant not in user.plants:
        raise Forbidden(f"{airline} flights belong to {plant}, which this user cannot act on")
