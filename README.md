# WeeChat Spellcheck with Tab Suggestions (spellcheck_tab.by)

A multilingual spellchecking plugin for WeeChat that provides tab-navigable suggestions and supports both dictionary-based corrections and channel nickname completions.

## Features

- Real-time spellchecking with Enchant/Hunspell
- Multilingual support (configured for Polish, English and German by default)
- Tab-based navigation through suggestions
- Shows up to 5 suggestions in a nicely formatted interface 
- Highlights erroneous words in red
- Highlights currently selected suggestion in magenta
- Automatically includes matching nicknames from channels as suggestions
- Uses Space to confirm the selected suggestion and reset state

## Installation

### Prerequisites

1. You need Python 3 and WeeChat
2. You need the `pyenchant` library, which can be installed via:
   ```
   pip install pyenchant
   ```
3. You need dictionaries for the languages you want to use (Hunspell or Aspell)
   - On Debian/Ubuntu: `sudo apt-get install hunspell-en-us hunspell-pl hunspell-de-de`
   - On Fedora: `sudo dnf install hunspell-en hunspell-pl hunspell-de`
   - On macOS with Homebrew: `brew install hunspell && brew install --cask hunspell-dictionaries`

### Installation Steps

1. Create Python scripts directory if it doesn't exist:
   ```
   mkdir -p ~/.local/share/weechat/python
   ```

2. Download the script to WeeChat's Python scripts directory:
   ```
   cd ~/.local/share/weechat/python
   curl -O https://raw.githubusercontent.com/your-username/weechat-spellcheck-tab/master/spellcheck_tab.py
   ```

3. Load the script in WeeChat:
   ```
   /script load spellcheck_tab.py
   ```

4. To autoload the script when WeeChat starts:
   ```
   ln -s ~/.local/share/weechat/python/spellcheck_tab.py ~/.local/share/weechat/python/autoload/
   ```

## Usage

1. Type in WeeChat normally. Misspelled words will be highlighted in red, with suggestions in brackets.
2. Press Tab to cycle through suggestions (up to 5 suggestions will be shown).
3. The currently selected suggestion will be highlighted in magenta and automatically replace the misspelled word.
4. Press Space to confirm the selected suggestion and continue typing.
5. Any other key press will cancel the suggestion mode.

If you're in a channel and type an incorrect word, the plugin will:
1. First check if it's misspelled according to the configured dictionaries
2. If it's misspelled, check if it could be the beginning of someone's nickname in the channel
3. Show both matching nicknames and dictionary suggestions (with nicknames listed first)

## Configuration

You can set the following options:

```
/set plugins.var.python.spellcheck_tab.word_color "red"
/set plugins.var.python.spellcheck_tab.max_inline_suggestions "5"
/set plugins.var.python.spellcheck_tab.debug_mode "0"
```

To modify the languages used, edit the script directly and change the `languages` list.

## License

GPL v2

---

# WeeChat Spellcheck z propozycjami pod klawiszem Tab (spellcheck_tab.py)

Plugin dla WeeChat oferujący podpowiedzi pisowni z możliwością nawigacji klawiszem Tab, obsługujący zarówno korekty słownikowe, jak i uzupełnianie nicków z kanału.

## Funkcje

- Sprawdzanie pisowni w czasie rzeczywistym przy użyciu Enchant/Hunspell
- Obsługa wielu języków (domyślnie skonfigurowany dla polskiego, angielskiego i niemieckiego)
- Nawigacja po propozycjach za pomocą klawisza Tab
- Wyświetla do 5 propozycji w czytelnym formacie
- Podświetla błędne słowa na czerwono
- Podświetla aktualnie wybraną propozycję na kolor magenta
- Automatycznie uwzględnia pasujące nicki z kanału jako propozycje
- Używa klawisza Spacja do zatwierdzenia wybranej propozycji i resetowania stanu

## Instalacja

### Wymagania wstępne

1. Potrzebujesz Python 3 i WeeChat
2. Potrzebujesz biblioteki `pyenchant`, którą można zainstalować za pomocą:
   ```
   pip install pyenchant
   ```
3. Potrzebujesz słowników dla języków, które chcesz używać (Hunspell lub Aspell)
   - Na Debian/Ubuntu: `sudo apt-get install hunspell-en-us hunspell-pl hunspell-de-de`
   - Na Fedora: `sudo dnf install hunspell-en hunspell-pl hunspell-de`
   - Na macOS z Homebrew: `brew install hunspell && brew install --cask hunspell-dictionaries`

### Kroki instalacji

1. Utwórz katalog skryptów Python, jeśli nie istnieje:
   ```
   mkdir -p ~/.local/share/weechat/python
   ```

2. Pobierz skrypt do katalogu skryptów Python WeeChat:
   ```
   cd ~/.local/share/weechat/python
   curl -O https://raw.githubusercontent.com/your-username/weechat-spellcheck-tab/master/spellcheck_tab.py
   ```

3. Załaduj skrypt w WeeChat:
   ```
   /script load spellcheck_tab.py
   ```

4. Aby automatycznie ładować skrypt przy starcie WeeChat:
   ```
   ln -s ~/.local/share/weechat/python/spellcheck_tab.py ~/.local/share/weechat/python/autoload/
   ```

## Użytkowanie

1. Pisz w WeeChat normalnie. Błędnie napisane słowa będą podświetlone na czerwono, z propozycjami w nawiasach.
2. Naciśnij Tab, aby przełączać się między propozycjami (wyświetlonych zostanie maksymalnie 5 propozycji).
3. Aktualnie wybrana propozycja będzie podświetlona na kolor magenta i automatycznie zastąpi błędnie napisane słowo.
4. Naciśnij Spację, aby zatwierdzić wybraną propozycję i kontynuować pisanie.
5. Naciśnięcie dowolnego innego klawisza anuluje tryb propozycji.

Jeśli jesteś na kanale i wpiszesz niepoprawne słowo, plugin:
1. Najpierw sprawdzi, czy jest błędnie napisane według skonfigurowanych słowników
2. Jeśli jest błędnie napisane, sprawdzi, czy może być początkiem czyjegoś nicka na kanale
3. Pokaże zarówno pasujące nicki, jak i propozycje słownikowe (z nickami na początku listy)

## Konfiguracja

Możesz ustawić następujące opcje:

```
/set plugins.var.python.spellcheck_tab.word_color "red"
/set plugins.var.python.spellcheck_tab.max_inline_suggestions "5"
/set plugins.var.python.spellcheck_tab.debug_mode "0"
```

Aby zmodyfikować używane języki, edytuj bezpośrednio skrypt i zmień listę `languages`.

## Licencja

GPL v2
