# Moving file uploads

**The decision:** Should we move customer file uploads to a new storage provider, change how uploads reach storage, or both?

A mid-size web team stores customers' files with one storage provider. Large uploads time out, and the transfer bill keeps growing. This map shows how an upload works today, what each option changes, and what the team still has to decide. All figures are made up.

_Checked against the sources on 2026-05-20. Checked against the incident review, a provider comparison and a team discussion._

## How an upload works

Each journey is a numbered path. Each column is the part of the system that does that step.

### Upload today
Every byte passes through our servers on its way to storage.

1. [Customer] **Customer picks a file and presses Upload** (Works today)
  Checked 2026-05-18.
2. [Web app] **Browser sends the whole file to our servers** (Works today)
  Pain: No progress bar; a dropped connection starts again. Checked 2026-05-18.
  > “Customers ask for a progress bar and the ability to resume after a dropped connection.” — Team discussion, Product manager, from support tickets [E8]
3. [Our servers] **Our servers pass the bytes on to storage** (Partly there)
  Pain: Long uploads tie up servers. A moment that matters. Checked 2026-04-02.
  > “Uploads over 200 MB timed out for about 40 minutes.” — Incident review: slow uploads, Summary [E1]
  > “Half our servers were just shovelling bytes. Nothing else could get through.” — Incident review: slow uploads, On-call engineer [E2]
4. [Background jobs] **A job scans the file for viruses** (Works today)
  Checked 2026-05-18.
5. [Database] **File is marked ready and shown to the customer** (Works today)
  Checked 2026-05-18.
- **Designer note (For information): Tell people what is happening.** Today a big upload shows a spinner with no end.
  We suggest: Show bytes sent, time left, and a clear message if the connection drops.
  Question: Should a dropped upload resume by itself, or ask first?
  > “Customers ask for a progress bar and the ability to resume after a dropped connection.” — Team discussion, Product manager, from support tickets [E8]
- **Engineer note (Must decide): The proxy is the bottleneck.** Servers hold a connection for the whole upload. That is why everything slowed down.
  We suggest: Do direct uploads first; it is independent of the provider choice.
  Question: Do we agree to separate the two decisions: direct uploads now, provider later?
  > “Half our servers were just shovelling bytes. Nothing else could get through.” — Incident review: slow uploads, On-call engineer [E2]
  > “The real problem is the proxy, not the provider. Direct uploads fix the timeouts wherever the files live.” — Team discussion, Backend lead [E7]

### Upload with direct links (proposed)
The browser sends the file straight to storage using a short-lived signed link.

1. [Customer] **Customer picks a file and presses Upload** (Works today)
2. [Our servers] **Our servers check the customer may upload, and issue a signed link for one file** (Planned)
  > “Signed links must expire in minutes and only allow one file path.” — Team discussion, Security engineer [E9]
3. [Storage provider] **Browser uploads straight to storage in pieces, with a progress bar** (Planned)
  A moment that matters.
  > “The real problem is the proxy, not the provider. Direct uploads fix the timeouts wherever the files live.” — Team discussion, Backend lead [E7]
  > “Customers ask for a progress bar and the ability to resume after a dropped connection.” — Team discussion, Product manager, from support tickets [E8]
4. [Background jobs] **Storage tells us the upload finished; a job scans it** (Missing)
  Pain: Untested: scanning without the proxy.
  > “Nobody has tested how virus scanning works if files no longer pass through our servers.” — Team discussion, Open point [E10]
5. [Database] **File is marked ready only after a clean scan** (Planned)
- **Security and privacy note (Must decide): Signed links must be narrow.** A link that allows any path, or lasts hours, would let anyone write files into our storage.
  We suggest: Links last 10 minutes, cover one path, and set a size limit.
  Question: Is 10 minutes long enough for the slowest customers, given uploads resume in pieces?
  > “Signed links must expire in minutes and only allow one file path.” — Team discussion, Security engineer [E9]
- **Customer voice note (Should decide): Customers asked for two things.** A progress bar and resuming after a dropped connection. Neither needs a new provider.
  We suggest: Ship both with direct uploads, and tell the 31 customers who raised tickets.
  Question: Do we contact the customers who reported the problem when the fix ships?
  > “Support received 31 tickets. Most from customers uploading video.” — Incident review: slow uploads, Support [E4]
  > “Customers ask for a progress bar and the ability to resume after a dropped connection.” — Team discussion, Product manager, from support tickets [E8]
