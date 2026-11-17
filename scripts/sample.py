"""Sample k readings per request from small local models (MLX, 4-bit).

Writes one JSON line per generation to results/samples.jsonl and skips lines that
already exist, so a stopped run picks up where it left off.

usage: python3 scripts/sample.py [--budget-min 13]
"""
import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import mlx.core as mx
from mlx_lm import generate, load
from mlx_lm.sample_utils import make_sampler

from ctable_readings.dataset import FAMILIES, requests

K = 8
OUT = os.path.join(os.path.dirname(__file__), "..", "results", "samples.jsonl")

SLOT_DESC = {
    "smoke_min": "lowest smoke level that triggers the action",
    "alarm_hours": "when the alarm rule is active",
    "zones": "which sprinkler zones turn on",
    "lock_delay_min": "minutes to wait after everyone leaves before locking (integer)",
    "lock_hours": "when the auto-lock rule is active",
    "night_start": "clock time when 'night' starts, HH:MM 24-hour",
    "lights": "which lights turn on",
    "auto_off_min": "minutes the stove may stay on with nobody in the kitchen (integer)",
    "home_exception": "whether the stove still turns off when someone is elsewhere in the house",
    "valve_action": "what happens on a leak",
    "sensors": "which leak sensors trigger the rule",
    "off_temp_f": "room temperature in degrees F at which the heater turns off (integer)",
    "max_hours": "most hours the heater may run in a row (integer)",
    "close_after_min": "minutes the garage may stay open before it closes (integer)",
    "close_hours": "when the auto-close rule is active",
}

TEMPLATES = [
    ("You turn smart-home requests into device settings. Reply with one JSON object only.",
     'Devices: {devices}\nRequest: "{text}"\nFill in these settings:\n{fields}\nJSON:'),
    ("You are a home automation assistant. Answer with JSON only.",
     'A homeowner told you: "{text}". Their devices: {devices}. Write the settings you will use as a JSON object with these keys:\n{fields}'),
    ("Reply with a single JSON object and nothing else.",
     "Configure this automation.\nUser said: {text}\nAvailable devices: {devices}\nReturn JSON with exactly these fields:\n{fields}"),
    ("You configure IoT rules. Output JSON only.",
     "Translate the instruction into a rule configuration. Instruction: {text} | Devices: {devices} | Output a JSON object with:\n{fields}"),
]

# name: (model, temperature, template rule)
SETTINGS = {
    "A_t07": ("mlx-community/Qwen2.5-1.5B-Instruct-4bit", 0.7, "fixed"),
    "C_para": ("mlx-community/Qwen2.5-1.5B-Instruct-4bit", 0.7, "rotate"),
    "B_t10": ("mlx-community/Qwen2.5-1.5B-Instruct-4bit", 1.0, "fixed"),
    "D_3b": ("mlx-community/Qwen2.5-3B-Instruct-4bit", 0.7, "fixed"),
}


def fields_text(family):
    lines = []
    for name, spec in FAMILIES[family]["slots"].items():
        if spec["kind"] == "enum":
            opts = ", ".join(f'"{v}"' for v in spec["values"])
            lines.append(f'- "{name}": {SLOT_DESC[name]}; one of {opts}')
        else:
            lines.append(f'- "{name}": {SLOT_DESC[name]}')
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--budget-min", type=float, default=13.0)
    args = ap.parse_args()
    done = set()
    if os.path.exists(OUT):
        with open(OUT) as f:
            for line in f:
                r = json.loads(line)
                done.add((r["setting"], r["id"], r["r"]))
    t0 = time.time()
    reqs = requests()
    loaded = {}
    with open(OUT, "a") as out:
        for sname, (model_id, temp, rule) in SETTINGS.items():
            todo = [(q, r) for q in reqs for r in range(K) if (sname, q["id"], r) not in done]
            if not todo:
                continue
            if model_id not in loaded:
                loaded.clear()
                loaded[model_id] = load(model_id)
            model, tok = loaded[model_id]
            sampler = make_sampler(temp=temp)
            for q, r in todo:
                if time.time() - t0 > args.budget_min * 60:
                    print("[sample] budget reached, stopping", flush=True)
                    return
                ti = 0 if rule == "fixed" else r % len(TEMPLATES)
                sys_msg, user_t = TEMPLATES[ti]
                user = user_t.format(devices=q["devices"], text=q["text"], fields=fields_text(q["family"]))
                prompt = tok.apply_chat_template(
                    [{"role": "system", "content": sys_msg}, {"role": "user", "content": user}],
                    add_generation_prompt=True, tokenize=False)
                mx.random.seed(1000 * list(SETTINGS).index(sname) + 10 * reqs.index(q) + r)
                text = generate(model, tok, prompt, max_tokens=80, sampler=sampler)
                out.write(json.dumps({"setting": sname, "model": model_id, "temp": temp, "template": ti,
                                      "id": q["id"], "family": q["family"], "r": r, "text": text}) + "\n")
                out.flush()
            print(f"[sample] {sname} done at {time.time() - t0:.0f}s", flush=True)
    print(f"[sample] all done in {time.time() - t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()
