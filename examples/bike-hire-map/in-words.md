# How Harbourside Bike Hire works, and what is missing

**The decision:** How does Harbourside Bike Hire work today, and what is missing?

A small Python prototype holds bikes by date and size and records returns. The documented web flow is not wired up here. Holds never expire, availability ignores bike status, and records disappear when the process stops. Proposed changes below are suggestions, not implemented features.

**How to read this:** Use Today and Side by side to compare the existing functions with the proposed workflow. Open boxes for code evidence; gaps contain user stories and completion checks. Role notes are assistant-authored review prompts.

_Checked against the sources on 2026-10-02. Checked against commit e3a7a50 of ._

## How it works

Existing code and documented human steps, followed by a proposed working service.

### What changes

7 changed.

- **Changed:** Choose a date and bike size → Use a booking page with clear pickup terms
- **Changed:** Choose the first matching bike without a hold → Reserve only a usable bike with an atomic check
- **Changed:** Keep the hold in process memory → Save bookings and expire abandoned holds
- **Changed:** Take payment at the counter → Record arrival and counter payment
- **Changed:** Mark a bike as out → Allow staff to check out a valid booking
- **Changed:** Mark a bike as in; record damage on paper → Report damage and block the bike until repaired
- **Changed:** No reminder is sent → Send a reminder with customer permission

### Booking through return
Follow the visitor, booking rules, records and staff handoffs.

1. [Visitor] **Choose a date and bike size** (Partly there) (today only)
  > “A small web app where visitors book a bike for the day and staff check bikes in and out.” — README.md, README.md:3 [readme]
  > “    bike = hold_bike(date, size, minutes=HOLD_MINUTES)” — src/booking/app.py, src/booking/app.py:9 [hold]
2. [Booking rules] **Choose the first matching bike without a hold** (Partly there) (today only)
  > “        if s == size and (date, bike) not in HOLDS:” — src/booking/store.py, src/booking/store.py:9 [availability]
  > “    bike = hold_bike(date, size, minutes=HOLD_MINUTES)” — src/booking/app.py, src/booking/app.py:9 [hold]
3. [Bike records] **Keep the hold in process memory** (Partly there) (today only)
  > “            HOLDS[(date, bike)] = minutes” — src/booking/store.py, src/booking/store.py:10 [duration]
  > “HOLDS = {}” — src/booking/store.py, src/booking/store.py:3 [memory]
4. [Staff] **Take payment at the counter** (Partly there) (today only)
  > “    return {"ok": True, "bike": bike, "pay": "at the counter"}” — src/booking/app.py, src/booking/app.py:12 [pay]
5. [Staff] **Mark a bike as out** (Partly there) (today only)
  > “    STATUS[bike] = "out"” — src/booking/store.py, src/booking/store.py:16 [out]
6. [Staff] **Mark a bike as in; record damage on paper** (Partly there) (today only)
  > “    STATUS[bike] = "in"” — src/booking/store.py, src/booking/store.py:21 [in]
  > “    # TODO: no way to record damage here; staff use a paper list.” — src/booking/app.py, src/booking/app.py:20 [damage]
7. [Scheduled work] **No reminder is sent** (Missing) (today only)
  > “- Staff would like a text reminder the evening before, and a way to report damage on a phone.” — docs/staff-notes.md, docs/staff-notes.md:5 [request]
  > “- "About one booking in five never shows up on a sunny Saturday." (shift lead)” — docs/staff-notes.md, docs/staff-notes.md:3 [no_show]
8. [Visitor] **Use a booking page with clear pickup terms** (Planned) (planned)
  > “A small web app where visitors book a bike for the day and staff check bikes in and out.” — README.md, README.md:3 [readme]
9. [Booking rules] **Reserve only a usable bike with an atomic check** (Planned) (planned)
  > “        if s == size and (date, bike) not in HOLDS:” — src/booking/store.py, src/booking/store.py:9 [availability]
10. [Bike records] **Save bookings and expire abandoned holds** (Planned) (planned)
  > “            HOLDS[(date, bike)] = minutes” — src/booking/store.py, src/booking/store.py:10 [duration]
