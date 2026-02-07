from __future__ import annotations

import random
from dataclasses import dataclass
import json
from pathlib import Path
from typing import List
from uuid import uuid4

from flask import Flask, redirect, render_template, request, session, url_for


@dataclass(frozen=True)
class Card:
    word: str
    taboo: List[str]


DATA_PATH = Path(__file__).with_name("cards.json")

DEFAULT_TIME_LIMIT = 60

GAME = {
    "players": [],
    "deck": [],
    "cards": [],
    "scores": {"red": 0, "blue": 0},
    "passes": 0,
    "turn_index": 0,
    "time_limit": DEFAULT_TIME_LIMIT,
    "started": False,
}


def load_cards() -> List[Card]:
    raw = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    cards: List[Card] = []
    for entry in raw:
        word = str(entry.get("word", "")).strip()
        taboo = [str(item).strip() for item in entry.get("taboo", []) if str(item).strip()]
        if word and taboo:
            cards.append(Card(word=word, taboo=taboo))
    return cards


def get_current_user():
    player_id = session.get("player_id")
    if not player_id:
        return None
    return next((p for p in GAME["players"] if p.get("id") == player_id), None)


def create_app() -> Flask:
    app = Flask(__name__)
    app.secret_key = "taboo-dev-secret"

    @app.route("/", methods=["GET"])
    def index():
        players = GAME["players"]
        error = session.pop("error", None)
        teams = {player.get("team") for player in players}
        can_start = len(players) >= 2 and {"red", "blue"}.issubset(teams)
        return render_template(
            "index.html",
            time_limit=GAME.get("time_limit", DEFAULT_TIME_LIMIT),
            players=players,
            can_start=can_start,
            error=error,
            current_user=get_current_user(),
            started=GAME["started"],
        )

    @app.route("/join", methods=["POST"])
    def join():
        if GAME["started"]:
            session["error"] = "Round already started. End round to join."
            return redirect(url_for("index"))
        name = request.form.get("name", "").strip()
        team = request.form.get("team", "").strip().lower()
        if not name or team not in {"red", "blue"}:
            session["error"] = "Enter a player name and choose a team."
            return redirect(url_for("index"))
        player = {"id": uuid4().hex, "name": name, "team": team}
        GAME["players"].append(player)
        session["player_id"] = player["id"]
        return redirect(url_for("index"))

    @app.route("/start", methods=["POST"])
    def start_game():
        players = GAME["players"]
        if len(players) < 2:
            session["error"] = "Add at least two players to start."
            return redirect(url_for("index"))
        teams = {player.get("team") for player in players}
        if not {"red", "blue"}.issubset(teams):
            session["error"] = "Add at least one player to each team."
            return redirect(url_for("index"))
        cards = load_cards()
        if not cards:
            session["error"] = "No cards available in cards.json."
            return redirect(url_for("index"))
        deck = [card.word for card in cards]
        random.shuffle(deck)
        GAME["deck"] = deck
        GAME["cards"] = [card.__dict__ for card in cards]
        GAME["scores"] = {"red": 0, "blue": 0}
        GAME["passes"] = 0
        GAME["turn_index"] = 0
        GAME["time_limit"] = int(request.form.get("time_limit", DEFAULT_TIME_LIMIT))
        GAME["started"] = True
        return redirect(url_for("game"))

    @app.route("/game", methods=["GET"])
    def game():
        if not GAME["started"]:
            return redirect(url_for("index"))
        players = GAME["players"]
        if not players:
            return redirect(url_for("index"))
        deck = GAME["deck"]
        if not deck:
            return redirect(url_for("index"))
        turn_index = GAME["turn_index"] % len(players)
        current_player = players[turn_index]
        opposite_team = "blue" if current_player["team"] == "red" else "red"
        current_user = get_current_user()
        can_view = False
        if current_user:
            can_view = (
                current_user.get("id") == current_player.get("id")
                or current_user.get("team") == opposite_team
            )
        current_word = deck[0]
        cards = GAME["cards"]
        card_data = next((c for c in cards if c.get("word") == current_word), None)
        card = Card(**card_data) if card_data else None
        return render_template(
            "game.html",
            card=card,
            scores=GAME.get("scores", {"red": 0, "blue": 0}),
            passes=GAME.get("passes", 0),
            time_limit=GAME.get("time_limit", DEFAULT_TIME_LIMIT),
            current_player=current_player,
            opposite_team=opposite_team,
            can_view=can_view,
            current_user=current_user,
        )

    @app.route("/action", methods=["POST"])
    def action():
        players = GAME["players"]
        if not players:
            return redirect(url_for("index"))
        deck = GAME["deck"]
        if not deck:
            return redirect(url_for("index"))
        action_type = request.form.get("action")
        turn_index = GAME["turn_index"] % len(players)
        current_player = players[turn_index]
        if session.get("player_id") != current_player.get("id"):
            return redirect(url_for("game"))
        team = current_player["team"]
        scores = GAME.get("scores", {"red": 0, "blue": 0})
        current = deck.pop(0)
        if action_type == "correct":
            scores[team] = scores.get(team, 0) + 1
        elif action_type == "taboo":
            scores[team] = max(0, scores.get(team, 0) - 1)
        elif action_type == "pass":
            GAME["passes"] = GAME.get("passes", 0) + 1
            deck.append(current)
        GAME["scores"] = scores
        GAME["deck"] = deck
        if not deck:
            return redirect(url_for("index"))
        return redirect(url_for("game"))

    @app.route("/turn/next", methods=["POST"])
    def next_turn():
        players = GAME["players"]
        if not players:
            return redirect(url_for("index"))
        turn_index = GAME["turn_index"] % len(players)
        current_player = players[turn_index]
        if session.get("player_id") != current_player.get("id"):
            return redirect(url_for("game"))
        GAME["turn_index"] = (GAME["turn_index"] + 1) % len(players)
        return redirect(url_for("game"))

    @app.route("/reset", methods=["POST"])
    def reset():
        GAME["players"] = []
        GAME["deck"] = []
        GAME["cards"] = []
        GAME["scores"] = {"red": 0, "blue": 0}
        GAME["passes"] = 0
        GAME["turn_index"] = 0
        GAME["time_limit"] = DEFAULT_TIME_LIMIT
        GAME["started"] = False
        session.clear()
        return redirect(url_for("index"))

    return app


app = create_app()


if __name__ == "__main__":
    app.run(debug=True)
