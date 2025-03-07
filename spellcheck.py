# -*- coding: utf-8 -*-
#
# Copyright © 2008 Jakub Jankowski <shasta@toxcorp.com>
# Copyright © 2012-2020 Jakub Wilk <jwilk@jwilk.net>
# Copyright © 2012 Gabriel Pettier <gabriel.pettier@gmail.com>
# 2025 Ported to WeeChat by yooz <yooz.public@gmail.com>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; version 2 dated June, 1991.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.

import weechat
import re
import enchant  # Używamy python-enchant zamiast Text::Aspell

SCRIPT_NAME = "spellcheck"
SCRIPT_AUTHOR = "Original by Jakub Wilk, Jakub Jankowski, Gabriel Pettier, Nei. Ported to WeeChat by yooz"
SCRIPT_VERSION = "0.1.0"
SCRIPT_LICENSE = "GPL2"
SCRIPT_DESC = "Checks for spelling errors using Enchant"

# Zmienne globalne
spellers = {}
suggestion_buffer = None

def spellcheck_setup(lang):
    """Inicjalizacja sprawdzania pisowni dla danego języka."""
    if lang in spellers:
        return spellers[lang]

    try:
        speller = enchant.Dict(lang)
        spellers[lang] = speller
        return speller
    except enchant.DictNotFoundError:
        weechat.prnt("", weechat.color("red") + f"Error while setting up spell-checker for {lang}" + weechat.color("reset"))
        return None

def spellcheck_check_word(langs, word, add_rest=False):
    """Sprawdzanie pisowni słowa w podanych językach."""
    prefix = ""
    suffix = ""

    # Pomiń sprawdzanie dla ścieżek, URL-i, emaili, liczb
    if not word or len(word) < 2:
        return None  # Zbyt krótkie słowo
    if word.startswith("/"):
        return None  # wygląda jak ścieżka
    if re.match(r"^\w+://", word):
        return None  # wygląda jak URL
    if re.match(r"^[^@]+@[^@]+$", word):
        return None  # wygląda jak email

    # Usuń znaki interpunkcyjne na początku
    match = re.match(r"^([^\w]*)(.*)", word)
    if match:
        if add_rest:
            prefix = match.group(1)
        word = match.group(2)

    # Usuń znaki interpunkcyjne na końcu
    match = re.match(r"(.*)([^\w]*)$", word)
    if match:
        word = match.group(1)
        if add_rest:
            suffix = match.group(2)

    # Jeśli po usunięciu znaków interpunkcyjnych nic nie zostało
    if not word or len(word) < 2:
        return None

    if re.match(r"^[\d\W]+$", word):
        return None  # wygląda jak liczba

    # Zapisz oryginalne słowo do celów debugowania
    orig_word = word

    # Podziel na listę języków
    try:
        langs_list = langs.split("+")
    except Exception as e:
        weechat.prnt("", weechat.color("red") + f"Error splitting languages: {e}" + weechat.color("reset"))
        langs_list = [langs]

    # Upewnij się, że mamy poprawne słowniki dla wszystkich języków
    for lang in langs_list:
        speller = spellcheck_setup(lang)
        if not speller:
            weechat.prnt("", weechat.color("red") + f"Error while setting up spell-checker for {lang}" + weechat.color("reset"))
            return None

    # Sprawdź pisownię w każdym języku
    results = []
    try:
        for lang in langs_list:
            speller = spellers[lang]
            try:
                if speller.check(word):
                    return None  # Słowo jest poprawne w co najmniej jednym języku
                else:
                    suggestions = speller.suggest(word)
                    results.extend([f"{prefix}{sugg}{suffix}" for sugg in suggestions])
            except Exception as e:
                weechat.prnt("", weechat.color("red") + f"Error checking word '{orig_word}' for {lang}: {e}" + weechat.color("reset"))
                return None
    except Exception as e:
        weechat.prnt("", weechat.color("red") + f"General error in spell checking: {e}" + weechat.color("reset"))
        return None

    return results

