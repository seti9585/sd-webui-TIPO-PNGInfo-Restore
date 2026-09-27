"""TIPO PNG Info Restore.

Restores the three TIPO prompt areas (Tag Prompt, Natural Language Prompt and
the ordinary prompt box) plus every TIPO parameter from the infotext embedded
in a PNG, so that pressing Generate again reproduces the same run.

Design notes:

* The ordinary prompt box is restored from this extension's own key when
  present, otherwise from z-tipo's "TIPO prompt" key. Either way the value is
  the prompt box content as it was just before the run. Nothing is
  reassembled, so dynamic prompt syntax, attention weights, quality tag and
  rating tag placement and the trailing period are all preserved verbatim.
* The Tag Prompt comes from this extension's own key when present, otherwise
  from z-tipo's "TIPO nl prompt" key, which despite its name holds the tag
  prompt.
* The Natural Language Prompt is only restored from this extension's own key.
  z-tipo does not record it, so for older images the textbox is left alone
  rather than filled with a guess.
* When the TIPO checkbox is off, z-tipo writes no infotext at all, so this
  extension records the three boxes and a settings snapshot itself. That is
  the "press Generate Prompt, turn TIPO off, then generate" workflow.
* Controls are located by their gradio label, with a positional fallback, so a
  z-tipo fork with a different control count does not shift every parameter.
* Only the paste entries that z-tipo itself registered are replaced. Entries
  contributed by any other extension are never touched.
* Rev8: Dynamic Prompts blocks such as {brown hair|blonde hair} are swapped
  for placeholder words before TIPO generates a prompt and swapped back
  afterwards, so the generated prompt keeps the variant syntax verbatim. This
  applies to the "Generate Prompt" button and to generation with TIPO on.
"""

import types

from modules import script_callbacks, scripts

from seti_tipo_pnginfo_restore.core import (
    get_tipo_param,
    protect_texts,
    restore_format_selected,
    restore_format_text,
    restore_main_prompt,
    restore_natural_language_prompt,
    restore_simple_param,
    restore_tag_prompt,
    restore_text,
    restore_timing,
    store_disabled_run,
    store_source_prompts,
)

BUILD_NAME = "TIPO PNG Info Restore Rev8"

TAB_NAMES = ("txt2img", "img2img")

# elem_id of a component that the WebUI creates after every script ui() has run
# and before the paste buttons are wired up. Using it removes any dependency on
# script ordering.
LATE_COMPONENT_ELEM_IDS = {
    "generation_info_txt2img": 0,
    "generation_info_img2img": 1,
}

# Gradio labels of the TIPO controls, as defined in z-tipo scripts/tipo.py.
CONTROL_LABELS = {
    "timing": "Upsampling timing",
    "seed": "Seed for upsampling tags",
    "follow_generation_seed": "Follow the image generation seed",
    "tag_length": "Tags Length target",
    "nl_length": "NL Length target",
    "ban_tags": "Ban tags",
    "format_selected": "Prompt Format",
    "format_text": "Custom Prompt Format",
    "temperature": "Temperature",
    "top_p": "Top-p",
    "top_k": "Top-k",
    "model": "Model",
    "gguf_cpu": "Use CPU (GGUF)",
    "no_formatting": "No formatting",
    "tag_prompt": "Tag Prompt",
    "nl_prompt": "Natural Language Prompt",
}

# Positional fallback for the current layout (17 controls).
CONTROL_INDEX_MODERN = {
    "timing": 1,
    "seed": 2,
    "follow_generation_seed": 3,
    "tag_length": 4,
    "nl_length": 5,
    "ban_tags": 6,
    "format_selected": 7,
    "format_text": 8,
    "temperature": 9,
    "top_p": 10,
    "top_k": 11,
    "model": 12,
    "gguf_cpu": 13,
    "no_formatting": 14,
    "tag_prompt": 15,
    "nl_prompt": 16,
}

# Positional fallback for the layout before "Follow the image generation seed"
# was added (16 controls).
CONTROL_INDEX_LEGACY = {
    "timing": 1,
    "seed": 2,
    "tag_length": 3,
    "nl_length": 4,
    "ban_tags": 5,
    "format_selected": 6,
    "format_text": 7,
    "temperature": 8,
    "top_p": 9,
    "top_k": 10,
    "model": 11,
    "gguf_cpu": 12,
    "no_formatting": 13,
    "tag_prompt": 14,
    "nl_prompt": 15,
}

