"""Synthetic ambiguous smart-home requests.

Each family is one small deployment with two settings ("slots") that a plain-English
request leaves open, plus one safety property that the operator cares about.
Each request is one phrasing of that family, with the reading I assigned as the
operator's intent. The intended labels are my own choices, written so that some
requests mean the less common reading on purpose (that is the case the coverage
worry is about). The plausible list per slot is the menu of readings I would accept
as reasonable for that kind of vagueness.

Slot kinds:
  enum - one of a fixed list of strings
  int  - an integer (minutes, degrees F, hours)
  time - a clock time HH:MM (24h)
"""

FAMILIES = {
    "fire_alarm": {
        "devices": "smoke sensor (reports low, mid or high), alarm siren, hall light",
        "slots": {
            "smoke_min": {"kind": "enum", "values": ["low", "mid", "high"],
                          "plausible": ["low", "mid", "high"], "type": "threshold"},
            "alarm_hours": {"kind": "enum", "values": ["all_day", "night_only"],
                            "plausible": ["all_day", "night_only"], "type": "scope"},
        },
        "property": "the alarm sounds for mid smoke at 14:00",
        "requests": [
            ("Sound the alarm when there is real smoke, and at night turn on the hall light too.", ("mid", "all_day")),
            ("At night, if there's real smoke, sound the alarm and turn on the hall light.", ("mid", "all_day")),
            ("If there's a lot of smoke at night, sound the alarm.", ("high", "night_only")),
            ("Sound the alarm for any serious smoke. Hall light only at night.", ("high", "all_day")),
            ("Whenever smoke shows up after dark, sound the alarm and light the hall.", ("low", "all_day")),
        ],
    },
    "sprinkler": {
        "devices": "smoke sensor (reports low, mid or high), sprinkler zones: kitchen, living_room, server_closet",
        "slots": {
            "smoke_min": {"kind": "enum", "values": ["low", "mid", "high"],
                          "plausible": ["mid", "high"], "type": "threshold"},
            "zones": {"kind": "enum", "values": ["kitchen_only", "all_zones"],
                      "plausible": ["kitchen_only", "all_zones"], "type": "scope"},
        },
        "property": "the server closet is never sprayed unless smoke is high",
        "requests": [
            ("Turn on the sprinklers if there's a real fire in the kitchen.", ("high", "kitchen_only")),
            ("Run the sprinklers when there's heavy smoke.", ("high", "all_zones")),
            ("If smoke is detected, turn on the sprinklers.", ("mid", "kitchen_only")),
            ("Sprinklers on whenever the smoke gets bad.", ("mid", "kitchen_only")),
            ("Use the sprinklers everywhere if there's smoke.", ("mid", "all_zones")),
        ],
    },
    "door_lock": {
        "devices": "front door smart lock, presence sensor (knows when everyone has left)",
        "slots": {
            "lock_delay_min": {"kind": "int", "plausible": [1, 5, 10, 15, 30], "type": "duration"},
            "lock_hours": {"kind": "enum", "values": ["always", "night_only"],
                           "plausible": ["always", "night_only"], "type": "scope"},
        },
        "property": "the door locks within 10 minutes after everyone leaves at 15:00",
        "requests": [
            ("Lock the front door a little while after everyone leaves.", (10, "always")),
            ("When we all leave, lock the door soon after.", (5, "always")),
            ("Lock up at night once everyone is gone for a bit.", (10, "always")),
            ("If nobody's home for a while, lock the front door.", (30, "always")),
            ("Make sure the door locks after we leave in the evening.", (5, "night_only")),
        ],
    },
    "night_light": {
        "devices": "hallway motion sensor, hallway light, all other lights",
        "slots": {
            "night_start": {"kind": "time", "plausible": ["19:00", "20:00", "21:00", "22:00", "23:00"], "type": "time_window"},
            "lights": {"kind": "enum", "values": ["hallway", "all_lights"],
                       "plausible": ["hallway", "all_lights"], "type": "scope"},
        },
        "property": "the hallway light turns on for motion at 21:30",
        "requests": [
            ("At night, turn on the lights when there's motion in the hallway.", ("21:00", "hallway")),
            ("Late at night, motion in the hall should turn on the light.", ("23:00", "hallway")),
            ("After dark, if someone walks by, turn on the lights.", ("19:00", "all_lights")),
            ("In the evening, turn the hallway light on with motion.", ("20:00", "hallway")),
            ("When it's bedtime, motion should switch on the lights.", ("22:00", "hallway")),
        ],
    },
    "stove": {
        "devices": "smart stove plug, kitchen presence sensor, home presence sensor",
        "slots": {
            "auto_off_min": {"kind": "int", "plausible": [10, 15, 20, 30, 60], "type": "duration"},
            "home_exception": {"kind": "enum", "values": ["off_even_if_home", "only_if_nobody_home"],
                               "plausible": ["off_even_if_home", "only_if_nobody_home"], "type": "exception"},
        },
        "property": "the stove turns off within 30 minutes when nobody is in the kitchen, even if someone is elsewhere in the house",
        "requests": [
            ("Turn the stove off if it's left on for a while with no one around.", (30, "off_even_if_home")),
            ("If I forget the stove, shut it off after a bit.", (15, "off_even_if_home")),
            ("Turn off the stove when the kitchen is empty for too long, unless someone's home.", (30, "only_if_nobody_home")),
            ("Kill the stove if nobody's watching it for a while.", (20, "off_even_if_home")),
            ("Shut the stove off if we leave it on and walk away.", (10, "off_even_if_home")),
        ],
    },
    "water_leak": {
        "devices": "leak sensors in basement and kitchen, main water valve, phone notifications",
        "slots": {
            "valve_action": {"kind": "enum", "values": ["close_valve", "notify_only"],
                             "plausible": ["close_valve", "notify_only"], "type": "action"},
            "sensors": {"kind": "enum", "values": ["basement_only", "all_sensors"],
                        "plausible": ["basement_only", "all_sensors"], "type": "scope"},
        },
        "property": "a kitchen leak closes the main valve",
        "requests": [
            ("If there's a leak, deal with it.", ("close_valve", "all_sensors")),
            ("Let me know about any leaks and stop the water if it's bad.", ("close_valve", "all_sensors")),
            ("Handle leaks downstairs.", ("close_valve", "basement_only")),
            ("If water is detected, take care of it.", ("close_valve", "all_sensors")),
            ("Watch for leaks and tell me.", ("notify_only", "all_sensors")),
        ],
    },
    "space_heater": {
        "devices": "space heater plug, room thermometer (degrees F)",
        "slots": {
            "off_temp_f": {"kind": "int", "plausible": [70, 72, 75, 78, 80], "type": "threshold"},
            "max_hours": {"kind": "int", "plausible": [1, 2, 4, 8], "type": "duration"},
        },
        "property": "the heater turns off by 78 F and never runs more than 4 hours",
        "requests": [
            ("Turn the heater off when it gets too warm, and don't let it run forever.", (75, 4)),
            ("Keep the room cozy but shut the heater off if it gets hot.", (78, 4)),
            ("Run the heater until it's comfortable, but not for too long.", (72, 2)),
            ("Heater off once it's warm. Don't leave it on all night.", (75, 4)),
            ("Make sure the heater doesn't overheat the room or run too long.", (80, 8)),
        ],
    },
    "garage": {
        "devices": "garage door opener, garage door open/closed sensor",
        "slots": {
            "close_after_min": {"kind": "int", "plausible": [5, 10, 15, 20, 30], "type": "duration"},
            "close_hours": {"kind": "enum", "values": ["always", "night_only"],
                            "plausible": ["always", "night_only"], "type": "scope"},
        },
        "property": "the garage closes within 20 minutes if left open at 16:00",
        "requests": [
            ("Close the garage if it's left open for a while.", (15, "always")),
            ("If the garage stays open at night, close it.", (15, "always")),
            ("Don't let the garage sit open too long.", (10, "always")),
            ("Close the garage door after a bit if we forget.", (20, "always")),
            ("Shut the garage in the evening if it's still open.", (30, "night_only")),
        ],
    },
}


