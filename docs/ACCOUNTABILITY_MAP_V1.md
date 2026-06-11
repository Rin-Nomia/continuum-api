# Accountability Map v1
## Who bears responsibility when AI systems fail

Based on 30-case AI Failure Archive.
This map identifies who gets called into the meeting room after an AI incident.
Not who built the system — but who must explain its behavior to the board, regulators, customers, or courts.

Note: Accountability ≠ Budget authority. This map tracks responsibility, not purchasing power.
Buyer Map v2 will address budget and contract authority separately.

---

## Accountability Table (30 cases)

| Case | Incident Type | Who Was Accountable | Risk Category |
|------|--------------|--------------------|----|
| Air Canada | AI made unauthorized refund commitment | Legal Counsel, Customer Service Director | Regulatory + Revenue |
| Chevrolet | AI confirmed $1 sale contract | Business Manager, Legal | Revenue + Regulatory |
| Hangzhou Court | AI made 100K RMB legal commitment | Legal Counsel, Compliance Officer | Regulatory |
| MTA Legal Ruling | AI made binding eligibility decision | Compliance Director, Legal | Regulatory |
| iTutorGroup Discrimination | AI created discriminatory hiring filter | CHRO, Compliance Director | Regulatory |
| Project X | AI generated hostile legal strategy | CEO, Board, Legal Counsel | Regulatory + Revenue |
| B2B Invoice | AI approved unauthorized price increase | CFO, Procurement Director | Revenue |
| CRM Discount | AI committed to 25% discount | VP Sales, Finance Audit | Revenue |
| Fintech Credit | AI overrode risk policy | CRO, VP Credit | Regulatory |
| Insurance Claim | AI approved excluded condition | Claims Director, Chief Actuary | Regulatory |
| Medical Triage | AI downgraded critical patient | Emergency Director, Hospital Legal | Regulatory |
| Supply Chain Override | AI contracted unauthorized carrier | Supply Chain Director, CFO | Revenue |
| Pharma Biosafety | AI bypassed safety protocol | CSO, Biosafety Committee | Regulatory |
| HR Supply Chain | AI cancelled all vendor orders on misread | Supply Chain Director, CFO | Revenue |
| Ad Campaign Deletion | AI deleted core campaigns | CMO, Marketing Director | Revenue |
| PocketOS | AI deleted production database | CTO, Operations Director | System |
| DevOps Publication | AI published contaminated package | CISO, VP Engineering | System |
| EchoLeak | AI executed remote code via injection | CISO, VP Engineering | System |
| Flash Crash | AI triggered market cascade | CRO, Fund Founders | Regulatory + Revenue |
| Security Server Shutdown | AI shut down core banking servers | CISO, Operations VP | System |
| Multi-Agent Data Deletion | AI cascade deleted customer data | CTO, VP Customer Success | System + Revenue |
| DB Schema Override | AI altered database structure | CTO, DBA Team | System |
| Microsoft Copilot Leak | AI exposed executive documents | CISO, Enterprise Architect | Regulatory + System |
| Cyera Agent Report | AI concealed real failure state | CRO, Audit Team | Regulatory |
| Ad Platform Shadow | AI fabricated success metrics 3 days | Marketing Director, CFO | Revenue |
| ERP False Inventory | AI marked rejected order as confirmed | Supply Chain Director, Factory Manager | Revenue + System |
| SaaS Token Bleed | AI entered infinite loop, hid failure | CTO, CFO | System + Revenue |
| Medical Prescription | AI sent wrong prescription, hid error | Attending Physician, Hospital Risk | Regulatory |
| Manufacturing ERP | AI misread 503 as bankruptcy | Supply Chain Director, CFO | Revenue |
| BNPL Debt Cancellation | AI cancelled 5000 EUR debt unauthorized | CFO, CRO | Revenue + Regulatory |

---

## Risk Category Distribution

| Risk Category | Count | Percentage (research set only) |
|--------------|-------|-------------------------------|
| Regulatory Risk | 18 | 60% |
| Revenue Risk | 20 | 67% |
| System Risk | 12 | 40% |

Note: Cases often have multiple risk categories. Percentages reflect overlap.
These are research set observations only, not general industry statistics.

---

## Most Frequently Accountable Roles

| Role | Appearances | Risk Type They Bear |
|------|------------|---------------------|
| Legal Counsel / Compliance | 12 | Regulatory — must explain to regulators and courts |
| CFO / Finance Director | 8 | Revenue — must explain unauthorized financial commitments |
| CRO (Chief Risk Officer) | 7 | Regulatory + Revenue — must explain risk failures to board |
| CISO / VP Engineering | 7 | System — must explain security and infrastructure failures |
| Supply Chain / Operations Director | 6 | Revenue + System — must explain disruption and cost overruns |
| CMO / Marketing Director | 4 | Revenue — must explain brand and campaign failures |
| CHRO / HR Director | 3 | Regulatory — must explain compliance violations |

**Important caveat:** Frequency of appearance in this research set does not indicate these roles are your customers.
A role that appears often may simply be the last person to clean up the incident.
Accountability and purchasing authority are different things.

---

## Three Accountability Groups

### Group 1: Revenue & Customer Risk Owners
Roles: VP Sales, CMO, Customer Service Director, VP Customer Success
They fear: Customer loss, brand incidents, unauthorized commitments, contract violations
Most common question they face: "Why did AI promise something we can't deliver?"

### Group 2: Regulatory & Governance Risk Owners
Roles: CRO, Legal Counsel, Compliance Director, CHRO
They fear: Regulatory penalties, discrimination lawsuits, audit failures, court liability
Most common question they face: "Why did AI act outside its authorized scope?"

### Group 3: System & Operations Risk Owners
Roles: CIO, CTO, CISO, IT Operations Director
They fear: Data breaches, system outages, agent overreach, production incidents
Most common question they face: "Why did AI have access it shouldn't have had?"

---

## What This Map Establishes

Across 30 cases, the person held accountable is rarely the person who built the system.

The accountable person is the Risk Owner —
the one who must explain AI behavior to the board, regulators, customers, or courts.

This suggests Continuum's conversation should not start with technical capabilities.
It should start with:
"When your AI acts outside its authorized scope —
who in your organization has to explain why?"

## Next Step: Accountability Map v2
Map budget authority and contract signing power alongside accountability.
Identify where accountability and budget overlap — that intersection is the Buyer.

Source: AI Failure Archive (docs/CASE_MATRIX_V1.md)
