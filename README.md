# NPS Rolling Returns

**This project is retired for now.**

It is paused and is not being maintained. The results may be wrong. Do not use them for investment decisions.

## Why it is retired: problems with the data source

Checked on 28 September 2026, on all 282 schemes from [npsnav.in](https://npsnav.in). The last price in that data was 25/09/2026.

The app reads daily scheme prices from npsnav.in. That site is unofficial. It is not the official NPS Trust or PFRDA source. There is no guarantee it stays available, or that the prices on it are right.

**Bad one-day prices that reverse the next day.** A price is wrong for a single day, then snaps back the next day. Examples:

- 04/11/2016, on 51 schemes. SBI Scheme E went 19.12, then 16.72, then 19.15.
- 02/10/2020 (a market holiday), on 47 schemes.
- 03/04/2020, on 18 schemes.
- 06/04/2025 (a Sunday), on 14 schemes.
- Aditya Birla Scheme E on 02/04/2020 jumps +38%, then falls 31% the next day.

Effect example: SBI Scheme E, 1-year lump sum starting 04/11/2016, shows 39.72%, versus about 21–22% for the days either side.

**Closed or merged schemes show a fake flat price of 10.0000 and still look live.**

- Scheme A Tier I (10 managers) drops to 10.0000 on 17/01/2026.
- Scheme A Tier II, UTI Corporate CG, and ICICI and HDFC NPS Lite have been flat for years.
- Max Life data stops on 17/04/2025.

Effect: SBI Scheme A, 1-year SIP for 2024–2026, shows a made-up worst of −79.64%. UTI Corporate CG, 3-year lump sum, shows 0.00% for all 2,120 periods.

**Scheme names do not cleanly identify the tier, the type, or the plan.** Regular/POP, GS, and Direct versions share names. Because of that, 49 of 282 schemes cannot be selected in the current app, and some are filed under the wrong tier or type.

**The site can be slow or unreachable.** The first load can hang for about a minute.

## What it did

It calculated rolling SIP and lump-sum returns for NPS schemes, and it could compare up to 3 funds.

## It may come back

The project may come back if a reliable official data source is used.

## Disclaimer

This project is for education only. It is not financial advice.

## Credit

Created by Nijeeth Muniyandi.

The code and these docs were generated with AI tools.

## License

MIT License. Copyright (c) 2026 Nijeeth Muniyandi. See [LICENSE](LICENSE).
