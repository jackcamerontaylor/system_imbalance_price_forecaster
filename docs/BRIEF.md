# Project brief

Build a day-ahead System Imbalance Price (SIP) forecaster from the supplied data.

- Output: a forecast for **each half-hour of a given day D**, made at **07:00** and at **09:00 UK
  time on D-1**. (A production system would run every half-hour from midnight and would also have a
  real-time variant; two run times keep this scoped.)
- SIP: the price (£/MWh, per half-hour) used to settle residual energy not settled in other markets.
- Targets: `imbalance_price` files. Candidate features: the other files (see
  `candidate_data/README.md`). Source formats differ.
- Python; script / notebook / package all fine.
- Scope: roughly 2 hours of effort (up to 4). The emphasis is on how the project is started and
  directed, not on a polished or highly accurate model. Results may be modest given public-only data.
- Deliverables: code and relevant outputs.