# Logical control name -> key inside the recorded settings snapshot. The key
# names match the ones z-tipo uses in its own "TIPO Parameters" value, so both
# sources read back through the same restore functions.
SETTINGS_FIELDS = (
    ("seed", "seed"),
    ("follow_generation_seed", "follow_generation_seed"),
    ("timing", "timing"),
    ("tag_length", "tag_length"),
    ("nl_length", "nl_length"),
    ("ban_tags", "ban_tags"),
    ("format_selected", "format_selected"),
    ("format_text", "format"),
    ("temperature", "temperature"),
    ("top_p", "top_p"),
    ("top_k", "top_k"),
    ("model", "model"),
    ("gguf_cpu", "gguf_cpu"),
    ("no_formatting", "no_formatting"),
)

ENABLED_INDEX = 0
MIN_CONTROL_COUNT = 16

# z-tipo TIPOScript._process(prompt, nl_prompt, aspect_ratio, seed,
# tag_length, nl_length, ban_tags, format_select, format, temperature, top_p,
# top_k, model, gguf_use_cpu, no_formatting, tag_prompt) takes 16 positional
# arguments. The first is the text TIPO works on and the last is the Tag
# Prompt, which z-tipo falls back to when the first is empty. Whichever of the
# two TIPO will actually use is protected. Any other argument count means the layout
# changed, and TIPO then runs exactly as it would without this extension.
PROCESS_ARG_COUNT = 16
PROCESS_PROTECTED_INDICES = (0, PROCESS_ARG_COUNT - 1)

_reported = set()


def _log(message):
    print(f"[{BUILD_NAME}] {message}")


def _log_once(key, message):
    if key in _reported:
        return
    _reported.add(key)
    _log(message)


def _component_choices(component):
    if component is None:
        return None
    return getattr(component, "choices", None)


def _component_label(component):
    label = getattr(component, "label", None)
    if isinstance(label, str):
        label = label.strip()
        return label or None
    return None


def _find_tipo_script(runner):
    scriptlist = getattr(runner, "scripts", None)
    if not scriptlist:
        return None
    for script in scriptlist:
        if script.__class__.__name__ != "TIPOScript":
            continue
        if not hasattr(script, "tag_prompt_area"):
            continue
        if not hasattr(script, "prompt_area"):
            continue
        return script
    return None


def _runner_for(is_img2img):
    return scripts.scripts_img2img if is_img2img else scripts.scripts_txt2img


def _resolve_controls(controls):
    """Map logical names to gradio components, by label then by position."""
    resolved = {}

    by_label = {}
    for component in controls:
        label = _component_label(component)
        if label is not None and label not in by_label:
            by_label[label] = component

    for name, label in CONTROL_LABELS.items():
        component = by_label.get(label)
        if component is not None:
            resolved[name] = component

    index_map = CONTROL_INDEX_MODERN if len(controls) >= 17 else CONTROL_INDEX_LEGACY
    for name, index in index_map.items():
        if resolved.get(name) is not None:
            continue
        if 0 <= index < len(controls) and controls[index] is not None:
            resolved[name] = controls[index]

    return resolved


def _resolve_prompt_areas(tipo_script, is_img2img):
    """Return (main prompt, natural language prompt, tag prompt) components."""
    main_prompt = None
    nl_prompt = None
    tag_prompt = None

    prompt_area = getattr(tipo_script, "prompt_area", None)
    if isinstance(prompt_area, (list, tuple)):
        base = is_img2img * 2
        if base < len(prompt_area):
            main_prompt = prompt_area[base]
        if base + 1 < len(prompt_area):
            nl_prompt = prompt_area[base + 1]

    tag_prompt_area = getattr(tipo_script, "tag_prompt_area", None)
    if isinstance(tag_prompt_area, (list, tuple)):
        if is_img2img < len(tag_prompt_area):
            tag_prompt = tag_prompt_area[is_img2img]

    return main_prompt, nl_prompt, tag_prompt


def _build_arg_index(controls, resolved):
    """Logical name -> position in the control list.

    The control list a script returns from ui() is also the order its values
    arrive in p.script_args, so these positions let the recorder read the TIPO
    UI values even when TIPO itself does nothing that run.
    """
    position = {}
    for index, component in enumerate(controls):
        position.setdefault(id(component), index)

    arg_index = {"enabled": ENABLED_INDEX}
    for name, component in resolved.items():
        index = position.get(id(component))
        if index is not None:
            arg_index[name] = index
    return arg_index


