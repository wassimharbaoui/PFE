import os
import time
from typing import Tuple

import requests


OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")


class OllamaError(Exception):
    """Erreur lors de l'appel au serveur Ollama."""


def chat_with_model(
    model: str,
    system_prompt: str,
    user_content: str,
    temperature: float = 0.2,
    max_tokens: int | None = None,
) -> Tuple[str, float]:
    """Appelle un modèle Ollama en mode chat.

    Retourne (reponse_texte, duree_secondes).
    """

    url = f"{OLLAMA_URL.rstrip('/')}/api/chat"

    payload: dict = {
        "model": model,
        "stream": False,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
        "options": {
            "temperature": temperature,
        },
    }

    if max_tokens is not None:
        # num_predict limite le nombre de tokens générés
        payload["options"]["num_predict"] = max_tokens

    start = time.perf_counter()
    try:
        response = requests.post(url, json=payload, timeout=600)
    except requests.RequestException as exc:  # type: ignore[unreachable]
        raise OllamaError(f"Impossible de contacter Ollama sur {OLLAMA_URL}: {exc}") from exc

    duration = time.perf_counter() - start

    if not response.ok:
        raise OllamaError(f"Ollama a renvoyé le statut HTTP {response.status_code}")

    try:
        data = response.json()
    except ValueError as exc:  # JSONDecodeError hérite de ValueError
        raise OllamaError("Réponse JSON invalide renvoyée par Ollama") from exc

    message = data.get("message") or {}
    content = (message.get("content") or "").strip()

    # Certains modèles peuvent occasionnellement renvoyer une chaîne vide.
    # Dans ce cas, on renvoie un message explicite plutôt qu'une erreur brute.
    if not content:
        content = (
            "Le modèle n'a pas renvoyé de texte pour cette question. "
            "Vous pouvez réessayer ou comparer avec un autre modèle."
        )

    return content, duration
