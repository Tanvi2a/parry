"""The five features. Everything comes from the merchant-visible case file;
rc_base_rate constants are learned from the TRAIN split at training time
and frozen into the model bundle -- inference never touches labels."""
import math

FEATURES = ["completeness", "contradictions", "auth_ok",
            "log_prior_orders", "rc_base_rate"]


def extract(cf, completeness_score, rc_base_rates, contradiction_count=0):
    a, cu = cf["auth"], cf["customer"]
    rc = cf["dispute"]["reason_code"]
    auth_ok = 1.0 if (a["otp_result"] == "passed"
                      and a["device_known"] == 1) else 0.0
    return [float(completeness_score), float(contradiction_count), auth_ok,
            math.log1p(cu["prior_orders"]),
            rc_base_rates.get(rc, rc_base_rates["__overall__"])]
