# -*- coding: utf-8 -*-
import weechat
import re
import enchant

###############################################################
#  Spellcheck Tab with Immediate Replacement on TAB
#  (TAB natychmiast podmienia słowo, a SPACJA zatwierdza i resetuje)
#  Version 1.0.0
###############################################################

SCRIPT_NAME = "spellcheck_tab"
SCRIPT_AUTHOR = "Optimized for multilingual support"
SCRIPT_VERSION = "1.0.0"
SCRIPT_LICENSE = "GPL2"
SCRIPT_DESC = (
    "Multilingual spellchecking with Tab suggestions (Enchant/Hunspell). "
    "TAB immediately overwrites the erroneous word with a suggestion (cycling through at most 5 suggestions), "
    "while SPACE adds a trailing space and resets the state."
)

# Globalne słowniki stanu
spellers = {}
last_suggestions = {}         # Sugestie ograniczone do maks. 5
current_suggestion_index = {}
last_word_position = {}        # Zapisuje (start_index, długość) błędnego słowa
suggestion_active = {}
languages = ["pl_PL", "en_US", "de_DE"]
original_word = {}            # Zapamiętuje oryginalne (błędne) słowo

def debug_log(message):
    if weechat.config_get_plugin("debug_mode") == "1":
        weechat.prnt("", f"DEBUG: {message}")

def get_speller(lang):
    """Zwraca obiekt speller dla danego języka (preferowany Hunspell, fallback Aspell)."""
    if lang not in spellers:
        try:
            broker = enchant.Broker()
            broker.set_ordering(lang, "hunspell,aspell")
            spellers[lang] = broker.request_dict(lang)
        except enchant.DictNotFoundError:
            weechat.prnt("", f"⚠️ Słownik nie znaleziony: {lang}")
            return None
    return spellers[lang]

def get_matching_nicks(buffer, word_prefix):
    """Zwraca listę nicków z kanału zaczynających się od podanego prefiksu."""
    matching_nicks = []
    
    # Pobierz nicklist dla danego buffera
    infolist = weechat.infolist_get("nicklist", buffer, "")
    if infolist:
        while weechat.infolist_next(infolist):
            # Sprawdź czy to nick (a nie grupa)
            if weechat.infolist_string(infolist, "type") == "nick":
                nick = weechat.infolist_string(infolist, "name")
                # Sprawdź czy nick zaczyna się od podanego prefiksu (case-insensitive)
                if nick.lower().startswith(word_prefix.lower()):
                    matching_nicks.append(nick)
        weechat.infolist_free(infolist)
    
    return matching_nicks

def check_word(word, buffer=None):
    """
    Sprawdza słowo we wszystkich skonfigurowanych językach.
    Zwraca listę maksymalnie 5 propozycji lub None, jeśli słowo jest poprawne/bez sugestii.
    """
    if len(word) < 2 or re.match(r"(^/|https?://|\S+@\S+|\d+)", word):
        return None

    # Najpierw sprawdzamy czy słowo jest poprawne w którymś z języków
    word_is_correct = False
    all_suggestions = []

    for lang in languages:
        speller = get_speller(lang)
        if not speller:
            continue
        if speller.check(word):
            word_is_correct = True
            break
        suggestions = speller.suggest(word)
        if suggestions:
            for s in suggestions:
                if s not in all_suggestions:
                    all_suggestions.append(s)
                if len(all_suggestions) >= 5:
                    break
        if len(all_suggestions) >= 5:
            break

    # Jeśli słowo jest poprawne lub nie ma sugestii słownikowych, kończymy
    if word_is_correct:
        return None
    
    # Jeśli słowo jest niepoprawne i jesteśmy na kanale, sprawdź pasujące nicki
    if buffer and not word_is_correct:
        buffer_type = weechat.buffer_get_string(buffer, "localvar_type")
        if buffer_type in ["channel", "private"]:
            matching_nicks = get_matching_nicks(buffer, word)
            # Dodaj pasujące nicki na początek sugestii
            if matching_nicks:
                all_suggestions = matching_nicks + all_suggestions
    
    return all_suggestions[:5] if all_suggestions else None

