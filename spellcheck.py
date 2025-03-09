# -*- coding: utf-8 -*-
#
# Copyright © 2008 Jakub Jankowski <shasta@toxcorp.com>
# Copyright © 2012-2020 Jakub Wilk <jwilk@jwilk.net>
# Copyright © 2012 Gabriel Pettier <gabriel.pettier@gmail.com>
# Ported to WeeChat by yooz <yooz.public@gmail.com>
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
import subprocess
import os
import tempfile

SCRIPT_NAME = "spellcheck"
SCRIPT_AUTHOR = "Original by Jakub Wilk, Jakub Jankowski, Gabriel Pettier, Nei. Ported to WeeChat by yooz"
SCRIPT_VERSION = "0.1.0"
SCRIPT_LICENSE = "GPL2"
SCRIPT_DESC = "Checks for spelling errors using Aspell"

# Zmienne globalne
spellers = {}
suggestion_buffer = None

def debug_print(message):
    """Funkcja pomocnicza do wyświetlania komunikatów debugowania."""
    if weechat.config_get_plugin("debug") == "1":
        weechat.prnt("", f"DEBUG: {message}")

def aspell_check_is_installed():
    """Sprawdzanie czy aspell jest zainstalowany w systemie."""
    try:
        result = subprocess.run(["aspell", "--version"], 
                             stdout=subprocess.PIPE, 
                             stderr=subprocess.PIPE, 
                             check=False)
        return result.returncode == 0
    except (subprocess.SubprocessError, FileNotFoundError):
        return False

def aspell_setup(lang):
    """Inicjalizacja sprawdzania pisowni dla danego języka."""
    if lang in spellers:
        return spellers[lang]
    
    # Sprawdź czy słownik językowy istnieje
    try:
        process = subprocess.run(
            ["aspell", "-d", lang, "dump", "config"], 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE, 
            text=True,
            check=False
        )
        if process.returncode != 0:
            weechat.prnt("", weechat.color("red") + f"Error: Language dictionary for {lang} not found" + weechat.color("reset"))
            return None
        
        # Zapisz informacje o konfiguracji spellera
        spellers[lang] = {
            'lang': lang
        }
        return spellers[lang]
    except subprocess.SubprocessError as e:
        weechat.prnt("", weechat.color("red") + f"Error setting up aspell for {lang}: {e}" + weechat.color("reset"))
        return None

def aspell_check_word(lang, word):
    """Sprawdza pisownię słowa używając Aspell poprzez plik tymczasowy dla większej niezawodności."""
    if not word or len(word) < 2:
        return True
    
    try:
        # Użyj pliku tymczasowego zamiast stdin, aby uniknąć problemów z buforowaniem
        with tempfile.NamedTemporaryFile(mode='w+', delete=False) as temp:
            temp.write(word + '\n')
            temp_path = temp.name
        
        # Uruchom aspell z plikiem wejściowym
        process = subprocess.run(
            ["aspell", "--lang="+lang, "list"],
            input=word + "\n",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False
        )
        
        # Wynik: jeśli słowo jest niepoprawne, aspell wypisuje je na stdout
        # Jeśli jest poprawne, aspell nie wypisuje nic
        result = process.stdout.strip()
        
        # Jeśli wynik jest pusty, słowo jest poprawne
        # Jeśli wynik zawiera słowo, słowo jest niepoprawne
        is_correct = not result
        
        if weechat.config_get_plugin("debug") == "1":
            debug_print(f"Checking word '{word}' in {lang}: {'correct' if is_correct else 'incorrect'}")
            if not is_correct:
                debug_print(f"Aspell output: '{result}'")
        
        return is_correct
    
    except Exception as e:
        weechat.prnt("", weechat.color("red") + f"Error checking word with aspell: {e}" + weechat.color("reset"))
        return True  # W razie błędu zakładamy, że słowo jest poprawne