- **Security and privacy note (Must decide): Nothing is downloadable before it is scanned.** With direct uploads, a file lands in storage before we have looked at it.
  We suggest: Upload into a holding area; move it to the live area only after a clean scan.
  Question: Who builds and tests the holding area before the 5% trial?
  > “Nobody has tested how virus scanning works if files no longer pass through our servers.” — Team discussion, Open point [E10]

## Options

The outcome at the top, then the problems that stand in its way, the ideas for each, and the quick tests that would prove an idea.

- Outcome: **Big uploads always finish, and the transfer bill falls**: By the September budget review.
- **Product owner note (Should decide): Two outcomes, two clocks.** Timeouts hurt customers now. The bill matters by September.
  We suggest: Fix timeouts this month; decide the provider in July with test results in hand.
  Question: Is July the right month to make the provider decision?
  > “Uploads over 200 MB timed out for about 40 minutes.” — Incident review: slow uploads, Summary [E1]
  > “Our storage bill grew 22% last quarter, mostly from data transfer out, not storage.” — Incident review: slow uploads, Costs [E3]
  - Problem: **Large uploads time out** (Missing)
  > “Uploads over 200 MB timed out for about 40 minutes.” — Incident review: slow uploads, Summary [E1]
  > “Support received 31 tickets. Most from customers uploading video.” — Incident review: slow uploads, Support [E4]
    - Idea: **Direct uploads with signed links** (Planned)
  > “The real problem is the proxy, not the provider. Direct uploads fix the timeouts wherever the files live.” — Team discussion, Backend lead [E7]
      - Quick test: **Ship to 5% of video uploads for two weeks**: Compare failure rate and server load.
      - **Analyst note (Should decide): Say what the trial must show.** Without a target, a two-week trial cannot pass or fail.
        We suggest: Pass if failed uploads drop below 1% and no server spends more than 5% of its time on uploads.
        Question: Are those the right pass marks for the trial?
        > “Uploads over 200 MB timed out for about 40 minutes.” — Incident review: slow uploads, Summary [E1]
    - Idea: **Raise timeouts and add servers** (Works today): Cheap now, costly later.
      - Quick test: **Raise the idle timeout to 10 minutes on one server**: Watch for queueing.
  - Problem: **Data out costs keep growing** (Partly there)
  > “Our storage bill grew 22% last quarter, mostly from data transfer out, not storage.” — Incident review: slow uploads, Costs [E3]
  > “Data out: $90 per TB today; $0 to our CDN with provider B.” — Storage providers compared, Comparison table [E5]
  - **Finance note (Must decide): The bill problem is data out, not storage.** Storage grew a little; data out grew a lot.
    We suggest: Try CDN caching first; it is cheap and fast to test.
    Question: How much must data out fall by September for this to count as fixed?
    > “Our storage bill grew 22% last quarter, mostly from data transfer out, not storage.” — Incident review: slow uploads, Costs [E3]
    > “Data out: $90 per TB today; $0 to our CDN with provider B.” — Storage providers compared, Comparison table [E5]
    - Idea: **Move files to provider B** (Planned)
  > “Data out: $90 per TB today; $0 to our CDN with provider B.” — Storage providers compared, Comparison table [E5]
  > “Moving 180 TB at current transfer prices would cost about $16,000 once. Provider B offers free one-time transfer over 100 TB, on request.” — Storage providers compared, Notes under the table [E6]
    - **Engineer note (Should decide): Nobody has run provider B.** Four years of experience with the current provider; none with B.
      We suggest: Run the one-month copy test before committing.
      Question: Are we willing to run two providers for a few months during the move?
      > “Moving 180 TB at current transfer prices would cost about $16,000 once. Provider B offers free one-time transfer over 100 TB, on request.” — Storage providers compared, Notes under the table [E6]
      - Quick test: **Copy one month of new files to B and serve them through the CDN**: Measure the bill and download speed.
    - Idea: **Cache popular downloads at the CDN** (Missing)
      - Quick test: **Turn on caching for public files only**: One week, then compare data out.

## Gaps between today and planned

### G1: Direct uploads with a progress bar and resume (impact 5/5, effort 3/5)
Fixes the timeouts no matter which provider we use.

- As a customer uploading a large video on a weak connection, I want the upload to resume where it stopped, so I do not start again.
  - Done when: a 2 GB upload survives a 30-second disconnect
  - Done when: the progress bar matches the bytes received
  - Done when: our servers handle no file bytes

### G2: Scan files that never touch our servers (impact 4/5, effort 2/5)
Today scanning assumes we saw the upload.

- As the security engineer, I want every upload scanned before anyone can download it, so direct uploads add no risk.
  - Done when: a file is not downloadable until its scan passes
  - Done when: an infected test file is quarantined and the customer is told

