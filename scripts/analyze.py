"""Score the saved samples. Reads results/samples.jsonl, writes results/summary.json,
results/per_request.csv and two figures. No model is loaded here."""
import csv
import json
import os
import sys
from collections import defaultdict
from itertools import product

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from ctable_readings import ctable
from ctable_readings.dataset import FAMILIES, requests, safe
from ctable_readings.parse import INVALID, parse_reading

ROOT = os.path.join(os.path.dirname(__file__), "..")
K = 8
# Okabe-Ito colorblind-safe colors
COL = {"A_t07": "#0072B2", "B_t10": "#E69F00", "C_para": "#009E73", "D_3b": "#CC79A7",
       "A+C+D": "#000000"}
LABEL = {"A_t07": "1.5B, T=0.7, one prompt", "B_t10": "1.5B, T=1.0, one prompt",
         "C_para": "1.5B, T=0.7, 4 paraphrased prompts", "D_3b": "3B, T=0.7, one prompt",
         "A+C+D": "pool of A, C and D (24 samples)"}


def load_samples():
    by = defaultdict(dict)  # (setting, id) -> {r: reading or None}
    with open(os.path.join(ROOT, "results", "samples.jsonl")) as f:
        for line in f:
            s = json.loads(line)
            by[(s["setting"], s["id"])][s["r"]] = parse_reading(s["family"], s["text"])
    return by


def valid(rd):
    return rd is not None and INVALID not in rd


def readings_for(by, settings, qid, k):
    out = []
    for s in settings:
        d = by.get((s, qid), {})
        out += [d[r] for r in sorted(d) if r < k]
    return out


def score(by, settings, k, reqs):
    rows = []
    for q in reqs:
        fam, slots = q["family"], q["slots"]
        intended = tuple(q["intended"])
        raw = readings_for(by, settings, q["id"], k)
        if len(raw) < k * len(settings):
            return None  # incomplete
        good = [r for r in raw if valid(r)]
        distinct = sorted(set(good), key=str)
        is_safe = lambda w, fam=fam: safe(fam, w)
        row = {"id": q["id"], "family": fam, "n": len(raw), "n_valid": len(good),
               "n_distinct": len(distinct), "intended": list(intended),
               "intended_safe": safe(fam, intended),
               "covered": intended in set(good)}
        for i, name in enumerate(slots):
            row[f"slot{i}_covered"] = intended[i] in {r[i] for r in good}
        if good:
            tied = ctable.build(slots, good, "tied")
            ind = ctable.build(slots, good, "independent")
            row.update({
                "verdict_tied": ctable.verdict(tied, is_safe),
                "verdict_ind": ctable.verdict(ind, is_safe),
                "q_tied": ctable.question(tied, is_safe),
                "q_ind": ctable.question(ind, is_safe),
                "worlds_ind": len(ind.worlds()),
                "unproposed_ind": len(ctable.unproposed(ind)),
                "cond_tied": ctable.violation_condition(tied, is_safe),
            })
        else:
            row.update({"verdict_tied": "no_valid", "verdict_ind": "no_valid", "q_tied": [],
                        "q_ind": [], "worlds_ind": 0, "unproposed_ind": 0, "cond_tied": ""})
        # the c-table says "safe under every reading", asks nothing, and the operator meant an unsafe one
        row["silent_unsafe"] = row["verdict_tied"] == "safe_all" and not row["intended_safe"]
        # the c-table says "unsafe under every reading" while the operator meant a safe one
        row["silent_false_alarm"] = row["verdict_tied"] == "unsafe_all" and row["intended_safe"]
        rows.append(row)
    return rows