def aspell_get_suggestions(lang, word):
    """Pobiera sugestie dla niepoprawnego słowa."""
    try:
        # Używamy 'pipe' mode z opcją -a
        process = subprocess.run(
            ["aspell", "-a", "-d", lang],
            input=f"{word}\n",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False
        )
        
        if process.returncode != 0:
            debug_print(f"Aspell error: {process.stderr}")
            return []
        
        output = process.stdout.strip().split("\n")
        
        # W trybie pipe, pierwsza linia to informacja o wersji
        # Druga linia zawiera wynik sprawdzania
        if len(output) > 1:
            result = output[1]
            if result.startswith("&"):
                # Format: "& word #count: sugg1, sugg2..."
                suggestions_part = result.split(":", 1)
                if len(suggestions_part) > 1:
                    suggestions = [s.strip() for s in suggestions_part[1].split(",")]
                    debug_print(f"Suggestions for '{word}': {suggestions}")
                    return suggestions
        
        debug_print(f"No suggestions for '{word}'")
        return []
    except Exception as e:
        weechat.prnt("", weechat.color("red") + f"Error getting suggestions with aspell: {e}" + weechat.color("reset"))
        return []

def aspell_add_word(lang, word):
    """Dodaje słowo do osobistego słownika aspell."""
    try:
        # Dodaj słowo za pomocą komendy osobistego słownika
        personal_path = os.path.expanduser(f"~/.aspell.{lang}.pws")
        
        # Sprawdź czy plik istnieje, jeśli nie - utwórz go
        if not os.path.exists(personal_path):
            with open(personal_path, 'w') as f:
                f.write(f"personal_ws-1.1 {lang} 0\n")
        
        # Odczytaj istniejące słowa
        with open(personal_path, 'r') as f:
            lines = f.readlines()
            
        # Sprawdź, czy słowo już istnieje
        words = [line.strip() for line in lines[1:] if line.strip()]
        if word in words:
            return True
        
        # Dodaj słowo do pliku
        with open(personal_path, 'a') as f:
            f.write(word + "\n")
        
        return True
    except Exception as e:
        weechat.prnt("", weechat.color("red") + f"Error adding word with aspell: {e}" + weechat.color("reset"))
        return False

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
    
    # Podziel na listę języków
    try:
        langs_list = langs.split("+")
    except Exception as e:
        debug_print(f"Error splitting languages: {e}")
        langs_list = [langs]
    
    # Upewnij się, że mamy poprawne słowniki dla wszystkich języków
    for lang in langs_list:
        speller = aspell_setup(lang)
        if not speller:
            weechat.prnt("", weechat.color("red") + f"Error while setting up aspell for {lang}" + weechat.color("reset"))
            return None
    
    # Sprawdź pisownię w każdym języku
    results = []
    for lang in langs_list:
        try:
            # Jeśli słowo jest poprawne w dowolnym języku, uznaj je za poprawne
            if aspell_check_word(lang, word):
                return None  # Słowo jest poprawne
            
            # Jeśli słowo jest niepoprawne, pobierz sugestie
            suggestions = aspell_get_suggestions(lang, word)
            if add_rest:
                results.extend([f"{prefix}{sugg}{suffix}" for sugg in suggestions])
            else:
                results.extend(suggestions)
        except Exception as e:
            debug_print(f"Error checking word '{word}' for {lang}: {e}")
    
    return results if results else []  # Zwróć listę sugestii lub pustą listę

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
    original_last_word = last_word  # Zachowaj oryginalne słowo do określenia pozycji
    
    # Usuń znak interpunkcyjny z końca słowa do sprawdzenia
    if last_word[-1] in ".?!":
        last_word = last_word[:-1]
    
    if not last_word:
        return string
    
    # Znajdź pozycję ostatniego słowa w tekście
    last_word_pos = string.rfind(original_last_word)
    if last_word_pos == -1:
        debug_print(f"Cannot find position of word: '{original_last_word}' in '{string}'")
        return string
    
    # Pobierz język dla bieżącego bufora
    lang = find_language(buffer)
    debug_print(f"Language for current buffer: {lang}")
    
    if lang == "und":  # Nieokreślony język
        return string
    
    # Sprawdź czy słowo jest niepoprawne i pobierz sugestie
    suggestions = spellcheck_check_word(lang, last_word)
    
    # Jeśli nie ma sugestii lub słowo jest poprawne, zwróć oryginalny string
    if suggestions is None:
        debug_print(f"Word '{last_word}' is correct or ignored")
        return string
    
    # Słowo jest niepoprawne - podkreśl je kolorem
    debug_print(f"Word '{last_word}' is incorrect. Suggestions: {suggestions}")
    
    word_color = weechat.config_get_plugin("word_color")
    if word_color:
        # Zastosuj kolorowanie bezpośrednio w tekście wejściowym
        color_code = weechat.color(word_color)
        reset_code = weechat.color("reset")
        
        # Zbuduj nowy string z podkreślonym słowem
        # Uwaga: zachowujemy znaki interpunkcyjne
        if original_last_word[-1] in ".?!" and len(original_last_word) > 1:
            # Podkreśl tylko część słowa bez znaku interpunkcyjnego
            punctuation = original_last_word[-1]
            colored_word = color_code + original_last_word[:-1] + reset_code + punctuation
        else:
            colored_word = color_code + original_last_word + reset_code
        
        # Zastąp oryginalne słowo kolorowanym
        result = string[:last_word_pos] + colored_word
        
        # Dodaj resztę tekstu jeśli istnieje
        if last_word_pos + len(original_last_word) < len(string):
            result += string[last_word_pos + len(original_last_word):]
        
        debug_print(f"Original string: '{string}'")
        debug_print(f"Colored string: '{result}'")
        
        # Zamień string wejściowy na wersję z kolorami
        return result
    
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
    if suggestions and len(suggestions) > 0:
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
    
    speller = aspell_setup(lang)
    if not speller:
        return weechat.WEECHAT_RC_ERROR
    
    weechat.prnt(buffer, f"Adding to {lang} dictionary: {' '.join(words)}")
    for word in words:
        success = aspell_add_word(lang, word)
        if not success:
            weechat.prnt(buffer, weechat.color("red") + f"Error adding word '{word}' to dictionary" + weechat.color("reset"))
    
    return weechat.WEECHAT_RC_OK