def find_word_at_cursor(text, cursor_pos):
    """
    Znajduje słowo znajdujące się bezpośrednio przed kursorem,
    zwraca (word, start_index, length).
    """
    if cursor_pos > len(text):
        cursor_pos = len(text)
    left_text = text[:cursor_pos]
    match = re.search(r'(\S+)$', left_text)
    if not match:
        return None, -1, 0
    word = match.group(1)
    word = re.sub(r"[.,!?]+$", "", word)
    word_start = match.start(1)
    word_length = len(word)
    return word, word_start, word_length

def input_modifier_cb(data, modifier, buffer, string):
    """
    Modyfikacja wyświetlania inputu.
      - Jeśli suggestion_active==True, wyświetlamy oryginalne błędne słowo
        i [sugestie] z aktualnie wybraną (podświetloną na magenta).
      - Jeśli suggestion_active==False, sprawdzamy bieżące słowo i generujemy sugestie.
    """
    if not string.strip():
        return string
        
    buffer_ptr = str(buffer)
    cursor_pos = weechat.buffer_get_integer(buffer, "input_pos")
    current_word, cur_start, cur_length = find_word_at_cursor(string, cursor_pos)
    
    # Jeśli nie znaleziono słowa pod kursorem
    if not current_word:
        return string

    # Jeśli mieliśmy stare dane słowa, ale user przeszedł do innego fragmentu → reset
    old_info = last_word_position.get(buffer_ptr)
    if old_info:
        old_start, old_length, old_word = old_info
        if (cur_start != old_start or cur_length != old_length):
            # Użytkownik przesunął się do innego słowa
            for dct in (
                last_suggestions,
                current_suggestion_index,
                last_word_position,
                original_word,
                suggestion_active
            ):
                dct.pop(buffer_ptr, None)

    if (suggestion_active.get(buffer_ptr, False)
        and buffer_ptr in original_word
        and buffer_ptr in last_suggestions
        and buffer_ptr in last_word_position):
        suggestions = last_suggestions[buffer_ptr]
        idx = current_suggestion_index.get(buffer_ptr, -1)
        orig_word = original_word[buffer_ptr]
        wstart, wlength, _ = last_word_position[buffer_ptr]

        color = weechat.color(weechat.config_get_plugin("word_color") or "red")
        highlighted_word = f"{color}{orig_word}{weechat.color('reset')}"
        visible_suggs = suggestions[:5]
        formatted_suggs = []
        for i, s in enumerate(visible_suggs):
            if i == idx:
                formatted_suggs.append(weechat.color("magenta") + s + weechat.color("reset"))
            else:
                formatted_suggs.append(s)
        bracket_text = " [" + ", ".join(formatted_suggs) + "]"
        new_string = (string[:wstart] +
                      highlighted_word +
                      bracket_text +
                      string[wstart + wlength:])
        return new_string
    else:
        # Sprawdź słowo i uzyskaj sugestie (najpierw spellcheck, potem nicki)
        suggestions = check_word(current_word, buffer)
        if not suggestions:
            # Brak sugestii -> wyczyść stare dane
            for dct in (last_suggestions, current_suggestion_index, last_word_position, original_word, suggestion_active):
                dct.pop(buffer_ptr, None)
            return string
            
        last_suggestions[buffer_ptr] = suggestions
        last_word_position[buffer_ptr] = (cur_start, cur_length, current_word)
        original_word[buffer_ptr] = current_word
        current_suggestion_index[buffer_ptr] = -1
        suggestion_active[buffer_ptr] = False
        
        # Podświetl błędne słowo
        color = weechat.color(weechat.config_get_plugin("word_color") or "red")
        highlighted_word = f"{color}{current_word}{weechat.color('reset')}"
        
        # Sugestie w nawiasach kwadratowych
        visible_suggs = suggestions[:5]
        bracket_text = " [" + ", ".join(visible_suggs) + "]"
        new_string = (string[:cur_start] +
                      highlighted_word +
                      bracket_text +
                      string[cur_start + cur_length:])
        return new_string

