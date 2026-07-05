---
title: LGD Model
type: module
status: draft
aliases: [lgd, loss given default model, cure severity model]
tags: [engine, lgd]
sources:
  - ../knowledge/sources/ifrs9_credit_risk_notes.md
links:
  uses: [Loan Panel]
  derived-from: [IFRS9 Study Notes]
---

# LGD Model

**Draft stub — Day 2 deliverable.** Two-stage workout LGD per the notes §10: P(cure) ×
severity-given-write-off, fit on the panel's 15,147 realised `lgd_time` values (bimodal: 20.6%
exact cures, write-off hump above 0.4, 9.8% of values above 1 to be handled explicitly, not
silently clipped).