def _hm(s):
    h, m = s.split(":")
    return int(h) * 60 + int(m)


def safe(family, reading):
    """True if the safety property holds under this reading (a tuple of slot values)."""
    a, b = reading
    if family == "fire_alarm":
        return a in ("low", "mid") and b == "all_day"
    if family == "sprinkler":
        return b == "kitchen_only" or a == "high"
    if family == "door_lock":
        return b == "always" and isinstance(a, int) and a <= 10
    if family == "night_light":
        return isinstance(a, str) and ":" in a and _hm(a) <= _hm("21:30") and _hm(a) >= _hm("12:00")
    if family == "stove":
        return isinstance(a, int) and a <= 30 and b == "off_even_if_home"
    if family == "water_leak":
        return a == "close_valve" and b == "all_sensors"
    if family == "space_heater":
        return isinstance(a, int) and isinstance(b, int) and a <= 78 and b <= 4
    if family == "garage":
        return b == "always" and isinstance(a, int) and a <= 20
    raise KeyError(family)


def requests():
    """Flat list of requests: dicts with id, family, text, slots, intended."""
    out = []
    for fam, spec in FAMILIES.items():
        for i, (text, intended) in enumerate(spec["requests"]):
            out.append({"id": f"{fam}-{i}", "family": fam, "text": text,
                        "devices": spec["devices"], "slots": list(spec["slots"].keys()),
                        "intended": list(intended)})
    return out
