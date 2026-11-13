# Recommendations on the Track 2 roadmap

13 November 2026. The roadmap is clear, and the repository follows its 9 steps and file names. These are the changes we would make, most important first.

## 1. Settle the geography this week (the roadmap and the test-site research disagree)

The roadmap says the host is "in the existing nine-block study area" (Eixample). The test-site research points to Poblenou or UPC Campus Nord instead. The Week 1 gate needs a host **and** its hourly load, so pick by data, not by roof:

- **UPC Campus Nord**, if UPC answers the SIRENA data request by about 18 Nov. Real 15-minute data makes the AI step (05) real.
- **Poblenou (Quatre Cantons)**, if not. Use proxy load, but check steps 02-03 against CEP9's real roof (58.32 kWp, about 73,750 kWh a year).
- **Eixample** only as a fallback, because we already have its LiDAR and 197 ranked roofs, but no office meter data.

The code works for any of them (`sites/`), so this is a data decision, not a code one.

## 2. Drop "fixed beta" as the main community option, keep it as a baseline

In the offline demo (an office roof plus 4 made-up neighbours), a fixed share for the whole year **lost the owner 420 EUR a year compared with keeping it all**. The host's fixed share was only 24%, so on weekdays it bought back from the grid the power it had given away. The hourly shares gained 228 EUR a year over host-only. Under our business model (the owner keeps the panels and sells only surplus), fixed betas work against the owner. Keep them in the comparison, but make the hourly agreement the main proposal.

## 3. Answer the roadmap's open "objective" question

The roadmap lists maximising self-consumption, owner value, participant savings or a weighted mix. Our user is the owner, so we suggest: **maximise the owner's net value, as long as every participant saves money**. With the prices we use (own use 0.16 > sale 0.10 > export 0.05 EUR/kWh), that gives the same answer as maximising self-consumption, which keeps the optimizer simple and easy to explain.

## 4. Measure the AI by money, not only by error

The demo's hourly scenario reached 100% use because predicted use was treated as actual use. That is too optimistic. Betas must be agreed in advance from **predictions**, then tested against **real** use (step 07 has `--actual` for this). Report, for the baseline and the AI model:

- MAE / RMSE of the demand forecast (as the roadmap says), and
- the kWh and EUR lost because the betas were set from a forecast.

That links the AI directly to the investment decision, which is what the studio asks for.

## 5. Update the business-model line

The roadmap still lists "who pays the PV capex" as open. The team decided on 12 Nov that the owner pays and sells the surplus at a fixed price. Two legal points belong in the guardrails table:

- Whether the owner may charge participants a price inside collective self-consumption is still being checked.
- Above 100 kW the simplified surplus compensation does not apply (RD 244/2019 art. 4.2.a), so export is sold at market price. Large 22@ or campus roofs may be over this limit.

## 6. Count participants, not buildings

"3-5 candidate buildings" is a good scope. But each flat signs up separately (its own meter), and only some will (we assume 40%). A 20-flat building is up to 20 participants. Show both numbers in the report.

## 7. Small technical items for Week 1

- **Time zones:** the roadmap asks for explicit daylight-saving handling. The carried-over code approximates it (summer time April to October). Switch to `zoneinfo("Europe/Madrid")` and add the DST unit test the roadmap lists.
- **Meter years vs. the solar year:** done. Meter data from any year is moved into the solar year keeping weekdays (an office's Saturday stays a Saturday).
- **"Connect one live verified source through MCP":** pick a public one without a login, such as PVGIS or Open Data BCN, so it works in the demo.
