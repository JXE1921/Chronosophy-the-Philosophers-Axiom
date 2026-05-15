"""
database.py — SQLite data layer for Philosopher Timeline.
Handles all persistence: CRUD for philosophers, quotes, and daily quote tracking.
"""

import sqlite3
import json
import os
import random
from datetime import date
from dataclasses import dataclass, field
from typing import Optional

# ─── Database path (sits next to the script) ────────────────────────────────
DB_PATH = os.path.join(os.path.dirname(__file__), "philosophers.db")


# ─── Data classes (shared across the app) ───────────────────────────────────

@dataclass
class Quote:
    id: int
    philosopher_id: int
    text: str


@dataclass
class Philosopher:
    id: int
    name: str
    birth_year: int
    death_year: Optional[int]          # None = still alive / unknown
    birth_city: str
    birth_country: str
    teachers: str                       # comma-separated names
    contributions: str                  # rich text / paragraph
    quotes: list[Quote] = field(default_factory=list)

    @property
    def lifespan_label(self) -> str:
        birth = str(self.birth_year) if self.birth_year >= 0 else f"{abs(self.birth_year)} BC"
        if self.death_year is None:
            return f"{birth} – ?"
        death = str(self.death_year) if self.death_year >= 0 else f"{abs(self.death_year)} BC"
        return f"{birth} – {death}"

    @property
    def era(self) -> str:
        """Bucket philosopher into a named era for display."""
        y = self.birth_year
        if y < -400:   return "Pre-Socratic"
        if y < 0:      return "Classical"
        if y < 500:    return "Hellenistic / Roman"
        if y < 1400:   return "Medieval"
        if y < 1650:   return "Renaissance"
        if y < 1800:   return "Early Modern"
        if y < 1900:   return "Modern"
        return "Contemporary"


# ─── Connection helper ───────────────────────────────────────────────────────

def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row          # access columns by name
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


# ─── Schema creation ─────────────────────────────────────────────────────────

def initialise_db() -> None:
    """Create tables if they don't exist and seed sample data on first run."""
    with _connect() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS philosophers (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                name          TEXT    NOT NULL,
                birth_year    INTEGER NOT NULL,
                death_year    INTEGER,
                birth_city    TEXT    NOT NULL DEFAULT '',
                birth_country TEXT    NOT NULL DEFAULT '',
                teachers      TEXT    NOT NULL DEFAULT '',
                contributions TEXT    NOT NULL DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS quotes (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                philosopher_id   INTEGER NOT NULL
                                    REFERENCES philosophers(id) ON DELETE CASCADE,
                text             TEXT    NOT NULL
            );

            CREATE TABLE IF NOT EXISTS daily_quote (
                id               INTEGER PRIMARY KEY CHECK (id = 1),
                quote_id         INTEGER NOT NULL,
                selected_on      TEXT    NOT NULL       -- ISO date string
            );
        """)

    # Seed sample data only on very first run (empty philosophers table)
    if not get_all_philosophers():
        _seed_sample_data()


# ─── CRUD — Philosophers ─────────────────────────────────────────────────────

def get_all_philosophers() -> list[Philosopher]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM philosophers ORDER BY birth_year"
        ).fetchall()
        result = []
        for r in rows:
            quotes = _get_quotes_for(conn, r["id"])
            result.append(_row_to_philosopher(r, quotes))
        return result


def get_philosopher(pid: int) -> Optional[Philosopher]:
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM philosophers WHERE id = ?", (pid,)
        ).fetchone()
        if not row:
            return None
        quotes = _get_quotes_for(conn, pid)
        return _row_to_philosopher(row, quotes)


def add_philosopher(p: Philosopher, quote_texts: list[str]) -> int:
    """Insert a philosopher + their quotes. Returns new ID."""
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO philosophers
                (name, birth_year, death_year, birth_city, birth_country, teachers, contributions)
                VALUES (?,?,?,?,?,?,?)""",
            (p.name, p.birth_year, p.death_year,
            p.birth_city, p.birth_country, p.teachers, p.contributions)
        )
        pid = cur.lastrowid
        for text in quote_texts:
            if text.strip():
                conn.execute(
                    "INSERT INTO quotes (philosopher_id, text) VALUES (?,?)",
                    (pid, text.strip())
                )
        return pid