def _build_fields(resolved, main_prompt):
    """Build the (component, getter) list this extension takes ownership of."""
    fields = []

    def add(name, getter):
        component = resolved.get(name)
        if component is not None:
            fields.append((component, getter))

    timing_choices = _component_choices(resolved.get("timing"))
    tag_length_choices = _component_choices(resolved.get("tag_length"))
    nl_length_choices = _component_choices(resolved.get("nl_length"))
    format_choices = _component_choices(resolved.get("format_selected"))
    model_choices = _component_choices(resolved.get("model"))

    add("timing", lambda d: restore_timing(d, timing_choices))
    add("seed", lambda d: get_tipo_param(d, "seed"))
    add(
        "follow_generation_seed",
        lambda d: get_tipo_param(d, "follow_generation_seed"),
    )
    add(
        "tag_length",
        lambda d: restore_simple_param(d, "tag_length", tag_length_choices),
    )
    add(
        "nl_length",
        lambda d: restore_simple_param(d, "nl_length", nl_length_choices),
    )
    add("ban_tags", lambda d: get_tipo_param(d, "ban_tags"))
    add("format_selected", lambda d: restore_format_selected(d, format_choices))
    add("format_text", restore_format_text)
    add("temperature", lambda d: get_tipo_param(d, "temperature"))
    add("top_p", lambda d: get_tipo_param(d, "top_p"))
    add("top_k", lambda d: get_tipo_param(d, "top_k"))
    add("model", lambda d: restore_simple_param(d, "model", model_choices))
    add("gguf_cpu", lambda d: get_tipo_param(d, "gguf_cpu"))
    add("no_formatting", lambda d: get_tipo_param(d, "no_formatting"))
    add("tag_prompt", restore_tag_prompt)
    add("nl_prompt", restore_natural_language_prompt)

    fields.append((main_prompt, restore_main_prompt))
    return fields


def _replace_paste_fields(runner, tipo_script, is_img2img):
    if getattr(runner, "_seti_tipo_restore_fields_done", False):
        return True

    controls = getattr(tipo_script, "controls", None)
    if not isinstance(controls, (list, tuple)):
        return False
    controls = list(controls)
    if len(controls) < MIN_CONTROL_COUNT:
        return False

    infotext_fields = getattr(runner, "infotext_fields", None)
    if not isinstance(infotext_fields, list):
        return False

    resolved = _resolve_controls(controls)
    main_prompt, nl_area, tag_area = _resolve_prompt_areas(tipo_script, is_img2img)
    if main_prompt is None:
        return False

    if resolved.get("tag_prompt") is None and tag_area is not None:
        resolved["tag_prompt"] = tag_area
    if resolved.get("nl_prompt") is None and nl_area is not None:
        resolved["nl_prompt"] = nl_area

    fields = _build_fields(resolved, main_prompt)
    owned = {id(component) for component, _ in fields}

    # Drop only the entries that z-tipo itself registered for these components.
    # Entries registered by any other extension stay exactly where they are.
    tipo_fields = getattr(tipo_script, "infotext_fields", None) or []
    doomed = set()
    for entry in tipo_fields:
        if not isinstance(entry, (list, tuple)) or not entry:
            continue
        if id(entry[0]) in owned:
            doomed.add(id(entry))

    if doomed:
        infotext_fields[:] = [
            entry for entry in infotext_fields if id(entry) not in doomed
        ]

    # Appending puts these entries last, so they win over the WebUI's own
    # "Prompt" entry for the ordinary prompt box.
    infotext_fields.extend(fields)

    runner._seti_tipo_restore_arg_index = _build_arg_index(controls, resolved)
    runner._seti_tipo_restore_fields_done = True

    missing = [name for name in CONTROL_LABELS if resolved.get(name) is None]
    if missing:
        _log(
            "Some TIPO controls were not recognized and are left untouched: "
            + ", ".join(sorted(missing))
        )
    return True