def spellcheck_show_suggestions_cb(data, buffer, args):
    """Wyświetla sugestie dla słowa podanego jako argument."""
    if not args:
        weechat.prnt(buffer, "Usage: /spellcheck_suggest <word>")
        return weechat.WEECHAT_RC_OK
    
    word = args.strip()
    lang = find_language(buffer)
    
    if lang == "und":
        weechat.prnt(buffer, "No language set for this buffer.")
        return weechat.WEECHAT_RC_OK
    
    is_correct = aspell_check_word(lang, word)
    
    if is_correct:
        weechat.prnt(buffer, f"Word '{word}' is spelled correctly.")
        return weechat.WEECHAT_RC_OK
    
    word_color = weechat.config_get_plugin("word_color")
    colored_word = f"{weechat.color(word_color)}{word}{weechat.color('reset')}"
    
    suggestions = aspell_get_suggestions(lang, word)
    
    if suggestions and len(suggestions) > 0:
        sugg_text = ", ".join(suggestions[:15])  # Ogranicz do 15 sugestii
        weechat.prnt(buffer, f"Suggestions for {colored_word} - {sugg_text}")
    else:
        weechat.prnt(buffer, f"No suggestions for {colored_word}")
    
    return weechat.WEECHAT_RC_OK

def config_cb(data, option, value):
    """Obsługa zmian konfiguracji."""
    return weechat.WEECHAT_RC_OK

# Główna funkcja inicjalizująca skrypt
def init_script():
    if not weechat.register(SCRIPT_NAME, SCRIPT_AUTHOR, SCRIPT_VERSION, SCRIPT_LICENSE, SCRIPT_DESC, "", ""):
        return
    
    # Sprawdź czy aspell jest zainstalowany
    if not aspell_check_is_installed():
        weechat.prnt("", weechat.color("red") + 
                    "Error: aspell is not installed on your system. Please install it first." + 
                    weechat.color("reset"))
        return
    
    # Ustawienia domyślne
    defaults = {
        "enabled": "1",
        "print_suggestions": "0",  # Domyślnie nie wyświetlaj sugestii
        "default_language": "en_US",
        "languages": "",
        "word_color": "red",
        "word_input_color": "underline",
        "window_name": "",
        "window_height": "10",
        "debug": "0"  # Dodatkowa opcja do debugowania
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
    
    # Dodaj komendę do wyświetlania sugestii
    weechat.hook_command(
        "spellcheck_suggest",
        "Show spelling suggestions for a word",
        "<word>",
        "word: word to check for spelling suggestions",
        "",
        "spellcheck_show_suggestions_cb",
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
