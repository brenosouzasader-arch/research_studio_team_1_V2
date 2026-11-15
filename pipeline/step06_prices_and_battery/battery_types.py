"""Battery types the user can compare. LFP is the default.

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
so a battery that cycles every day wears out sooner (step 09 adds the replacement cost).
"""

LFP_CAPEX_EUR_PER_KWH = 500.0   # ASSUMPTION: no checkable European price for a 20-500 kWh building
                                # battery found yet. For scale: PNNL 2022 gives 385 USD/kWh for a
                                # 100 MW, 4-hour LFP plant (utility size, so cheaper per kWh) [PNNL 2022].

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
    "sodium_ion": {
        "label": "Sodium-ion",
        "capex_eur_per_kwh": LFP_CAPEX_EUR_PER_KWH * 0.8,   # [IEA GEVO 2024] "could cost up to 20% less" IF
                                                            # brought to scale: a best case, not today's price
        "round_trip": 0.85,              # ASSUMPTION: same as lithium-ion; no checkable figure found
        "cycle_life": 3000,              # ASSUMPTION: no checkable figure found
        "calendar_years": 12,            # ASSUMPTION: no checkable figure found
        "usable_share": 0.8,             # ASSUMPTION, as LFP
        "c_rate": 0.5,                   # ASSUMPTION, as LFP
        "om_share_per_year": 0.025,      # ASSUMPTION, as LFP
        "notes": "Needs no lithium [IEA GEVO 2024]. Production outside China is still at "
                 "laboratory or pilot scale [IEA GEVO 2024]. Performance numbers are placeholders.",
    },
    "vanadium_flow": {
        "label": "Vanadium redox flow",
        "capex_eur_per_kwh": LFP_CAPEX_EUR_PER_KWH * 385 / 356,   # [PNNL 2022] 100 MW 10 h: VRFB 385 vs LFP 356 USD/kWh
        "round_trip": 0.675,             # [PNNL 2020] literature 65-80%; model assumes 67.5% (2020)
        "cycle_life": 10000,             # [PNNL 2020] "almost all estimating ... 10,000 cycles and above"
        "calendar_years": 15,            # [PNNL 2020] "between 10 and 20 years"; we take the middle
        "usable_share": 1.0,             # ASSUMPTION: flow batteries can be fully discharged
        "c_rate": 0.25,                  # ASSUMPTION: flow batteries are usually 4-hour or longer
        "om_share_per_year": 0.025,      # ASSUMPTION, as LFP
        "notes": "Electrolyte essentially does not degrade; membranes and electrodes may need "
                 "replacing every 10 years [PNNL 2020]. Large and heavy: needs a plant room, not a roof. "
                 "Loses more energy per cycle than lithium.",
    },
    "second_life_ev": {
        "label": "Second-life electric-car batteries",
        "capex_eur_per_kwh": LFP_CAPEX_EUR_PER_KWH * 0.5,   # [Dong 2023] "20%-80% of new batteries"; we take 50%
        "round_trip": 0.80,              # ASSUMPTION: "lower roundtrip efficiency" than new [Dong 2023], no figure
        "cycle_life": 2000,              # ASSUMPTION: no checkable figure found
        "calendar_years": 7,             # [NREL 2015] "3-10 year second use lifetimes"; we take 7
        "usable_share": 0.55,            # [Dong 2023] "50%-60% DOD" for second-life packs
        "c_rate": 0.5,                   # ASSUMPTION, as LFP
        "om_share_per_year": 0.025,      # ASSUMPTION, as LFP
        "notes": "Re-uses car batteries that kept about 70-80% of their capacity [NREL 2015, Dong 2023]: "
                 "the greenest option, but each pack is different and life is uncertain.",
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