11. [Staff] **Record arrival and counter payment** (Planned) (planned)
  > “    return {"ok": True, "bike": bike, "pay": "at the counter"}” — src/booking/app.py, src/booking/app.py:12 [pay]
12. [Staff] **Allow staff to check out a valid booking** (Planned) (planned)
  > “    STATUS[bike] = "out"” — src/booking/store.py, src/booking/store.py:16 [out]
13. [Staff] **Report damage and block the bike until repaired** (Planned) (planned)
  > “    # TODO: no way to record damage here; staff use a paper list.” — src/booking/app.py, src/booking/app.py:20 [damage]
14. [Scheduled work] **Send a reminder with customer permission** (Planned) (planned)
  > “- Staff would like a text reminder the evening before, and a way to report damage on a phone.” — docs/staff-notes.md, docs/staff-notes.md:5 [request]
- **UX designer note (Should decide): Booking terms.** The README says a day booking but the hold lasts 15 minutes in name only.
  We suggest: Explain when the visitor must arrive.
  Question: When should a reservation become a confirmed day booking?
  > “    bike = hold_bike(date, size, minutes=HOLD_MINUTES)” — src/booking/app.py, src/booking/app.py:9 [hold]
- **Lead engineer note (Should decide): Build order.** Allocation currently ignores status and never releases holds.
  We suggest: Fix allocation and expiry, then persistence and screens.
  Question: Which booking failure should be covered first?
  > “            HOLDS[(date, bike)] = minutes” — src/booking/store.py, src/booking/store.py:10 [duration]
  > “        if s == size and (date, bike) not in HOLDS:” — src/booking/store.py, src/booking/store.py:9 [availability]
- **Architect note (Should decide): Consistent records.** Separate dictionaries do not coordinate reservations and bike state.
  We suggest: Use one durable transactional store.
  Question: What overlapping hire periods must availability support?
  > “HOLDS = {}” — src/booking/store.py, src/booking/store.py:3 [memory]
  > “        if s == size and (date, bike) not in HOLDS:” — src/booking/store.py, src/booking/store.py:9 [availability]
- **AI agent teammate note (Should decide): Safe automation.** Expired holds could be released automatically once the policy is agreed.
  We suggest: Automate expiry; leave repair clearance to staff.
  Question: Which bike changes must always require a staff decision?
  > “            HOLDS[(date, bike)] = minutes” — src/booking/store.py, src/booking/store.py:10 [duration]
  > “    # TODO: no way to record damage here; staff use a paper list.” — src/booking/app.py, src/booking/app.py:20 [damage]
- **Security and privacy note (Should decide): Staff access and contact data.** The functions have no authorization boundary; reminders would require contact data.
  We suggest: Define staff access and collect only needed contact details.
  Question: Who should be allowed to change bike condition?
  > “    STATUS[bike] = "out"” — src/booking/store.py, src/booking/store.py:16 [out]
  > “- Staff would like a text reminder the evening before, and a way to report damage on a phone.” — docs/staff-notes.md, docs/staff-notes.md:5 [request]
- **Product manager note (Should decide): Prioritize damage handling.** Damage is recorded on paper and cannot block booking.
  We suggest: Prioritize usable inventory before reminders.
  Question: Should damage blocking be the first release?
  > “    # TODO: no way to record damage here; staff use a paper list.” — src/booking/app.py, src/booking/app.py:20 [damage]
  > “- Staff would like a text reminder the evening before, and a way to report damage on a phone.” — docs/staff-notes.md, docs/staff-notes.md:5 [request]
- **Business analyst note (Should decide): Measure no-shows.** The one-in-five figure is a staff estimate for sunny Saturdays.
  We suggest: Record arrivals and cancellations before comparing results.
  Question: What will count as a no-show?
  > “- "About one booking in five never shows up on a sunny Saturday." (shift lead)” — docs/staff-notes.md, docs/staff-notes.md:3 [no_show]
- **Customer voice note (Should decide): Helpful reminders.** Staff want reminders the evening before.
  We suggest: Agree useful reminder content with customers.
  Question: What information would help customers arrive on time?
  > “- Staff would like a text reminder the evening before, and a way to report damage on a phone.” — docs/staff-notes.md, docs/staff-notes.md:5 [request]

