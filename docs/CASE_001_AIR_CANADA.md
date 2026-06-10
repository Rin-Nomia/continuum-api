# Case #001: AI Authorization Boundary Failure — Air Canada
## How an AI chatbot created legal liability by crossing a policy boundary

---

## Part 1: What Happened

In November 2022, a passenger asked Air Canada's chatbot about bereavement fares after a family death.

The chatbot told him he could apply for a refund within 90 days of travel — even after the trip was completed.

This was wrong. Air Canada's actual policy did not allow retroactive refund applications.

The passenger trusted the chatbot, paid full price, and later applied for the refund. Air Canada refused.

**The court ruling (February 2024):**
The British Columbia Civil Resolution Tribunal ruled that Air Canada was liable for its chatbot's statements.

The court rejected Air Canada's argument that the chatbot was a "separate legal entity."

Air Canada was ordered to pay the fare difference, interest, and legal fees.

**The core finding:**
The company is responsible for everything its AI says — not just its human agents.

---

## Part 2: Why Traditional Fixes Don't Solve This

Most teams respond to incidents like this by:

- Improving the prompt
- Updating the knowledge base
- Adding more RAG context
- Fine-tuning the model

**The problem remains:**

None of these approaches tell the system when it has crossed from providing information into making an unauthorized commitment on behalf of the company.

The Air Canada chatbot didn't hallucinate a random fact.

It generated a plausible, confident response — based on real policy fragments — that happened to cross an authorization boundary.

A better model would make the same mistake more convincingly.

---

## Part 3: Where Continuum Intervenes
AI is about to make a statement about refund eligibility
↓
Policy Boundary Risk detected
(response contains financial commitment language)
↓
Governance Decision: GUIDE
↓
Automatic commitment stopped
Conversation transferred to human agent
↓
Decision record created
Full audit evidence stored

**What this prevents:**
The AI never delivers an unauthorized refund promise.
The human agent handles the edge case with full context.
The company retains a complete governance record of the interaction.

---

## Part 4: Governance Value

**Accountability**
Every AI interaction that approaches a policy boundary is logged.
The company can demonstrate what the system did — and did not — commit to.

**Governance**
Authorization boundaries are defined before deployment, not discovered after an incident.
The system knows what it is — and is not — permitted to say.

**Enforcement**
When a response crosses the boundary threshold, intervention happens before the output reaches the user.
Not after.

---

## Key Insight

Air Canada's problem was not that AI said the wrong thing.

It was that AI didn't know it was approaching a boundary it wasn't authorized to cross.

Continuum doesn't make AI smarter.

It tells AI where it is not allowed to go — and enforces that boundary in real time.

---

*Case source: Moffatt v. Air Canada, 2024 BCCRT 149*