def tab_key_cb(data, buffer, command):
    """
    Obsługa TAB:
      - Zwiększa indeks aktualnej sugestii (iteruje tylko po dostępnych propozycjach).
      - Natychmiast podmienia błędne słowo w polu input na wybraną sugestię.
      - Aktualizuje last_word_position, aby nowy zakres odpowiadał długości wstawionego słowa.
    """
    buffer_ptr = str(buffer)
    
    if buffer_ptr not in last_suggestions or not last_suggestions[buffer_ptr]:
        return weechat.WEECHAT_RC_OK

    suggestions = last_suggestions[buffer_ptr]
    suggestion_active[buffer_ptr] = True

    if buffer_ptr not in current_suggestion_index:
        current_suggestion_index[buffer_ptr] = -1
    current_idx = current_suggestion_index[buffer_ptr]
    new_idx = (current_idx + 1) % len(suggestions)
    current_suggestion_index[buffer_ptr] = new_idx

    chosen = suggestions[new_idx]

    input_text = weechat.buffer_get_string(buffer, "input")
    if buffer_ptr not in last_word_position:
        return weechat.WEECHAT_RC_OK
        
    word_start, word_length, _ = last_word_position[buffer_ptr]
    new_input = input_text[:word_start] + chosen + input_text[word_start + word_length:]
    weechat.buffer_set(buffer, "input", new_input)
    weechat.buffer_set(buffer, "input_pos", str(word_start + len(chosen)))
    
    # Aktualizujemy zakres wybranego słowa, aby iteracje pracowały poprawnie:
    last_word_position[buffer_ptr] = (word_start, len(chosen), original_word[buffer_ptr])
    return weechat.WEECHAT_RC_OK_EAT

def space_key_cb(data, buffer, command):
    """
    Obsługa SPACJI:
      - Jeśli suggestion_active == True, SPACJA dodaje spację na końcu i resetuje stan.
      - Jeśli nie, działa normalnie (przekazuje spację do wejścia).
    """
    buffer_ptr = str(buffer)
    
    if not suggestion_active.get(buffer_ptr, False):
        return weechat.WEECHAT_RC_OK

    # Jeśli suggestion_active jest True, SPACJA dodaje spację i resetuje stan.
    input_text = weechat.buffer_get_string(buffer, "input")
    new_input = input_text + " "
    weechat.buffer_set(buffer, "input", new_input)
    weechat.buffer_set(buffer, "input_pos", str(len(input_text) + 1))
    
    for dct in (last_suggestions, current_suggestion_index, last_word_position, original_word, suggestion_active):
        dct.pop(buffer_ptr, None)
    return weechat.WEECHAT_RC_OK_EAT

def other_key_cb(data, buffer, command):
    """
    Obsługa innych klawiszy – resetuje stan, jeśli suggestion_active.
    """
    buffer_ptr = str(buffer)
    if not suggestion_active.get(buffer_ptr, False):
        return weechat.WEECHAT_RC_OK
        
    for dct in (last_suggestions, current_suggestion_index, last_word_position, original_word, suggestion_active):
        dct.pop(buffer_ptr, None)
    return weechat.WEECHAT_RC_OK

def main():
    if not weechat.register(SCRIPT_NAME, SCRIPT_AUTHOR, SCRIPT_VERSION, SCRIPT_LICENSE, SCRIPT_DESC, "", ""):
        return

    defaults = {
        "word_color": "red",
        "max_inline_suggestions": "5",
        "debug_mode": "0",
    }
    for option, value in defaults.items():
        if not weechat.config_is_set_plugin(option):
            weechat.config_set_plugin(option, value)

    weechat.hook_modifier("input_text_display", "input_modifier_cb", "")
    weechat.hook_command_run("/input complete_next", "tab_key_cb", "")
    weechat.hook_command_run("/input insert ' '", "space_key_cb", "")

    # Hooki dla innych klawiszy, które powinny resetować stan sugestii:
    weechat.hook_command_run("/input delete_*", "other_key_cb", "")
    weechat.hook_command_run("/input move_*", "other_key_cb", "")
    weechat.hook_command_run("/input history_*", "other_key_cb", "")
    weechat.hook_command_run("/input return", "other_key_cb", "")
    weechat.hook_command_run("/input search_*", "other_key_cb", "")
    weechat.hook_command_run("/input transpose_chars", "other_key_cb", "")
    weechat.hook_command_run("/input undo", "other_key_cb", "")
    weechat.hook_command_run("/input redo", "other_key_cb", "")

    weechat.prnt("", f"{SCRIPT_NAME} v{SCRIPT_VERSION} załadowany.")
    weechat.prnt("", "TAB: natychmiast podmienia błędne słowo na kolejną sugestię (max 5 propozycji).")
    weechat.prnt("", "SPACJA: dodaje spację i resetuje stan.")
    
if __name__ == "__main__":
    main()
