import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from ctable_readings import ctable
from ctable_readings.dataset import FAMILIES, requests, safe
from ctable_readings.parse import INVALID, norm_time, parse_reading

SLOTS = ["smoke_min", "alarm_hours"]


def fire(w):
    return safe("fire_alarm", w)


def test_agreement_becomes_constant():
    t = ctable.build(SLOTS, [("mid", "all_day"), ("high", "all_day")], "tied")
    assert t.cells[1] == "all_day"
    assert [c.name for c in t.cvars] == ["smoke_min"]


def test_independent_adds_unproposed_combinations():
    # Two samples that disagree on both settings.
    r = [("mid", "night_only"), ("low", "all_day")]
    ind = ctable.build(SLOTS, r, "independent")
    tied = ctable.build(SLOTS, r, "tied")
    assert len(ind.worlds()) == 4
    assert len(tied.worlds()) == 2
    assert set(ctable.unproposed(ind)) == {("low", "night_only"), ("mid", "all_day")}
    assert ctable.unproposed(tied) == []


def test_global_condition_changes_the_question():
    # Both proposed readings break the property, so with the tie there is nothing
    # to ask: the request is unsafe under every sampled reading. Independent
    # variables invent ('mid','all_day'), which is safe, and so a question appears.
    r = [("high", "all_day"), ("mid", "night_only")]
    ind = ctable.build(SLOTS, r, "independent")
    tied = ctable.build(SLOTS, r, "tied")
    assert ctable.verdict(tied, fire) == "unsafe_all"
    assert ctable.question(tied, fire) == []
    assert ctable.verdict(ind, fire) == "some"
    assert ctable.question(ind, fire) == ["smoke_min", "alarm_hours"]


def test_single_question_when_one_setting_flips_it():
    r = [("mid", "all_day"), ("mid", "night_only")]
    t = ctable.build(SLOTS, r, "tied")
    assert ctable.verdict(t, fire) == "some"
    assert ctable.question(t, fire) == ["alarm_hours"]
    assert ctable.violation_condition(t, fire) == "^alarm_hours=night_only"


def test_safe_all_has_no_question():
    t = ctable.build(SLOTS, [("mid", "all_day"), ("low", "all_day")], "tied")
    assert ctable.verdict(t, fire) == "safe_all"
    assert ctable.question(t, fire) == []
    assert ctable.violation_condition(t, fire) == "false"


def test_parse_and_normalize():
    assert norm_time("10 PM") == "22:00"
    assert norm_time("21:30") == "21:30"
    assert norm_time("noon-ish") is None
    out = parse_reading("fire_alarm", 'Sure: {"smoke_min": "Mid", "alarm_hours": "all day"}')
    assert out == ("mid", "all_day")
    out = parse_reading("door_lock", '{"lock_delay_min": "5 minutes", "lock_hours": "weekends"}')
    assert out == (5, INVALID)
    assert parse_reading("fire_alarm", "no json here") is None


def test_dataset_shape():
    qs = requests()
    assert len(qs) == 40
    for q in qs:
        spec = FAMILIES[q["family"]]["slots"]
        assert len(q["intended"]) == len(spec) == 2
        for v, (name, s) in zip(q["intended"], spec.items()):
            assert v in s["plausible"], (q["id"], name, v)
    # every family has at least one safe and one unsafe plausible reading
    for fam, spec in FAMILIES.items():
        p = [s["plausible"] for s in spec["slots"].values()]
        vs = {safe(fam, (a, b)) for a in p[0] for b in p[1]}
        assert vs == {True, False}, fam


def test_parse_nested_and_comments():
    t = '```json\n{\n  "lock_delay_min": 15,  // 15 minutes\n  "lock_hours": "night_only"\n}\n```'
    assert parse_reading("door_lock", t) == (15, "night_only")
    t = '[{"device": "smoke sensor", "smoke_min": "high"}, {"device": "siren", "alarm_hours": "all_day"}]'
    assert parse_reading("fire_alarm", t) == ("high", "all_day")
    t = '{"night_start": "22:00", "lights": ["hallway", "all_lights"]}'
    assert parse_reading("night_light", t) == ("22:00", INVALID)