def _patch_writer(tipo_script):
    if getattr(tipo_script, "_seti_tipo_restore_writer_done", False):
        return True

    original = getattr(tipo_script, "write_infotext", None)
    if not callable(original):
        return False

    def patched_write_infotext(
        self,
        p,
        prompt,
        process_timing,
        seed,
        follow_generation_seed,
        *args,
    ):
        original(
            p,
            prompt,
            process_timing,
            seed,
            follow_generation_seed,
            *args,
        )
        try:
            stored = store_source_prompts(
                getattr(p, "extra_generation_params", None),
                prompt,
                args,
            )
        except Exception as exc:
            _log_once("writer_error", f"Could not store source prompts: {exc}")
            return
        if not stored:
            _log_once(
                "writer_shape",
                "TIPO passed an unexpected argument shape to write_infotext. "
                "The source prompts will not be recorded, and the Natural "
                "Language Prompt will not be restorable from these images.",
            )

    tipo_script.write_infotext = types.MethodType(patched_write_infotext, tipo_script)
    tipo_script._seti_tipo_restore_writer_done = True
    return True


def _patch_process(tipo_script):
    """Keep Dynamic Prompts blocks intact through TIPO prompt generation.

    z-tipo's "Generate Prompt" button (prompt_gen_only) and its generation
    hooks (process / before_process) all call self._process(...). Setting an
    instance attribute makes every one of those calls go through the wrapper,
    because self._process looks at the instance before the class.

    Any failure inside the wrapper falls back to calling TIPO with the original
    arguments, so this can never make TIPO stop working. Errors raised by TIPO
    itself are passed through unchanged.
    """
    if getattr(tipo_script, "_seti_tipo_restore_process_done", False):
        return True

    original = getattr(tipo_script, "_process", None)
    if not callable(original):
        return False

    def patched_process(self, *args, **kwargs):
        if kwargs or len(args) != PROCESS_ARG_COUNT:
            _log_once(
                "process_shape",
                "TIPO _process was called with an unexpected argument shape. "
                "Dynamic Prompts blocks are not protected for this call.",
            )
            return original(*args, **kwargs)

        try:
            # z-tipo does "prompt = prompt.strip() or tag_prompt", so only one
            # of the two texts is ever used. Protect only that one; otherwise
            # a block sitting in an unused Tag Prompt would be reported as
            # dropped and appended to a prompt it never belonged to (for
            # example the already expanded prompt of the AFTER timing).
            first = args[PROCESS_PROTECTED_INDICES[0]]
            if isinstance(first, str) and first.strip():
                index = PROCESS_PROTECTED_INDICES[0]
            else:
                index = PROCESS_PROTECTED_INDICES[1]
            protected, table = protect_texts([args[index]])
        except Exception as exc:
            _log_once("protect_error", f"Could not protect Dynamic Prompts: {exc}")
            return original(*args, **kwargs)

        if table is None:
            return original(*args, **kwargs)

        new_args = list(args)
        new_args[index] = protected[0]

        result = original(*new_args, **kwargs)

        try:
            restored, missing = restore_text(result, table)
        except Exception as exc:
            _log_once("restore_error", f"Could not restore Dynamic Prompts: {exc}")
            return result

        if missing:
            _log(
                "TIPO dropped "
                + str(len(missing))
                + " Dynamic Prompts block(s); appended to the tag line: "
                + " , ".join(missing)
            )
        return restored

    tipo_script._process = types.MethodType(patched_process, tipo_script)
    tipo_script._seti_tipo_restore_process_done = True
    return True


def _apply(is_img2img):
    """Patch one tab. Safe to call several times; the work happens once."""
    runner = _runner_for(is_img2img)
    if runner is None:
        return False

    tab = TAB_NAMES[1 if is_img2img else 0]

    tipo_script = _find_tipo_script(runner)
    if tipo_script is None:
        return False

    try:
        writer_ok = _patch_writer(tipo_script)
    except Exception as exc:
        _log_once(f"writer_error_{tab}", f"Writer patch failed safely on {tab}: {exc}")
        writer_ok = False

    try:
        process_ok = _patch_process(tipo_script)
    except Exception as exc:
        _log_once(
            f"process_error_{tab}",
            f"Dynamic Prompts patch failed safely on {tab}: {exc}",
        )
        process_ok = False

    try:
        fields_ok = _replace_paste_fields(runner, tipo_script, is_img2img)
    except Exception as exc:
        _log_once(f"error_{tab}", f"Patch failed safely on {tab}: {exc}")
        return False

    if writer_ok:
        _log_once(f"writer_{tab}", f"Source prompt writer patched on {tab}.")
    else:
        _log_once(
            f"writer_miss_{tab}",
            f"TIPO infotext writer was not recognized on {tab}.",
        )

    if process_ok:
        _log_once(
            f"process_{tab}",
            f"Dynamic Prompts protection patched on {tab}.",
        )
    else:
        _log_once(
            f"process_miss_{tab}",
            f"TIPO prompt generator was not recognized on {tab}; "
            "Dynamic Prompts blocks are not protected.",
        )

    if fields_ok:
        _log_once(f"fields_{tab}", f"Infotext restore mapping patched on {tab}.")

    return fields_ok


