"""Core helpers for the TIPO PNG Info Restore extension.

This module contains data handling only. Every restore_* function receives the
infotext dictionary that the WebUI paste machinery builds from a PNG and
returns the value that one single TIPO UI control should be set to.

Returning None means "leave this control untouched". The WebUI paste code turns
a None result into gr.update() with no value, so the control keeps whatever the
user currently has.

This module never guesses, infers or reconstructs a value. A control is only
written when the infotext positively contains the value for it; otherwise None
is returned.

Since Rev8 it also holds the helpers that keep Dynamic Prompts blocks such as
{brown hair|blonde hair} intact through TIPO prompt generation. See the
"Dynamic Prompts protection" section at the bottom of this file.
"""

import ast
import json
import re

# ---------------------------------------------------------------------------
# Infotext keys written by z-tipo-extension itself.
#
# Reference: KohakuBlueleaf/z-tipo-extension, scripts/tipo.py, write_infotext().
#   INFOTEXT_KEY        = "TIPO Parameters"  -> json dump of the settings
#   INFOTEXT_KEY_PROMPT = "TIPO prompt"      -> p.prompt.strip() or args[-1]
#   INFOTEXT_NL_PROMPT  = "TIPO nl prompt"   -> args[-2]
#   INFOTEXT_KEY_FORMAT = "TIPO format"      -> args[3] (the preset NAME)
#
# args[-2] is the "Tag Prompt" textbox and args[-1] is the "Natural Language
# Prompt" textbox. So "TIPO nl prompt" actually holds the TAG prompt, and the
# natural language prompt is not stored by z-tipo at all.
#
# Note also the "or" in INFOTEXT_KEY_PROMPT: when the main prompt box is empty,
# z-tipo stores the natural language field there instead. That ambiguity is the
# reason this extension records the main prompt under its own key.
#
# None of these keys exist at all when the TIPO checkbox is off, because both
# process() and before_process() return before write_infotext() is reached.
# ---------------------------------------------------------------------------
TIPO_PARAMS_KEY = "TIPO Parameters"
TIPO_PROMPT_KEY = "TIPO prompt"
TIPO_TAG_PROMPT_KEY = "TIPO nl prompt"
TIPO_FORMAT_KEY = "TIPO format"

# ---------------------------------------------------------------------------
# Infotext keys written by this extension, to fill the gaps above.
#
# Schema history:
#   "1" - SOURCE_TAG_KEY and SOURCE_NL_KEY only.
#   "2" - SOURCE_MAIN_KEY added, so the main prompt no longer has to be
#         inferred from the ambiguous "TIPO prompt" value.
#   "3" - SOURCE_SETTINGS_KEY added, written only for runs where the TIPO
#         checkbox was off and z-tipo therefore recorded nothing.
# Readers key off the presence of each individual key, so all schemas load.
# ---------------------------------------------------------------------------
SOURCE_SCHEMA_KEY = "TIPO Input Restore Schema"
SOURCE_SCHEMA_VALUE = "3"
SOURCE_MAIN_KEY = "TIPO Input Main Prompt"
SOURCE_TAG_KEY = "TIPO Input Tag Prompt"
SOURCE_NL_KEY = "TIPO Input Natural Language Prompt"
SOURCE_SETTINGS_KEY = "TIPO Input Settings"

# z-tipo stores the parameter dict as json.dumps(...).translate(QUOTESWAP),
# which swaps single and double quotes. Apply the same table to undo it. The
# settings this extension writes are plain JSON and need no such treatment.
QUOTESWAP = str.maketrans("'\"", "\"'")

TIMING_VALUES = {
    "BEFORE": "Before applying other prompt processings",
    "AFTER": "After applying other prompt processings",
}

CUSTOM_FORMAT_NAME = "custom"

# write_infotext(p, prompt, timing, seed, follow_seed, *args) receives exactly
# 13 items in *args on current z-tipo, and the last two are the tag prompt and
# the natural language prompt. Any other count means the layout this extension
# was written against no longer holds, so nothing is recorded rather than risk
# writing the wrong text into the infotext.
WRITER_ARG_COUNT = 13

_TRUE_RE = re.compile(r"\btrue\b")
_FALSE_RE = re.compile(r"\bfalse\b")
_NULL_RE = re.compile(r"\bnull\b")


# ---------------------------------------------------------------------------
# Parameter dictionary parsing
# ---------------------------------------------------------------------------
def _load_mapping(text):
    """Try hard to turn one stored parameter string into a dict."""
    for candidate in (text, text.translate(QUOTESWAP)):
        try:
            parsed = json.loads(candidate)
        except Exception:
            parsed = None
        if isinstance(parsed, dict):
            return parsed

    for candidate in (text, text.translate(QUOTESWAP)):
        try:
            parsed = ast.literal_eval(candidate)
        except Exception:
            parsed = None
        if isinstance(parsed, dict):
            return parsed

    return None