def agg(rows):
    n = len(rows)
    return {
        "requests": n,
        "valid_rate": sum(r["n_valid"] for r in rows) / sum(r["n"] for r in rows),
        "miss_intended": sum(not r["covered"] for r in rows) / n,
        "miss_intended_count": sum(not r["covered"] for r in rows),
        "slot_miss": sum((not r["slot0_covered"]) + (not r["slot1_covered"]) for r in rows) / (2 * n),
        "mean_distinct": sum(r["n_distinct"] for r in rows) / n,
        "silent_unsafe": sum(r["silent_unsafe"] for r in rows),
        "silent_false_alarm": sum(r["silent_false_alarm"] for r in rows),
        "some_tied": sum(r["verdict_tied"] == "some" for r in rows),
        "some_ind": sum(r["verdict_ind"] == "some" for r in rows),
        "spurious_some_ind": sum(r["verdict_ind"] == "some" and r["verdict_tied"] != "some" for r in rows),
        "question_differs": sum(r["q_ind"] != r["q_tied"] for r in rows),
        "requests_with_unproposed": sum(r["unproposed_ind"] > 0 for r in rows),
        "unproposed_worlds_total": sum(r["unproposed_ind"] for r in rows),
        "worlds_ind_total": sum(r["worlds_ind"] for r in rows),
        "questions_tied_total": sum(len(r["q_tied"]) for r in rows),
        "questions_ind_total": sum(len(r["q_ind"]) for r in rows),
    }


def menu_baseline(reqs):
    """Readings from a fixed per-type menu instead of the model: every plausible combination."""
    some = 0
    qsum = 0
    for q in reqs:
        fam, slots = q["family"], q["slots"]
        p = [FAMILIES[fam]["slots"][s]["plausible"] for s in slots]
        worlds = list(product(*p))
        t = ctable.build(slots, worlds, "tied")
        is_safe = lambda w, fam=fam: safe(fam, w)
        some += ctable.verdict(t, is_safe) == "some"
        qsum += len(ctable.question(t, is_safe))
    return {"requests": len(reqs), "some": some, "questions_total": qsum}


def type_coverage(by, settings, reqs):
    """Share of the plausible readings of each ambiguity type that the samples ever produced."""
    hit = defaultdict(int)
    tot = defaultdict(int)
    for q in reqs:
        good = [r for r in readings_for(by, settings, q["id"], K) if valid(r)]
        for i, name in enumerate(q["slots"]):
            spec = FAMILIES[q["family"]]["slots"][name]
            seen = {r[i] for r in good}
            for v in spec["plausible"]:
                tot[spec["type"]] += 1
                hit[spec["type"]] += v in seen
    return {t: {"plausible": tot[t], "seen": hit[t], "share_seen": hit[t] / tot[t]} for t in sorted(tot)}