def update_philosopher(p: Philosopher, quote_texts: list[str]) -> None:
    with _connect() as conn:
        conn.execute(
            """UPDATE philosophers SET
                name=?, birth_year=?, death_year=?, birth_city=?,
                birth_country=?, teachers=?, contributions=?
                WHERE id=?""",
            (p.name, p.birth_year, p.death_year, p.birth_city,
            p.birth_country, p.teachers, p.contributions, p.id)
        )
        # Replace all quotes for this philosopher
        conn.execute("DELETE FROM quotes WHERE philosopher_id=?", (p.id,))
        for text in quote_texts:
            if text.strip():
                conn.execute(
                    "INSERT INTO quotes (philosopher_id, text) VALUES (?,?)",
                    (p.id, text.strip())
                )


def delete_philosopher(pid: int) -> None:
    with _connect() as conn:
        conn.execute("DELETE FROM philosophers WHERE id=?", (pid,))


def search_philosophers(query: str, country: str = "",
                        era: str = "", sort: str = "birth_year") -> list[Philosopher]:
    """Flexible search/filter. Returns sorted list."""
    all_p = get_all_philosophers()
    q = query.lower().strip()
    result = []
    for p in all_p:
        if q and q not in p.name.lower():
            continue
        if country and country != "All" and p.birth_country != country:
            continue
        if era and era != "All" and p.era != era:
            continue
        result.append(p)

    if sort == "name":
        result.sort(key=lambda x: x.name)
    else:
        result.sort(key=lambda x: x.birth_year)
    return result


def get_all_countries() -> list[str]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT DISTINCT birth_country FROM philosophers ORDER BY birth_country"
        ).fetchall()
        return [r["birth_country"] for r in rows if r["birth_country"]]


# ─── Daily Quote ─────────────────────────────────────────────────────────────

def get_daily_quote() -> Optional[tuple[str, str]]:
    """
    Return (quote_text, philosopher_name).
    Selects a new random quote once per calendar day and caches it.
    """
    today = date.today().isoformat()
    with _connect() as conn:
        row = conn.execute("SELECT * FROM daily_quote WHERE id=1").fetchone()

        if row and row["selected_on"] == today:
            # Already selected today — fetch from DB
            qrow = conn.execute(
                """SELECT q.text, p.name FROM quotes q
                    JOIN philosophers p ON p.id = q.philosopher_id
                    WHERE q.id=?""", (row["quote_id"],)
            ).fetchone()
            if qrow:
                return qrow["text"], qrow["name"]

        # Select a new random quote
        all_quotes = conn.execute(
            """SELECT q.id, q.text, p.name FROM quotes q
                JOIN philosophers p ON p.id = q.philosopher_id"""
        ).fetchall()

        if not all_quotes:
            return None

        chosen = random.choice(all_quotes)
        conn.execute(
            """INSERT INTO daily_quote (id, quote_id, selected_on)
                VALUES (1, ?, ?)
                ON CONFLICT(id) DO UPDATE SET quote_id=excluded.quote_id,
                                            selected_on=excluded.selected_on""",
            (chosen["id"], today)
        )
        return chosen["text"], chosen["name"]


# ─── Internal helpers ─────────────────────────────────────────────────────────

def _get_quotes_for(conn: sqlite3.Connection, pid: int) -> list[Quote]:
    rows = conn.execute(
        "SELECT * FROM quotes WHERE philosopher_id=?", (pid,)
    ).fetchall()
    return [Quote(id=r["id"], philosopher_id=pid, text=r["text"]) for r in rows]


def _row_to_philosopher(row: sqlite3.Row, quotes: list[Quote]) -> Philosopher:
    return Philosopher(
        id=row["id"],
        name=row["name"],
        birth_year=row["birth_year"],
        death_year=row["death_year"],
        birth_city=row["birth_city"],
        birth_country=row["birth_country"],
        teachers=row["teachers"],
        contributions=row["contributions"],
        quotes=quotes,
    )


# ─── Seed data ────────────────────────────────────────────────────────────────