def _on_after_component(component, **kwargs):
    elem_id = kwargs.get("elem_id")
    if elem_id is None:
        elem_id = getattr(component, "elem_id", None)
    if elem_id not in LATE_COMPONENT_ELEM_IDS:
        return
    try:
        _apply(LATE_COMPONENT_ELEM_IDS[elem_id])
    except Exception as exc:
        _log_once("hook_error", f"Late patch failed safely: {exc}")


script_callbacks.on_after_component(_on_after_component)


def _tipo_ui_values(p, runner, tipo_script):
    """Read the live TIPO control values out of this run's script arguments."""
    arg_index = getattr(runner, "_seti_tipo_restore_arg_index", None)
    if not isinstance(arg_index, dict) or not arg_index:
        return None, None

    args_from = getattr(tipo_script, "args_from", None)
    args_to = getattr(tipo_script, "args_to", None)
    script_args = getattr(p, "script_args", None)
    if args_from is None or args_to is None or script_args is None:
        return None, None

    try:
        values = list(script_args[args_from:args_to])
    except Exception:
        return None, None

    if len(values) < MIN_CONTROL_COUNT:
        return None, None
    return arg_index, values


def _record_disabled_run(p, is_img2img):
    """Record the prompt boxes and settings for a run made with TIPO off.

    z-tipo returns from process() and before_process() before writing anything
    when its checkbox is off, so without this the image carries no TIPO data at
    all. Nothing is written unless at least one of the two TIPO input boxes has
    text in it, which keeps the infotext of unrelated images clean.
    """
    runner = _runner_for(is_img2img)
    if runner is None:
        return

    tipo_script = _find_tipo_script(runner)
    if tipo_script is None:
        return

    arg_index, values = _tipo_ui_values(p, runner, tipo_script)
    if arg_index is None:
        return

    def value_of(name):
        index = arg_index.get(name)
        if index is None or index >= len(values):
            return None
        return values[index]

    if value_of("enabled"):
        # z-tipo will write its own infotext, and the writer patch adds the
        # source prompts on top of it.
        return

    tag_prompt = value_of("tag_prompt")
    nl_prompt = value_of("nl_prompt")
    if not isinstance(tag_prompt, str):
        tag_prompt = ""
    if not isinstance(nl_prompt, str):
        nl_prompt = ""
    if not tag_prompt.strip() and not nl_prompt.strip():
        return

    settings = {}
    for name, key in SETTINGS_FIELDS:
        value = value_of(name)
        if value is not None:
            settings[key] = value
    if not settings:
        return

    stored = store_disabled_run(
        getattr(p, "extra_generation_params", None),
        getattr(p, "prompt", None),
        tag_prompt,
        nl_prompt,
        settings,
    )
    if not stored:
        _log_once(
            "disabled_store",
            "Could not record the TIPO input boxes for a run with TIPO off.",
        )


class TIPOInfotextRestoreScript(scripts.Script):
    sorting_priority = 100000
    create_group = False

    def title(self):
        return BUILD_NAME

    def show(self, is_img2img):
        return scripts.AlwaysVisible

    def ui(self, is_img2img):
        # First chance to patch. If this script's ui() happens to run before
        # TIPO's, nothing is ready yet and the generation_info hook above takes
        # care of it instead.
        try:
            _apply(1 if is_img2img else 0)
        except Exception as exc:
            _log_once("ui_error", f"Patch attempt failed safely: {exc}")
        return []

    def before_process(self, p, *args):
        # before_process runs ahead of every script's process(), so p.prompt is
        # still the text the user typed: no TIPO output, no Dynamic Prompts
        # expansion.
        self._record_once(p)

    def process(self, p, *args):
        # Fallback for backends that do not call before_process at all. The
        # guard keeps the earlier, cleaner capture when both hooks run.
        self._record_once(p)

    def _record_once(self, p):
        if getattr(p, "_seti_tipo_restore_recorded", False):
            return
        try:
            _record_disabled_run(p, 1 if self.is_img2img else 0)
        except Exception as exc:
            _log_once("record_error", f"Recording failed safely: {exc}")
        try:
            p._seti_tipo_restore_recorded = True
        except Exception:
            pass