## Gaps between today and planned

### expiry: Holds never expire (impact 5/5, effort 2/5)
As a visitor, I want abandoned holds released so I can book an available bike.

- As a visitor, I want abandoned holds released so I can book an available bike.
  - Done when: A hold has an expiry timestamp.
  - Done when: After 15 minutes an abandoned hold becomes available.
  - Done when: A confirmed booking survives temporary hold expiry.

### inventory: Availability ignores bike condition and checkout state (impact 5/5, effort 3/5)
As staff, I want only usable bikes offered so customers receive safe bikes.

- As staff, I want only usable bikes offered so customers receive safe bikes.
  - Done when: An unavailable or damaged bike cannot be booked.
  - Done when: Concurrent requests cannot reserve the same bike for overlapping use.
  - Done when: Returning a damaged bike blocks future allocation until repair is recorded.

### durable: Records disappear on restart (impact 5/5, effort 3/5)
As staff, I want durable bookings so a restart does not lose reservations.

- As staff, I want durable bookings so a restart does not lose reservations.
  - Done when: Bookings and bike state survive a process restart.
  - Done when: Reservation and status changes commit together or fail together.

### checks: No automated tests or setup manifest (impact 4/5, effort 2/5)
As a maintainer, I want repeatable checks so booking changes do not break availability.

- As a maintainer, I want repeatable checks so booking changes do not break availability.
  - Done when: Setup and launch dependencies are documented.
  - Done when: Checks cover expiry, persistence, concurrent allocation, damaged bikes and invalid staff actions.

### web: The documented web flow is not implemented (impact 4/5, effort 4/5)
As a visitor or staff member, I want usable screens to complete the booking workflow.

- As a visitor or staff member, I want usable screens to complete the booking workflow.
  - Done when: A documented command starts the app from a fresh checkout.
  - Done when: A visitor can choose a date and size and see success or no availability.
  - Done when: Only authorized staff can change bike state.
  - Done when: Invalid dates, sizes, identifiers and state transitions are rejected.

### reminders: No reminders or arrival tracking (impact 3/5, effort 3/5)
As a visitor, I want a reminder so I remember my booking.

- As a visitor, I want a reminder so I remember my booking.
  - Done when: Pickup time and hold policy are defined before scheduling reminders.
  - Done when: Consenting customers receive one reminder at the agreed time.
  - Done when: Failed sends are visible to staff without duplicate delivery.
  - Done when: Arrival and no-show counts are measured; staff estimates remain labeled as estimates.

## Questions to decide

### Should decide
- When should a reservation become a confirmed day booking? (UX designer, on Use a booking page with clear pickup terms)
- What overlapping hire periods must availability support? (Architect, on Save bookings and expire abandoned holds)
- What will count as a no-show? (Business analyst, on Send a reminder with customer permission)
- Which booking failure should be covered first? (Lead engineer, on Reserve only a usable bike with an atomic check)
- Should damage blocking be the first release? (Product manager, on Report damage and block the bike until repaired)
- Who should be allowed to change bike condition? (Security and privacy, on Allow staff to check out a valid booking)
- What information would help customers arrive on time? (Customer voice, on Send a reminder with customer permission)
- Which bike changes must always require a staff decision? (AI agent teammate, on Save bookings and expire abandoned holds)

## Sources

- [s0] README.md (document)
- [s1] src/booking/app.py (code)
- [s2] src/booking/store.py (code)
- [s3] docs/staff-notes.md (document)

## Who is speaking

- **UX designer**: Will people understand this and find their way without help?
- **Architect**: Do the parts fit together, and what breaks if one changes?
- **Business analyst**: Is it clear what must be true, for whom, and how we will measure it?
- **Lead engineer**: What is the smallest safe order to build this in, and how do we test it?
- **Product manager**: Is this the right thing to do next, and what would we cut?
- **Security and privacy**: Who can see or change this, and what happens to the data?
- **Customer voice**: Would the people who use it notice, and would they care?
- **AI agent teammate**: Which steps could an agent do safely, and which need a person's OK?
