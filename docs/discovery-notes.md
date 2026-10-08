# Discovery notes — Healthcare

## Scenario (paste the brief verbatim)

> Healthcare: A health system strategy team wants a tool that generates a structured briefing for
> a given medical condition, covering the current standard of care, emerging treatments in
> development, and key companies/institutions involved.

## 1. Problem → _Problem Statement_

- Who is the end user (a role, not "users")? What do they do today without this?
  - A strategy team at a health system; one user, who is a strategist.
  - The strategist comes into an interface, asks the tool about a given medical condition and its standard of care, and the response comes back.
  - What they do today: (not discussed)
- What does it cost when they get it wrong or slow today?
  - (not discussed)

## 2. Evidence → _Evidence_

- What tells us this is real: a quote, a ticket theme, a number? Or is it an assumption?
  - (not discussed)

## 3. Why build it → _Thesis_

- Why now? Why would they switch from how they cope today?
  - (not discussed)

## 4. The bet → _Hypothesis_

- What would the user do differently if this works? What one signal says "it's working"? What says "it isn't"?
  - RIGHT if: (not discussed)
  - WRONG if: (not discussed)

## 5. User and job → _Target User & JTBD_

- When does the user reach for this (the trigger)? Who is it explicitly **not** for?
  - When … (trigger not discussed) the strategist enters a medical condition and gets a briefing with a very clear format: what the condition is, the treatment and development, and who is involved around the treatment.
  - Not for: (not discussed)

## 6. Smallest proof → _MVP_

- What is the one end-to-end question flow that, if it works, proves the idea? What's Release 2?
  - MVP: input is a medical condition; output is a briefing on the condition with the three sections from the scenario ("This is our product flow"):
    - What is the current standard of care?
    - What are the emerging treatments for that condition?
    - What are the key institutions involved?
  - MVP: generate sample data and make sure the tool works first; don't add everything in the beginning. If time runs out without a working slice, "that will be a no."
  - Release 2: (not discussed)

## 7. Success → _Success Metrics_

- What one metric says their life got easier? (metric · target · how measured)
  - (not discussed)

## 8. Out of scope → _Non-goals_

- (not discussed)

## 9. Constraints → feed `/plan-architecture` (not the PRD)

- **Data:** format, volume, update frequency, owner. May we use synthetic data for the prototype?
  - Synthetic data requested for this project.
  - Stakeholder concern: standard of care and emerging treatments need care around freshness and source credibility; synthetic documents may contradict what we have to show.
  - Response: because this is an MVP, keep data in-house and work from a sample golden dataset; create a set of already existing medical conditions.
  - Synthetic/sample data accepted for the prototype ("That's a good plan. Yeah, you can start.") ASSUMPTION
  - Volume: "a small controlled MVP corpus."
- **Cost of a wrong answer:** sets guardrail strictness and whether every answer needs a citation.
  - (not discussed)
- **PII / regulatory:** HIPAA, FINRA, internal-only? Sets redaction and hosting.
  - Asked about regulatory constraints. Stakeholder: "I can only give the scenario and the assumptions and everything. You can make that up."
- **Audience and latency:** internal or client-facing? How fast must it answer?
  - Internal, for the health system's strategy team. ASSUMPTION
  - Latency: (not discussed)
- **Trust:** what makes them use it: citations, confidence, escalation to a human?
  - Freshness and source credibility of standard-of-care and emerging-treatment content. ASSUMPTION
- **Existing systems:** must it sit next to something, or is greenfield fine today?
  - (not discussed)

## Open questions → _Open Questions_

- [ ] How will source records and metadata be structured? (Stakeholder: that determines whether hybrid retrieval is useful later; talk them through it during implementation.)
- [ ] How will content be tagged or chunked so the system can tell standard of care from emerging treatments and key institutions, rather than retrieving semantically similar but mixed evidence? (Answer so far: very simple assumptions, each chunk carries enough information as one unit; options kept open.)
- [ ] Which parts of the setup kit (discovery, technical spec, tickets, multiple agents) will the prototype actually use? Stakeholder's concern is the amount of orchestration. (Walked through by screen share; answer not recorded.)

## Unsorted

- Retrieval approach: retrieve standard of care, treatments and key institutions "rather than just sending everything to the LLM"; pgvector embedding search inside Supabase for anything needing semantic search or reasoning.
- Stakeholder asked why pgvector at all for a small corpus instead of structured lookup or full-text search. Answer: hybrid keyword + semantic search, since Supabase provides both. Stakeholder: "Using Supabase for both keyword retrieval and PG vector is a reasonable way to keep the stack consolidated. You can go ahead with that approach."
- Stakeholder: "You don't need to make any changes based on what I said. I'm not trying to steer you toward a particular implementation… I just want to understand the trade-off."
- Keyword search: applied to whatever data model is built, separately from it; options kept open.
- Process: overview of how the session will run, given by screen share.