def _parse_one(params, key):
    raw = params.get(key)
    if isinstance(raw, dict):
        # z-tipo registers an on_infotext_pasted callback that already decoded
        # its own value for us.
        return raw
    if not isinstance(raw, str):
        return None

    text = raw.strip()
    if not text:
        return None

    parsed = _load_mapping(text)
    if parsed is not None:
        return parsed

    # Last resort: the text uses Python-style quoting but JSON-style literals.
    normalized = _TRUE_RE.sub("True", text)
    normalized = _FALSE_RE.sub("False", normalized)
    normalized = _NULL_RE.sub("None", normalized)
    try:
        parsed = ast.literal_eval(normalized)
    except Exception:
        return None
    return parsed if isinstance(parsed, dict) else None


def parse_tipo_params(params):
    """Return the TIPO settings dict from an infotext dict, or None.

    z-tipo's own key wins. The key written by this extension is the fallback,
    and it only exists for runs where the TIPO checkbox was off.
    """
    if not isinstance(params, dict):
        return None

    for key in (TIPO_PARAMS_KEY, SOURCE_SETTINGS_KEY):
        parsed = _parse_one(params, key)
        if parsed is not None:
            return parsed
    return None


def has_tipo_identity(params):
    """True only when this infotext positively came from a TIPO-aware run.

    Either z-tipo recorded its settings, or this extension recorded the source
    prompts. A run with the TIPO checkbox off produces only the latter.
    """
    if not isinstance(params, dict):
        return False
    if SOURCE_SCHEMA_KEY in params:
        return True
    return parse_tipo_params(params) is not None


def get_tipo_param(params, key):
    parsed = parse_tipo_params(params)
    if parsed is None:
        return None
    return parsed.get(key)


# ---------------------------------------------------------------------------
# Choice validation
# ---------------------------------------------------------------------------
def _choice_values(choices):
    """Flatten a gradio choices list into the set of acceptable values."""
    if choices is None:
        return None
    values = set()
    for choice in choices:
        if isinstance(choice, (tuple, list)):
            for item in choice:
                try:
                    values.add(item)
                except TypeError:
                    pass
        else:
            try:
                values.add(choice)
            except TypeError:
                pass
    return values


def _validated_choice(value, choices):
    """Return value only if it is one of the choices the control accepts."""
    if value is None:
        return None
    values = _choice_values(choices)
    if values is None:
        return value
    return value if value in values else None


# ---------------------------------------------------------------------------
# Simple parameter restore
# ---------------------------------------------------------------------------
def restore_simple_param(params, key, choices=None):
    return _validated_choice(get_tipo_param(params, key), choices)


def restore_timing(params, choices=None):
    """z-tipo stores the short form; this extension stores the UI label."""
    value = get_tipo_param(params, "timing")
    if isinstance(value, str) and value in TIMING_VALUES:
        value = TIMING_VALUES[value]
    return _validated_choice(value, choices)


def _selected_format_name(params):
    parsed = parse_tipo_params(params)
    if parsed is not None:
        value = parsed.get("format_selected")
        if isinstance(value, str) and value:
            return value
    if isinstance(params, dict):
        legacy = params.get(TIPO_FORMAT_KEY)
        if isinstance(legacy, str) and legacy:
            return legacy
    return None


def restore_format_selected(params, choices=None):
    if not has_tipo_identity(params):
        return None
    return _validated_choice(_selected_format_name(params), choices)


def restore_format_text(params):
    """Restore the custom format textarea only when the preset is 'custom'.

    The WebUI fires format_dropdown.change when the dropdown is restored, and
    that handler overwrites the textarea with the preset template. Writing the
    textarea for a non-custom preset would race against it for no benefit.
    """
    if _selected_format_name(params) != CUSTOM_FORMAT_NAME:
        return None
    value = get_tipo_param(params, "format")
    return value if isinstance(value, str) and value else None


# ---------------------------------------------------------------------------
# Prompt restore
# ---------------------------------------------------------------------------
def restore_main_prompt(params):
    """Restore the ordinary prompt box to its state just before generation.

    Preferred source is SOURCE_MAIN_KEY, which this extension writes from the
    prompt the run started with. It is the prompt box content verbatim, with
    no strip() and no fallback to another field, and it is captured before
    Dynamic Prompts expansion so that syntax such as {A|B} survives.

    For images made before this extension was installed, "TIPO prompt" is used
    as written. That value keeps the dynamic prompt syntax, the attention
    weights, the quality tag and rating tag placement and the trailing period
    exactly as they were, so nothing is reassembled here.

    The WebUI "Prompt" field is deliberately not used as a fallback: it holds
    the post-TIPO, post-Dynamic-Prompts text.
    """
    if not has_tipo_identity(params):
        return None

    if SOURCE_MAIN_KEY in params:
        value = params.get(SOURCE_MAIN_KEY)
        return value if isinstance(value, str) else None

    value = params.get(TIPO_PROMPT_KEY)
    return value if isinstance(value, str) else None


