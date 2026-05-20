from __future__ import annotations

import json
import re
from typing import Literal, Optional

from langchain_core.tools import tool
from pydantic import BaseModel, Field


class ClientInfo(BaseModel):
    """Structured client information collected by the intake flow."""

    nom_prenom: str = Field(..., min_length=1, description="Nom et prenom du client")
    motif_consultation: str = Field(
        ..., min_length=1, description="Motif de consultation"
    )
    preference_medecin: str = Field(
        ..., min_length=1, description="Preference de medecin"
    )
    email: str = Field(
        ...,
        min_length=3,
        pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$",
        description="Adresse email du client",
    )
    telephone: str = Field(
        ..., min_length=6, max_length=20, description="Numero de telephone"
    )
    preference_contact: Literal["mail", "sms"] = Field(
        ..., description="Preference de contact: mail ou sms"
    )
    numero_securite_sociale: str = Field(
        ..., min_length=13, max_length=15, description="Numero de securite sociale"
    )
    piece_jointe: Optional[str] = Field(
        default=None,
        description="Piece jointe ou chemin du document, optionnelle",
    )


class ClientInfoDraft(BaseModel):
    """Partial client information while the intake tool asks questions."""

    nom_prenom: Optional[str] = None
    motif_consultation: Optional[str] = None
    preference_medecin: Optional[str] = None
    email: Optional[str] = None
    telephone: Optional[str] = None
    preference_contact: Optional[Literal["mail", "sms"]] = None
    numero_securite_sociale: Optional[str] = None
    piece_jointe: Optional[str] = None


QUESTION_FLOW = [
    ("nom_prenom", "Quel est votre nom et prenom ?"),
    ("motif_consultation", "Quel est le motif de consultation ?"),
    ("preference_medecin", "Avez-vous une preference de medecin ?"),
    ("email", "Quelle est votre adresse email ?"),
    ("telephone", "Quel est votre numero de telephone ?"),
    (
        "preference_contact",
        "Quelle est votre preference de contact ? (mail ou sms)",
    ),
    (
        "numero_securite_sociale",
        "Quel est votre numero de securite sociale ?",
    ),
    (
        "piece_jointe",
        "Merci de fournir la piece jointe ou laissez vide si vous n'en avez pas.",
    ),
]


class ClientIntakeSession:
    """Stateful helper that asks one question at a time."""

    def __init__(self) -> None:
        self._draft = ClientInfoDraft()
        self._current_index = 0
        self._is_complete = False

    @property
    def current_field(self) -> Optional[str]:
        if self._is_complete or self._current_index >= len(QUESTION_FLOW):
            return None
        return QUESTION_FLOW[self._current_index][0]

    def _next_question(self) -> str:
        if self._current_index >= len(QUESTION_FLOW):
            self._is_complete = True
            validated = ClientInfo.model_validate(self._draft.model_dump())
            return json.dumps(validated.model_dump(), indent=2, ensure_ascii=False)
        return QUESTION_FLOW[self._current_index][1]

    def _store_answer(self, answer: str) -> Optional[str]:
        field_name = self.current_field
        if field_name is None:
            return None

        try:
            cleaned = answer.strip()
            if not cleaned:
                if field_name == "piece_jointe":
                    setattr(self._draft, field_name, None)
                    self._current_index += 1
                    return None
                raise ValueError(f"Le champ '{field_name}' ne peut pas etre vide.")

            if field_name == "email" and not re.match(
                r"^[^@\s]+@[^@\s]+\.[^@\s]+$", cleaned
            ):
                raise ValueError("Adresse email invalide.")

            if field_name == "telephone" and not re.match(
                r"^[0-9+\s().-]{6,20}$", cleaned
            ):
                raise ValueError("Numero de telephone invalide.")

            if field_name == "numero_securite_sociale" and not re.match(
                r"^\d{13,15}$", cleaned
            ):
                raise ValueError("Numero de securite sociale invalide.")

            if field_name == "preference_contact":
                cleaned = cleaned.lower()
                if cleaned not in {"mail", "sms"}:
                    raise ValueError("Preference de contact invalide: mail ou sms.")

            setattr(self._draft, field_name, cleaned)
            self._current_index += 1
            return None
        except Exception as exc:
            return str(exc)

    def step(self, answer: Optional[str] = None) -> str:
        """Advance the intake flow.

        Call once with no answer to receive the first question, then call again
        with each user answer to get the next question.
        """

        if self._is_complete:
            validated = ClientInfo.model_validate(self._draft.model_dump())
            return json.dumps(validated.model_dump(), indent=2, ensure_ascii=False)

        if answer is not None:
            error_message = self._store_answer(answer)
            if error_message:
                current_question = self._next_question()
                return (
                    f"Erreur de validation: {error_message}\n"
                    f"Merci de repondre a nouveau.\n{current_question}"
                )

        if self._current_index >= len(QUESTION_FLOW):
            self._is_complete = True
            validated = ClientInfo.model_validate(self._draft.model_dump())
            return json.dumps(validated.model_dump(), indent=2, ensure_ascii=False)

        return self._next_question()

    def reset(self) -> None:
        self._draft = ClientInfoDraft()
        self._current_index = 0
        self._is_complete = False


_client_intake_session = ClientIntakeSession()


@tool("collect_client_information")
def collect_client_information(answer: Optional[str] = None) -> str:
    """Collecte les informations client en posant les questions une par une.

    Appeler sans argument pour obtenir la premiere question.
    Appeler avec la reponse precedente pour obtenir la question suivante.
    Quand toutes les reponses sont collectees, le tool renvoie le JSON valide.
    """
    try:
        return _client_intake_session.step(answer)
    except Exception as exc:
        current_field = _client_intake_session.current_field
        if current_field is None:
            return f"Erreur inattendue pendant la collecte: {exc}"
        current_question = dict(QUESTION_FLOW).get(current_field, "")
        return (
            f"Erreur inattendue pendant la collecte: {exc}\n"
            f"Merci de repondre a nouveau.\n{current_question}"
        )


def reset_client_information() -> None:
    """Reset the shared intake session."""

    _client_intake_session.reset()


def ask_client_information() -> ClientInfo:
    """Interactive terminal helper for manual testing."""

    _client_intake_session.reset()
    question = _client_intake_session.step()
    while True:
        answer = input(f"{question}\n> ").strip()
        response = _client_intake_session.step(answer)
        if response.startswith("{"):
            return ClientInfo.model_validate_json(response)
        question = response