### G3: Move existing files to provider B (impact 3/5, effort 4/5)
Cuts the data-out bill; only worth it if the free transfer is granted.

- As finance, I want the move to cost nothing up front, so the saving shows before the September review.
  - Done when: provider B confirms free transfer in writing
  - Done when: every file's checksum matches after the copy
  - Done when: downloads switch over with no broken links
- **Finance note (Should decide): Only move if the transfer is free.** At $16,000, the move pays back in about seven months. Free transfer makes it pay back at once.
  We suggest: Ask provider B for free transfer in writing before deciding.
  Question: Who asks provider B, and by when?
  > “Moving 180 TB at current transfer prices would cost about $16,000 once. Provider B offers free one-time transfer over 100 TB, on request.” — Storage providers compared, Notes under the table [E6]
- **AI agent teammate note (For information): An assistant can check the copy.** Comparing checksums for millions of files is repetitive and easy to get wrong by hand.
  We suggest: Let an agent run and report the checksum comparison; a person signs off the switch-over.
  Question: Who signs off the switch-over once the agent's report is clean?
  > “Moving 180 TB at current transfer prices would cost about $16,000 once. Provider B offers free one-time transfer over 100 TB, on request.” — Storage providers compared, Notes under the table [E6]

## Questions to decide

### Must decide
- Do we agree to separate the two decisions: direct uploads now, provider later? (Engineer, on Our servers pass the bytes on to storage)
- Is 10 minutes long enough for the slowest customers, given uploads resume in pieces? (Security and privacy, on Our servers check the customer may upload, and issue a signed link for one file)
- Who builds and tests the holding area before the 5% trial? (Security and privacy, on Storage tells us the upload finished; a job scans it)
- How much must data out fall by September for this to count as fixed? (Finance, on Data out costs keep growing)

### Should decide
- Who asks provider B, and by when? (Finance, on Move existing files to provider B)
- Are we willing to run two providers for a few months during the move? (Engineer, on Move files to provider B)
- Do we contact the customers who reported the problem when the fix ships? (Customer voice, on Browser uploads straight to storage in pieces, with a progress bar)
- Is July the right month to make the provider decision? (Product owner, on Big uploads always finish, and the transfer bill falls)
- Are those the right pass marks for the trial? (Analyst, on Ship to 5% of video uploads for two weeks)

### For information
- Who signs off the switch-over once the agent's report is clean? (AI agent teammate, on Move existing files to provider B)
- Should a dropped upload resume by itself, or ask first? (Designer, on Browser sends the whole file to our servers)

## Decisions

### D1: Do we build direct uploads now, separately from the provider choice?
Status: Decided. Owner: Backend lead. Due: 2026-05-29. Decided by: Engineering lead.
Options: Yes, now; Wait for the provider decision.
What we decided: Yes. Direct uploads ship to 5% of video uploads in June.

### D2: Do we move to provider B?
Status: Open. Owner: Engineering lead. Due: 2026-07-15.
Options: Move all files; Move new files only; Stay, and add CDN caching.

### D3: How do signed links and scanning work?
Status: Open. Owner: Security engineer. Due: 2026-06-05.

## Did it work?

- **Failed large uploads** Before: About 6% during busy hours. Target: Below 1%. Not measured yet.

- **Data out cost per month** Before: Up 22% last quarter. Target: Down 30% by September. Not measured yet.

## Sources

- [S1] Incident review: slow uploads (document, 2026-05-04)
- [S2] Storage providers compared (data, 2026-05-12)
- [S3] Team discussion (meeting, 2026-05-15)

## Words we use

- **signed link**: A web address that lets one browser upload or download one file for a few minutes, without a password.
- **proxy**: When our servers pass every byte between the customer and storage, instead of the customer talking to storage directly.
- **resumable upload**: An upload sent in pieces, so a dropped connection only loses the last piece.
- **data out**: Files sent from storage to anyone outside it. Providers charge for this.

## Who is speaking

- **Designer**: Will people understand this and find their way without help?
- **Analyst**: Is it clear what must be true, for whom, and how we will measure it?
- **Engineer**: What do we build first, what could break, and how do we test it?
- **Product owner**: What is in the first version, what do we cut, and what does success look like?
- **Security and privacy**: Who can see what, what do we keep, and what happens if it leaks?
- **Customer voice**: Would the people we serve choose this, and would they need a manual?
- **AI agent teammate**: What can an agent do on its own, and what needs a person's OK?
- **Finance**: What does it cost to build and run, and when does it pay back?