def find_language(buffer):
    """Znalezienie odpowiedniego języka dla bufora."""
    server = weechat.buffer_get_string(buffer, "localvar_server")
    channel = weechat.buffer_get_string(buffer, "localvar_channel")

    # Domyślny język, jeśli nie znaleziono specyficznego
    default_lang = weechat.config_get_plugin("default_language")

    if not server or not channel:
        return default_lang

    # Normalizacja nazwy kanału dla !kanałów
    if channel.startswith("!"):
        channel = "!" + channel[6:]

    # Konwersja na małe litery
    server = server.lower()
    channel = channel.lower()

    # Sprawdź ustawienia języków
    lang_settings = weechat.config_get_plugin("languages")
    languages = [lang.strip() for lang in lang_settings.split(",") if lang.strip()]

    for lang_str in languages:
        parts = lang_str.split("/")
        if len(parts) == 3:  # network/channel/lang
            net, chan, lang = parts
            if chan.lower() == channel and net.lower() == server:
                return lang
        elif len(parts) == 2:  # channel/lang
            chan, lang = parts
            if chan.lower() == channel:
                return lang

    return default_lang

def create_suggestion_buffer():
    """Utworzenie bufora dla sugestii pisowni."""
    global suggestion_buffer

    buffer_name = weechat.config_get_plugin("window_name")
    if not buffer_name:
        return None

    suggestion_buffer = weechat.buffer_search("python", buffer_name)
    if not suggestion_buffer:
        suggestion_buffer = weechat.buffer_new(buffer_name, "", "", "", "")
        if suggestion_buffer:
            weechat.buffer_set(suggestion_buffer, "title", "Spelling Suggestions")
            weechat.buffer_set(suggestion_buffer, "localvar_set_no_log", "1")
            weechat.buffer_set(suggestion_buffer, "display", "1")

            # Ustaw wysokość okna
            height = weechat.config_get_plugin("window_height")
            weechat.command("", f"/window splith {height}")

    return suggestion_buffer

def spellcheck_input_cb(data, modifier, buffer, string):
    """Obsługa wprowadzanego tekstu."""
    if weechat.config_get_plugin("enabled") != "1":
        return string

    # Sprawdź tylko gdy ostatni znak to spacja lub znak interpunkcyjny
    if not string or string[-1] not in " .?!":
        return string

    # Pomiń komendy (oprócz /say i /me)
    cmd_chars = weechat.config_string(weechat.config_get("weechat.look.command_chars"))
    if string.startswith(tuple(cmd_chars)) and not re.match(f"^[{re.escape(cmd_chars)}](say|me)\\s", string, re.I):
        return string

    # Rozdziel tekst na słowa i znajdź ostatnie
    words = re.findall(r'\S+', string)
    if not words:
        return string

    # Pobierz ostatnie słowo i jego pozycję
    last_word = words[-1]
    if last_word[-1] in ".?!":
        last_word = last_word[:-1]  # Usuń znak interpunkcyjny

    if not last_word:
        return string

    # Znajdź pozycję ostatniego słowa w tekście
    last_word_pos = string.rfind(last_word)
    if last_word_pos == -1:
        return string

    lang = find_language(buffer)
    if lang == "und":  # Nieokreślony język
        return string

    # Sprawdź czy słowo jest niepoprawne
    suggestions = spellcheck_check_word(lang, last_word)
    if not suggestions:
        return string

    # Słowo jest niepoprawne - podkreśl je kolorem
    word_color = weechat.config_get_plugin("word_color")
    if word_color:
        # Zastosuj kolorowanie bezpośrednio w tekście wejściowym
        # Używamy kodów kolorów WeeChat
        color_code = weechat.color(word_color)
        reset_code = weechat.color("reset")

        # Zbuduj nowy string z podkreślonym słowem
        result = string[:last_word_pos] + color_code + last_word + reset_code

        # Dodaj resztę tekstu jeśli istnieje
        if last_word_pos + len(last_word) < len(string):
            result += string[last_word_pos + len(last_word):]

        # Zamień string wejściowy na wersję z kolorami
        string = result

    return string

def spellcheck_input_return_cb(data, modifier, buffer, string):
    """Obsługa Enter - ukryj bufor sugestii."""
    global suggestion_buffer

    if suggestion_buffer:
        window_name = weechat.config_get_plugin("window_name")
        if window_name:
            weechat.command("", f"/window hide {window_name}")

    return string