def _seed_sample_data() -> None:
    """Populate the database with 15 carefully chosen philosophers."""
    SEED = [
        dict(
            name="Socrates", birth_year=-470, death_year=-399,
            birth_city="Athens", birth_country="Greece",
            teachers="Diotima, Prodicus",
            contributions=(
                "Founder of Western philosophy's Socratic method. Championed "
                "the examined life, moral virtue, and dialectical inquiry. "
                "Influenced ethics and epistemology profoundly."
            ),
            quotes=[
                "The unexamined life is not worth living.",
                "I know that I know nothing.",
                "To find yourself, think for yourself.",
                "Wonder is the beginning of wisdom.",
            ]
        ),
        dict(
            name="Plato", birth_year=-428, death_year=-348,
            birth_city="Athens", birth_country="Greece",
            teachers="Socrates",
            contributions=(
                "Founded the Academy in Athens. Developed Theory of Forms, "
                "political philosophy in The Republic, and systematic epistemology. "
                "Established metaphysics as a discipline."
            ),
            quotes=[
                "Wise men speak because they have something to say; fools speak because they have to say something.",
                "At the touch of love, everyone becomes a poet.",
                "Reality is created by the mind; we can change our reality by changing our mind.",
            ]
        ),
        dict(
            name="Aristotle", birth_year=-384, death_year=-322,
            birth_city="Stagira", birth_country="Greece",
            teachers="Plato",
            contributions=(
                "Tutored Alexander the Great. Founded the Lyceum. Made foundational "
                "contributions to logic, ethics, metaphysics, biology, and politics. "
                "His works shaped Western thought for two millennia."
            ),
            quotes=[
                "We are what we repeatedly do. Excellence, then, is not an act, but a habit.",
                "It is the mark of an educated mind to be able to entertain a thought without accepting it.",
                "Happiness is the meaning and the purpose of life, the whole aim and end of human existence.",
            ]
        ),
        dict(
            name="Confucius", birth_year=-551, death_year=-479,
            birth_city="Qufu", birth_country="China",
            teachers="Unknown",
            contributions=(
                "Father of Confucianism. Emphasized moral rectitude, social harmony, "
                "filial piety, and ritual propriety. His Analects shaped Chinese, Korean, "
                "Japanese, and Vietnamese cultures."
            ),
            quotes=[
                "It does not matter how slowly you go as long as you do not stop.",
                "Everything has beauty, but not everyone sees it.",
                "The man who asks a question is a fool for a minute; the man who does not ask is a fool for life.",
                "Life is really simple, but we insist on making it complicated.",
            ]
        ),
        dict(
            name="Immanuel Kant", birth_year=1724, death_year=1804,
            birth_city="Königsberg", birth_country="Germany",
            teachers="Martin Knutzen",
            contributions=(
                "Synthesised rationalism and empiricism. Developed the Categorical "
                "Imperative as a basis for deontological ethics. His Critique of Pure "
                "Reason transformed epistemology."
            ),
            quotes=[
                "Act only according to that maxim whereby you can at the same time will that it should become a universal law.",
                "Science is organised knowledge. Wisdom is organised life.",
                "Two things fill the mind with ever new and increasing admiration: the starry heavens above and the moral law within.",
            ]
        ),
        dict(
            name="René Descartes", birth_year=1596, death_year=1650,
            birth_city="La Haye en Touraine", birth_country="France",
            teachers="Franciscus Burgersdijk",
            contributions=(
                "Father of modern philosophy. Coined 'Cogito, ergo sum'. "
                "Developed mind-body dualism and the method of radical doubt. "
                "Founded analytic geometry."
            ),
            quotes=[
                "I think, therefore I am.",
                "The reading of all good books is like conversation with the finest men of past centuries.",
                "It is not enough to have a good mind; the main thing is to use it well.",
            ]
        ),
        dict(
            name="Friedrich Nietzsche", birth_year=1844, death_year=1900,
            birth_city="Röcken", birth_country="Germany",
            teachers="Arthur Schopenhauer (self-taught)",
            contributions=(
                "Developed concepts of the Übermensch, will to power, and eternal recurrence. "
                "Critiqued morality, religion, and modernity. "
                "Influenced existentialism, postmodernism, and continental philosophy."
            ),
            quotes=[
                "That which does not kill us, makes us stronger.",
                "Without music, life would be a mistake.",
                "He who has a why to live can bear almost any how.",
                "In individuals, insanity is rare; but in groups, parties, nations and epochs, it is the rule.",
            ]
        ),
        dict(
            name="John Locke", birth_year=1632, death_year=1704,
            birth_city="Wrington", birth_country="England",
            teachers="Richard Lower",
            contributions=(
                "Father of liberalism. Developed social contract theory, natural rights "
                "(life, liberty, property), and influenced the US Declaration of Independence. "
                "Foundational figure in empiricism."
            ),
            quotes=[
                "The mind is furnished with ideas by experience alone.",
                "Reading furnishes the mind only with materials of knowledge; it is thinking that makes what we read ours.",
                "New opinions are always suspected, and usually opposed, without any other reason but because they are not already common.",
            ]
        ),
        dict(
            name="Simone de Beauvoir", birth_year=1908, death_year=1986,
            birth_city="Paris", birth_country="France",
            teachers="Jean-Paul Sartre",
            contributions=(
                "Pioneered existentialist feminism. 'The Second Sex' became a foundational "
                "feminist text. Explored ethics of ambiguity and freedom as existential projects."
            ),
            quotes=[
                "One is not born, but rather becomes, a woman.",
                "I am too intelligent, too demanding, and too resourceful for anyone to be able to take charge of me entirely.",
                "Change your life today. Don't gamble on the future; act now, without delay.",
            ]
        ),
        dict(
            name="Ibn Rushd (Averroes)", birth_year=1126, death_year=1198,
            birth_city="Córdoba", birth_country="Spain",
            teachers="Ibn Tufayl",
            contributions=(
                "Greatest medieval Islamic philosopher. His commentaries on Aristotle "
                "reintroduced Greek philosophy to medieval Europe. Advocated harmony "
                "between reason and religious faith."
            ),
            quotes=[
                "Ignorance leads to fear, fear leads to hatred, and hatred leads to violence.",
                "Knowledge is the conformity of the object and the intellect.",
            ]
        ),
        dict(
            name="Baruch Spinoza", birth_year=1632, death_year=1677,
            birth_city="Amsterdam", birth_country="Netherlands",
            teachers="Francis van den Enden",
            contributions=(
                "Radical rationalist and pantheist. His Ethics presented philosophy "
                "in geometric form. Advocated freedom of thought, separation of church "
                "and state, and democratic governance."
            ),
            quotes=[
                "The highest activity a human being can attain is learning for understanding.",
                "Do not weep. Do not wax indignant. Understand.",
                "Peace is not the absence of war; it is a virtue, a state of mind.",
            ]
        ),
        dict(
            name="Jean-Paul Sartre", birth_year=1905, death_year=1980,
            birth_city="Paris", birth_country="France",
            teachers="Edmund Husserl, Martin Heidegger",
            contributions=(
                "Leader of existentialism. 'Existence precedes essence' defined his "
                "philosophy of radical freedom and responsibility. Nobel Prize in "
                "Literature (declined). Key works: Being and Nothingness, No Exit."
            ),
            quotes=[
                "Existence precedes essence.",
                "Hell is other people.",
                "Freedom is what you do with what's been done to you.",
                "Life begins on the other side of despair.",
            ]
        ),
        dict(
            name="Mary Wollstonecraft", birth_year=1759, death_year=1797,
            birth_city="London", birth_country="England",
            teachers="Richard Price",
            contributions=(
                "Pioneer of feminist philosophy. 'A Vindication of the Rights of Woman' "
                "argued for women's equal education and citizenship. "
                "Foundational figure in liberal feminism."
            ),
            quotes=[
                "I do not wish women to have power over men, but over themselves.",
                "Virtue can only flourish among equals.",
                "The beginning is always today.",
            ]
        ),
        dict(
            name="Laozi", birth_year=-601, death_year=-531,
            birth_city="Ku County", birth_country="China",
            teachers="Unknown",
            contributions=(
                "Founder of Taoism. The Tao Te Ching is one of the most translated "
                "works in history. Championed simplicity, naturalness, and non-action (wu wei) "
                "as the path to harmony."
            ),
            quotes=[
                "The journey of a thousand miles begins with a single step.",
                "Knowing others is wisdom; knowing yourself is enlightenment.",
                "Nature does not hurry, yet everything is accomplished.",
                "To the mind that is still, the whole universe surrenders.",
            ]
        ),
        dict(
            name="David Hume", birth_year=1711, death_year=1776,
            birth_city="Edinburgh", birth_country="Scotland",
            teachers="Francis Hutcheson",
            contributions=(
                "Radical empiricist and sceptic. Challenged causation, personal identity, "
                "and religious argument. Influenced Kant, utilitarianism, and analytic philosophy. "
                "Key works: A Treatise of Human Nature."
            ),
            quotes=[
                "Reason is the slave of the passions.",
                "Beauty in things exists in the mind which contemplates them.",
                "Custom is the great guide of human life.",
            ]
        ),
    ]

    for d in SEED:
        quotes = d.pop("quotes")
        p = Philosopher(id=0, **d)
        add_philosopher(p, quotes)
