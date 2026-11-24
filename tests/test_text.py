"""Tests for the pure text helpers: goodbyes, unfinished sentences, sentence splitting."""
import pytest

import jarvis


@pytest.mark.parametrize("text", [
    "Thank you.", "OK, thank you!", "Thanks Jarvis", "That's all.", "Goodbye",
    "Gracias", "Muchas gracias, Jarvis.", "Eso es todo", "Adiós",
])
def test_goodbyes(text):
    assert jarvis.is_goodbye(text)


@pytest.mark.parametrize("text", [
    "Thanks, now open Steam.", "What time is it?", "Gracias, ¿puedes abrir Firefox?",
    "Open the downloads folder.", "",
])
def test_not_goodbyes(text):
    assert not jarvis.is_goodbye(text)


@pytest.mark.parametrize("text", [
    "Open the folder and...", "Open the folder and", "I want it because.", "Um.",
    "Abre la carpeta y", "Busca el archivo porque", "Search for,",
])
def test_unfinished(text):
    assert jarvis.looks_unfinished(text)


@pytest.mark.parametrize("text", ["Open Firefox.", "What time is it?", "Abre Steam.", ""])
def test_finished(text):
    assert not jarvis.looks_unfinished(text)


def test_normalize():
    assert jarvis.normalize("¿Qué hora ES?") == "que hora es"
    assert jarvis.normalize("Adiós, ¡GRACIAS!").split() == ["adios", "gracias"]
    assert jarvis.normalize("That's all.") == "that's all"


@pytest.mark.parametrize("text, expected", [
    ("Hello there. How are you? Fine!", ["Hello there.", "How are you?", "Fine!"]),
    ('He said "hi." Then he left.', ['He said "hi."', "Then he left."]),
    ("It costs 3.5 dollars. OK.", ["It costs 3.5 dollars.", "OK."]),
    ("¡Hola! ¿Cómo estás?", ["¡Hola!", "¿Cómo estás?"]),
    ("No punctuation at all", ["No punctuation at all"]),
])
def test_sentences(text, expected):
    assert jarvis.Assistant._sentences(text) == expected


def test_sentence_stream_while_claude_writes():
    stream = jarvis.SentenceStream()
    assert stream.add("Hel") == []
    assert stream.add("lo there. How") == ["Hello there."]
    assert stream.add(" are you?\n\nFi") == ["How are you?"]
    assert stream.add("ne") == []
    assert stream.flush() == ["Fine"]
    assert stream.flush() == []