def restore_tag_prompt(params):
    """Restore the Tag Prompt textbox."""
    if not has_tipo_identity(params):
        return None

    if SOURCE_TAG_KEY in params:
        value = params.get(SOURCE_TAG_KEY)
        return value if isinstance(value, str) else None

    # Fallback for images made without this extension. See the note at the top
    # of this file: "TIPO nl prompt" holds the tag prompt.
    value = params.get(TIPO_TAG_PROMPT_KEY)
    return value if isinstance(value, str) else None


def restore_natural_language_prompt(params):
    """Restore the Natural Language Prompt textbox.

    z-tipo does not record this field, so it can only be restored from the key
    this extension writes. Without that key the value is unknown and the
    textbox is left untouched.
    """
    if not has_tipo_identity(params):
        return None

    value = params.get(SOURCE_NL_KEY)
    return value if isinstance(value, str) else None


# ---------------------------------------------------------------------------
# Infotext writing
# ---------------------------------------------------------------------------
def store_source_prompts(extra_generation_params, prompt, args):
    """Record the three TIPO prompt inputs for a run with TIPO enabled.

    prompt is the main prompt box content that z-tipo passes to write_infotext.
    args is the *args tuple from the same call; its last two items are the tag
    prompt and the natural language prompt. The settings are not recorded here
    because z-tipo already wrote them under its own key.

    Returns False without writing anything when the call shape does not match
    the layout this extension was written against.
    """
    if not isinstance(extra_generation_params, dict):
        return False
    if not isinstance(args, (list, tuple)):
        return False
    if len(args) != WRITER_ARG_COUNT:
        return False

    tag_prompt = args[-2]
    nl_prompt = args[-1]
    if not isinstance(prompt, str):
        return False
    if not isinstance(tag_prompt, str) or not isinstance(nl_prompt, str):
        return False

    extra_generation_params[SOURCE_SCHEMA_KEY] = SOURCE_SCHEMA_VALUE
    extra_generation_params[SOURCE_MAIN_KEY] = prompt
    extra_generation_params[SOURCE_TAG_KEY] = tag_prompt
    extra_generation_params[SOURCE_NL_KEY] = nl_prompt
    return True


def store_disabled_run(
    extra_generation_params,
    prompt,
    tag_prompt,
    nl_prompt,
    settings,
):
    """Record a run made with the TIPO checkbox off.

    z-tipo writes nothing at all in that case, so this extension records both
    the three prompt boxes and a snapshot of the TIPO settings under its own
    keys. The settings go under SOURCE_SETTINGS_KEY rather than z-tipo's key,
    so that z-tipo's own paste entry still sees no "TIPO Parameters" and leaves
    the enable checkbox off, matching how the image was made.

    Returns False without writing anything when the values are not usable.
    """
    if not isinstance(extra_generation_params, dict):
        return False
    if not isinstance(prompt, str):
        return False
    if not isinstance(tag_prompt, str) or not isinstance(nl_prompt, str):
        return False
    if not isinstance(settings, dict) or not settings:
        return False

    try:
        encoded = json.dumps(settings, ensure_ascii=False)
    except Exception:
        return False

    extra_generation_params[SOURCE_SCHEMA_KEY] = SOURCE_SCHEMA_VALUE
    extra_generation_params[SOURCE_MAIN_KEY] = prompt
    extra_generation_params[SOURCE_TAG_KEY] = tag_prompt
    extra_generation_params[SOURCE_NL_KEY] = nl_prompt
    extra_generation_params[SOURCE_SETTINGS_KEY] = encoded
    return True