def main():
    by = load_samples()
    reqs = requests()
    groups = {"A_t07": ["A_t07"], "B_t10": ["B_t10"], "C_para": ["C_para"], "D_3b": ["D_3b"],
              "A+C+D": ["A_t07", "C_para", "D_3b"]}
    summary = {"k": K, "settings": {}, "curves": {}, "type_coverage": {}, "menu_baseline": menu_baseline(reqs)}
    all_rows = []
    for g, ss in groups.items():
        rows = score(by, ss, K, reqs)
        if rows is None:
            print(f"[analyze] {g}: incomplete, skipped")
            continue
        summary["settings"][g] = {"label": LABEL[g], **agg(rows)}
        summary["type_coverage"][g] = type_coverage(by, ss, reqs)
        curve = []
        for k in range(1, K + 1):
            rk = score(by, ss, k, reqs)
            curve.append(agg(rk)["miss_intended"])
        summary["curves"][g] = curve
        for r in rows:
            all_rows.append({"group": g, **{k: (json.dumps(v) if isinstance(v, list) else v) for k, v in r.items()}})
    with open(os.path.join(ROOT, "results", "summary.json"), "w") as f:
        json.dump(summary, f, indent=1)
    if all_rows:
        with open(os.path.join(ROOT, "results", "per_request.csv"), "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(all_rows[0].keys()))
            w.writeheader()
            w.writerows(all_rows)

    # Figure 1: miss rate of the intended reading vs samples per setting
    fig, ax = plt.subplots(figsize=(5.6, 3.4))
    marks = {"A_t07": "o", "B_t10": "s", "C_para": "^", "D_3b": "D", "A+C+D": "x"}
    for g, curve in summary["curves"].items():
        n = len(groups[g])
        xs = [k * n for k in range(1, K + 1)]
        ax.plot(xs, [100 * c for c in curve], marker=marks[g], ms=4, color=COL[g], label=LABEL[g])
    ax.set_xlabel("samples per request")
    ax.set_ylabel("intended reading missing (%)")
    ax.set_ylim(0, 100)
    ax.grid(alpha=0.3)
    ax.legend(fontsize=7, frameon=False, ncol=2, loc="upper center", bbox_to_anchor=(0.5, -0.22))
    fig.tight_layout()
    fig.savefig(os.path.join(ROOT, "figures", "fig1_miss_vs_k.pdf"))

    # Figure 2: independent c-variables vs tied global condition
    gs = [g for g in groups if g in summary["settings"]]
    if gs:
        fig, ax = plt.subplots(figsize=(5.6, 2.8))
        x = range(len(gs))
        w = 0.38
        a = [summary["settings"][g]["questions_tied_total"] for g in gs]
        b = [summary["settings"][g]["questions_ind_total"] for g in gs]
        ax.bar([i - w / 2 for i in x], a, w, color="#0072B2", label="tied (global condition)")
        ax.bar([i + w / 2 for i in x], b, w, color="#E69F00", hatch="//", label="independent c-variables")
        ax.set_xticks(list(x))
        ax.set_xticklabels(["A: 1.5B T=0.7", "B: 1.5B T=1.0", "C: paraphrased", "D: 3B T=0.7", "pool A+C+D"][:len(gs)] if len(gs) == 5 else gs, fontsize=7)
        ax.set_ylabel("settings asked about\n(sum over 40 requests)")
        ax.legend(fontsize=7, frameon=False, ncol=2, loc="lower center", bbox_to_anchor=(0.5, 1.0))
        ax.grid(axis="y", alpha=0.3)
        fig.tight_layout()
        fig.savefig(os.path.join(ROOT, "figures", "fig2_tied_vs_independent.pdf"))
    # LaTeX macros for the note, so every number in it comes from this file
    def mac(name, val):
        return "\\newcommand{\\%s}{%s}\n" % (name, val)
    tex = ""
    tags = {"A_t07": "A", "B_t10": "B", "C_para": "C", "D_3b": "D", "A+C+D": "P"}
    for g, s in summary["settings"].items():
        t = tags[g]
        tex += mac(f"miss{t}", f"{100 * s['miss_intended']:.0f}")
        tex += mac(f"missN{t}", s["miss_intended_count"])
        tex += mac(f"valid{t}", f"{100 * s['valid_rate']:.0f}")
        tex += mac(f"silent{t}", s["silent_unsafe"])
        tex += mac(f"falsealarm{t}", s["silent_false_alarm"])
        tex += mac(f"wrongsilent{t}", s["silent_unsafe"] + s["silent_false_alarm"])
        tex += mac(f"slotmiss{t}", f"{100 * s['slot_miss']:.0f}")
        tex += mac(f"someTied{t}", s["some_tied"])
        tex += mac(f"someInd{t}", s["some_ind"])
        tex += mac(f"spurious{t}", s["spurious_some_ind"])
        tex += mac(f"qdiff{t}", s["question_differs"])
        tex += mac(f"unpropReq{t}", s["requests_with_unproposed"])
        tex += mac(f"unpropW{t}", s["unproposed_worlds_total"])
        tex += mac(f"worldsInd{t}", s["worlds_ind_total"])
        tex += mac(f"qTied{t}", s["questions_tied_total"])
        tex += mac(f"qInd{t}", s["questions_ind_total"])
        tex += mac(f"distinct{t}", f"{s['mean_distinct']:.1f}")
        c = summary["curves"][g]
        tex += mac(f"missOne{t}", f"{100 * c[0]:.0f}")
    for g, t in (("A_t07", "A"), ("A+C+D", "P")):
        tc = summary["type_coverage"].get(g, {})
        for typ, v in tc.items():
            tex += mac("cov%s%s" % (t, typ.replace("_", "")), f"{100 * v['share_seen']:.0f}")
    mb = summary["menu_baseline"]
    tex += mac("menuSome", mb["some"]) + mac("menuQ", mb["questions_total"])
    with open(os.path.join(ROOT, "results", "numbers.tex"), "w") as f:
        f.write(tex)
    print(json.dumps({g: {k: v for k, v in s.items() if k != "label"} for g, s in summary["settings"].items()}, indent=1))
    print("menu:", summary["menu_baseline"])


if __name__ == "__main__":
    main()
