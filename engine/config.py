"""One place to read config/parry.yaml, with safe defaults."""
import pathlib

import yaml

CFG_PATH = pathlib.Path("config/parry.yaml")
DEFAULTS = dict(cost_to_fight_paise=65000, auto_submit_cap_paise=500000,
                p_win_floor=0.75, abstain_band=[0.45, 0.60],
                completeness_floor=0.8, seed=42)


def load():
    cfg = dict(DEFAULTS)
    if CFG_PATH.exists():
        loaded = yaml.safe_load(CFG_PATH.read_text()) or {}
        cfg.update({k: v for k, v in loaded.items() if v is not None})
    return cfg