# ---------------------------------------------------------------------------
# Dynamic Prompts protection (Rev8)
#
# TIPO does not paste the user's tags back. z-tipo splits the prompt on
# commas, KGen feeds the tags to the language model, and the final prompt is
# rebuilt from the text the model returns. A Dynamic Prompts block such as
# {brown hair|blonde hair|grey hair|silver hair} does not survive that round
# trip reliably, so the generated prompt ends up with no variant syntax and
# every image gets the same choice.
#
# The fix is a plain swap around z-tipo's _process():
#
#   before: every top-level {...} block -> one placeholder word
#   after : every placeholder word      -> the original block, byte for byte
#
# The placeholder is made of lowercase ASCII letters and digits only, so it
# passes every step of the pipeline unchanged:
#   - no comma          -> the comma split does not cut it
#   - no underscore     -> KGen's underscore-to-space rewrite does not touch it
#   - no ( ) [ ] : \    -> the attention parser treats it as plain text
#   - no < > #          -> extra network and comment parsing ignore it
#
# Placeholder layout: PREFIX + index + SUFFIX, for example "sdpq0x". The
# suffix makes "sdpq1x" impossible to find inside "sdpq11x", so ten or more
# blocks cannot be confused with each other.
#
# Nested blocks such as {a|{b|c}} are protected as one outer block. A backslash
# escaped brace (\{ or \}) is literal text and never starts or ends a block.
# An opening brace that is never closed is left alone.
# ---------------------------------------------------------------------------
PLACEHOLDER_PREFIXES = ("sdpq", "sdpw", "sdpk", "sdpv", "sdpz")
PLACEHOLDER_SUFFIX = "x"


def find_dynamic_blocks(text):
    """Return a list of (start, end) spans of top-level {...} blocks.

    end is exclusive, so text[start:end] is the whole block including braces.
    """
    spans = []
    if not isinstance(text, str) or "{" not in text:
        return spans

    depth = 0
    start = -1
    index = 0
    length = len(text)
    while index < length:
        char = text[index]
        if char == "\\":
            # Skip the escaped character, whatever it is.
            index += 2
            continue
        if char == "{":
            if depth == 0:
                start = index
            depth += 1
        elif char == "}" and depth > 0:
            depth -= 1
            if depth == 0 and start >= 0:
                spans.append((start, index + 1))
                start = -1
        index += 1
    return spans


def _choose_prefix(texts):
    """Pick a placeholder prefix that does not already occur in any input."""
    joined = "\n".join(t for t in texts if isinstance(t, str)).lower()
    for prefix in PLACEHOLDER_PREFIXES:
        if prefix not in joined:
            return prefix
    return None


class DynamicBlockTable:
    """Shared block <-> placeholder mapping for one TIPO call."""

    def __init__(self, prefix):
        self.prefix = prefix
        self.block_to_token = {}
        self.token_to_block = {}
        self.order = []

    def token_for(self, block):
        token = self.block_to_token.get(block)
        if token is not None:
            return token
        token = f"{self.prefix}{len(self.order)}{PLACEHOLDER_SUFFIX}"
        self.block_to_token[block] = token
        self.token_to_block[token] = block
        self.order.append(token)
        return token

    def __bool__(self):
        return bool(self.order)


def protect_text(text, table):
    """Replace every top-level {...} block in text with its placeholder."""
    if not isinstance(text, str):
        return text
    spans = find_dynamic_blocks(text)
    if not spans:
        return text

    pieces = []
    cursor = 0
    for start, end in spans:
        pieces.append(text[cursor:start])
        pieces.append(table.token_for(text[start:end]))
        cursor = end
    pieces.append(text[cursor:])
    return "".join(pieces)


def protect_texts(texts):
    """Protect several strings with one shared table.

    Returns (protected_texts, table). table is None when nothing needed
    protection or when no safe placeholder prefix could be found; in both
    cases the caller should run TIPO with the original values.
    """
    candidates = [t for t in texts if isinstance(t, str)]
    if not any(find_dynamic_blocks(t) for t in candidates):
        return list(texts), None

    prefix = _choose_prefix(candidates)
    if prefix is None:
        return list(texts), None

    table = DynamicBlockTable(prefix)
    protected = [protect_text(t, table) for t in texts]
    if not table:
        return list(texts), None
    return protected, table


def _append_to_first_line(text, blocks):
    """Append blocks to the end of the first line of text.

    The first line of a TIPO result is where its tags are, so a block that
    TIPO dropped is put back among the tags rather than after the natural
    language section or the extra network line.
    """
    addition = ", ".join(blocks)
    newline = text.find("\n")
    if newline < 0:
        head, tail = text, ""
    else:
        head, tail = text[:newline], text[newline:]

    stripped = head.rstrip()
    if stripped.endswith(","):
        stripped = stripped[:-1].rstrip()
    if stripped:
        head = stripped + ", " + addition
    else:
        head = addition
    return head + tail


def restore_text(text, table):
    """Put every original block back in place of its placeholder.

    Returns (restored_text, missing_blocks). A block whose placeholder is not
    found anywhere in text is appended to the tag line so that it is never
    lost silently; those blocks are also returned so the caller can report
    them.
    """
    if not isinstance(text, str) or not table:
        return text, []

    missing = []
    for token in table.order:
        block = table.token_to_block[token]
        if token in text:
            text = text.replace(token, block)
        else:
            missing.append(block)

    if missing:
        text = _append_to_first_line(text, missing)
    return text, missing
