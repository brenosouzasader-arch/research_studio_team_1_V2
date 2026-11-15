"""Battery types the user can compare. LFP is the default.

Only the two chemistries that are well studied and on sale for buildings today are here: LFP and NMC.
Sodium-ion, vanadium flow and second-life car batteries were removed on 15 Nov 2026: we found no
checkable performance numbers for them at building size, so most of their rows were guesses.

Every number has a source or is marked ASSUMPTION. The sources are listed in docs/SOURCES.md
under "Batteries"; the short name in brackets points to that list.

What each field means:
- capex_eur_per_kwh   installed cost per nameplate kWh, including inverter and fitting
- round_trip          share of the energy put in that comes back out (0.85 = 15% lost)
- cycle_life          full charge-discharge cycles before the battery is worn out
- calendar_years      years before it is worn out even if little used
- usable_share        share of the nameplate kWh we let the controller use (depth of discharge)
- c_rate              maximum charge or discharge power per kWh (0.5 = a 2-hour battery)
- om_share_per_year   yearly upkeep as a share of the installed cost
- notes               what a user should know (materials, safety, maturity)

Battery life used by the tool = the shorter of calendar_years and cycle_life / cycles per year,
so a battery that cycles every day wears out sooner (step 08 adds the replacement cost).
"""

LFP_CAPEX_EUR_PER_KWH = 195.0   # 999 EUR / 5.12 kWh nominal = 195 EUR per nameplate kWh. One shop price, tax included,
                                # for a home-size unit (Deye SE-G5.1 Pro-B, 5.12 kWh nominal, 4.6 kWh usable), without
                                # installation or inverter [tienda-solar.es product page, read 15 Nov 2026].
                                # ASSUMPTION for a 20-500 kWh building battery: commercial systems add installation and
                                # an inverter but get volume discounts, so the real price could be higher or lower.
                                # Breno asked for an average of shop prices; only this one price could be read
                                # (the category page lists no products to the fetch tool). Replace with a Barcelona quote.

TYPES = {
    "lfp": {
        "label": "Lithium iron phosphate (LFP), the default",
        "capex_eur_per_kwh": LFP_CAPEX_EUR_PER_KWH,
        "round_trip": 0.85,              # [NREL ATB 2024] "85% as a representative round-trip efficiency"
        "cycle_life": 2400,              # [PNNL 2022] "cycle life at 80% DOD for LFP ... 2,400"
        "calendar_years": 15,            # [NREL ATB 2024] "15-year lifetime" (PNNL 2022 says 16)
        "usable_share": 0.8,             # [PNNL 2022] the cycle life above is quoted at 80% depth of discharge
        "c_rate": 0.5,                   # ASSUMPTION: 2-hour battery, one of NREL ATB's standard durations
        "om_share_per_year": 0.025,      # [NREL ATB 2024] fixed O&M "2.5% of the capital costs"
        "notes": "Most used chemistry for stationary storage since 2021 [NREL ATB 2024]. "
                 "No cobalt or nickel.",
    },
    "nmc": {
        "label": "Lithium nickel manganese cobalt (NMC)",
        "capex_eur_per_kwh": LFP_CAPEX_EUR_PER_KWH * 435 / 385,   # [PNNL 2022] 100 MW 4 h: NMC 435 vs LFP 385 USD/kWh
        "round_trip": 0.85,              # [NREL ATB 2024] same value for both lithium-ion types
        "cycle_life": 1520,              # [PNNL 2022] "1,520 cycles" at 80% DOD
        "calendar_years": 13,            # [PNNL 2022] "13 years for NMC"
        "usable_share": 0.8,             # [PNNL 2022] cycle life quoted at 80% DOD
        "c_rate": 0.5,                   # ASSUMPTION, as LFP
        "om_share_per_year": 0.025,      # [NREL ATB 2024]
        "notes": "Smaller and lighter than LFP but shorter-lived here, and uses cobalt and nickel.",
    },
}

DEFAULT = "lfp"


def get(name=DEFAULT):
    if name not in TYPES:
        raise SystemExit(f"Unknown battery type '{name}'. Choose from: {', '.join(TYPES)}")
    return {"name": name, **TYPES[name]}


def life_years(battery, cycles_per_year):
    """Years until replacement: worn out by age or by use, whichever comes first."""
    by_use = battery["cycle_life"] / cycles_per_year if cycles_per_year > 0 else float("inf")
    return min(battery["calendar_years"], by_use)