def spellcheck_complete_cb(data, completion_item, buffer, completion):
    """Dodawanie sugestii pisowni do listy uzupełnień."""
    if weechat.config_get_plugin("enabled") != "1":
        return weechat.WEECHAT_RC_OK

    input_line = weechat.buffer_get_string(buffer, "input")
    input_pos = weechat.buffer_get_integer(buffer, "input_pos")

    # Znajdź słowo przed kursorem
    if input_pos <= 0 or not input_line:
        return weechat.WEECHAT_RC_OK

    word_start = input_line[:input_pos].rstrip().rfind(" ") + 1
    word = input_line[word_start:input_pos]

    if not word:
        return weechat.WEECHAT_RC_OK

    lang = find_language(buffer)
    if lang == "und":
        return weechat.WEECHAT_RC_OK

    suggestions = spellcheck_check_word(lang, word, True)
    if suggestions:
        for suggestion in suggestions:
            weechat.hook_completion_list_add(completion, suggestion, 0, weechat.WEECHAT_LIST_POS_SORT)

    return weechat.WEECHAT_RC_OK

def spellcheck_add_cb(data, buffer, args):
    """Dodawanie słów do osobistego słownika."""
    if not args:
        weechat.prnt(buffer, "SPELLCHECK_ADD <word>...    add word(s) to personal dictionary")
        return weechat.WEECHAT_RC_OK

    words = args.split()
    lang = find_language(buffer)

    speller = spellcheck_setup(lang)
    if not speller:
        return weechat.WEECHAT_RC_ERROR

    weechat.prnt(buffer, f"Adding to {lang} dictionary: {' '.join(words)}")
    for word in words:
        speller.add_to_pwl(word)

    # Uwaga: W Enchant nie ma bezpośredniego odpowiednika save_all_word_lists
    # Słowa są zazwyczaj zapisywane automatycznie

    return weechat.WEECHAT_RC_OK

def config_cb(data, option, value):
    """Obsługa zmian konfiguracji."""
    return weechat.WEECHAT_RC_OK

# Główna funkcja inicjalizująca skrypt
def init_script():
    if not weechat.register(SCRIPT_NAME, SCRIPT_AUTHOR, SCRIPT_VERSION, SCRIPT_LICENSE, SCRIPT_DESC, "", ""):
        return

    # Sprawdź czy moduł enchant jest zainstalowany
    try:
        import enchant
    except ImportError:
        weechat.prnt("", weechat.color("red") +
                    "Error: python-enchant module is not installed. Please install it with: pip install pyenchant" +
                    weechat.color("reset"))
        return

    # Ustawienia domyślne
    defaults = {
        "enabled": "1",
        "print_suggestions": "1",
        "default_language": "en_US",
        "languages": "",
        "word_color": "red",
        "word_input_color": "underline",
        "window_name": "",
        "window_height": "10"
    }

    for option, value in defaults.items():
        if not weechat.config_is_set_plugin(option):
            weechat.config_set_plugin(option, value)
            weechat.config_set_desc_plugin(option, f"Spellcheck: {option}")

    # Zarejestruj komendy
    weechat.hook_command(
        "spellcheck_add",
        "Add word(s) to personal dictionary",
        "<word>...",
        "word: word to add to personal dictionary",
        "",
        "spellcheck_add_cb",
        ""
    )

    # Zarejestruj hooki
    # Używamy "input_text_display" zamiast "input_text_display_with_cursor" dla lepszego kolorowania
    weechat.hook_modifier("input_text_display", "spellcheck_input_cb", "")
    weechat.hook_modifier("input_return", "spellcheck_input_return_cb", "")
    weechat.hook_completion("spellcheck_suggestions", "Spelling suggestions", "spellcheck_complete_cb", "")
    weechat.hook_config("plugins.var.python." + SCRIPT_NAME + ".*", "config_cb", "")

    # Wyświetl komunikat o pomyślnym załadowaniu
    weechat.prnt("", f"{SCRIPT_NAME} {SCRIPT_VERSION} loaded successfully. Use /set plugins.var.python.spellcheck.* to configure.")

if __name__ == "__main__":
    init_script()
