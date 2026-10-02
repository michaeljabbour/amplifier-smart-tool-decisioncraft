# Moving file uploads

**The decision:** Should we move customer file uploads to a new storage provider, change how uploads reach storage, or both?

A mid-size web team stores customers' files with one storage provider. Large uploads time out, and the transfer bill keeps growing. This map shows how an upload works today, what each option changes, and what the team still has to decide. All figures are made up.

**How to read this:** The first view, How an upload works, has six journeys: an upload today, the proposed direct upload, downloading and sharing, deleting, moving existing files, and what happens when something goes wrong. Each column is a part of the system, from the customer's browser on the left to the storage provider on the right, so you can see where each step happens. The second view, Options, starts from the outcome we want and branches into problems, ideas and quick tests. Turn on Show technical names in any box to see the services and settings involved. Notes from security, finance, support and others sit on the steps they are about.

_Checked against the sources on 2026-05-20. Checked against the incident review, April upload numbers, 31 support tickets, a provider comparison and call notes, the scanning and retention setup, and a team discussion._

## How an upload works

Five journeys from the customer's browser to the storage provider. Each column is the part of the system that does that step. The upload journey shows today and the plan in one.

### What changes

5 new · 4 changed · 1 goes away.

- **Changed:** Browser sends the whole file to our servers → Our servers check the customer may upload, and issue a signed link for one file
- **New:** A file record is created in 'uploading' state
- **Changed:** Our servers pass the bytes on to storage → Browser uploads straight to storage in pieces, with a progress bar
- **Goes away:** Long uploads hold a server connection open
- **Changed:** On weak wifi the upload fails and starts again from zero → If the connection drops, the upload resumes from the last piece
- **New:** Some office firewalls may block the storage address
- **New:** File lands in a holding area nobody else can read
- **New:** Storage tells us the upload finished; a job scans it
- **Changed:** If the scan fails, downloads are blocked → File is marked ready only after a clean scan
- **New:** Customer sees 'Ready' or a plain message if it was rejected

### Uploading a file
How an upload works today, and with direct links to storage. Use Today, Planned and What changes to read it.

1. [Customer] **Customer picks a file and presses Upload** (Works today)
  How it feels: Mixed.
2. [Web app] **Browser sends the whole file to our servers** (Works today) (today only)
  Pain: No progress bar; people cannot tell if it is stuck.
  > “Customers ask for a progress bar and the ability to resume after a dropped connection.” — Team discussion, Product manager, from support tickets [E8]
  > “Just show me how far along it is. I can't tell if it's stuck.” — Support tickets, sample of 31, Agency producer [E13]
3. [Our servers] **Our servers check the customer may upload, and issue a signed link for one file** (Planned) (planned)
  A moment that matters.
  > “Signed links must expire in minutes and only allow one file path.” — Team discussion, Security engineer [E9]
4. [Database] **A file record is created in 'uploading' state** (Planned) (planned)
5. [Our servers] **Our servers pass the bytes on to storage** (Partly there) (today only)
  A moment that matters.
  > “Uploads over 200 MB timed out for about 40 minutes.” — Incident review: slow uploads, Summary [E1]
  > “Half our servers were just shovelling bytes. Nothing else could get through.” — Incident review: slow uploads, On-call engineer [E2]
  > “Upload servers spend about 55% of their time passing bytes to storage.” — Upload numbers, April, Server time [E17]
6. [Storage provider] **Browser uploads straight to storage in pieces, with a progress bar** (Planned) (planned)
  How it feels: Good.
  > “The real problem is the proxy, not the provider. Direct uploads fix the timeouts wherever the files live.” — Team discussion, Backend lead [E7]
  > “Customers ask for a progress bar and the ability to resume after a dropped connection.” — Team discussion, Product manager, from support tickets [E8]
  > “Just show me how far along it is. I can't tell if it's stuck.” — Support tickets, sample of 31, Agency producer [E13]
7. [Our servers] **Long uploads hold a server connection open** (Partly there) (today only)
  Pain: Other customers' requests queue behind them.
  > “Half our servers were just shovelling bytes. Nothing else could get through.” — Incident review: slow uploads, On-call engineer [E2]
  > “Upload servers spend about 55% of their time passing bytes to storage.” — Upload numbers, April, Server time [E17]
8. [Customer] **On weak wifi the upload fails and starts again from zero** (Missing) (today only)
  A moment that matters. How it feels: Bad.
  > “I lost two hours re-uploading the same file three times.” — Support tickets, sample of 31, Wedding videographer [E12]
  > “Failure rate for uploads over 200 MB: 6.2% in busy hours, 1.4% at night.” — Upload numbers, April, Failures [E16]
9. [Customer] **If the connection drops, the upload resumes from the last piece** (Planned) (planned)
  A moment that matters.
  > “I lost two hours re-uploading the same file three times.” — Support tickets, sample of 31, Wedding videographer [E12]
  > “19 of 31 tickets were video uploads over 200 MB; 8 said it got to 90% and then failed.” — Support tickets, sample of 31, Ticket tags [E11]
10. [Customer] **Some office firewalls may block the storage address** (Missing) (planned)
  Pain: Schools and offices with strict firewalls.
  > “Our firewall blocks some sites. Will the new way still work here?” — Support tickets, sample of 31, School office [E14]
11. [Storage provider] **File lands in a holding area nobody else can read** (Planned) (planned)
  > “Signed links must expire in minutes and only allow one file path.” — Team discussion, Security engineer [E9]
  > “Files are shown to the customer before the scan finishes; downloads are blocked only if the scan fails.” — Scanning and retention setup, Scanning [E23]
12. [Database] **File record is saved and the file shown to the customer** (Works today)
  > “Files are shown to the customer before the scan finishes; downloads are blocked only if the scan fails.” — Scanning and retention setup, Scanning [E23]
13. [Background jobs] **Storage tells us the upload finished; a job scans it** (Missing) (planned)
  > “Nobody has tested how virus scanning works if files no longer pass through our servers.” — Team discussion, Open point [E10]
  > “Upload completion messages go to a web address we choose; they retry for 24 hours.” — Provider B call notes and draft terms, Notifications [E21]
  > “Scanning takes about 9 seconds under 100 MB and up to 4 minutes for 5 GB.” — Scanning and retention setup, Scanning [E24]
14. [Background jobs] **A job scans the file for viruses** (Works today)
  > “Scanning takes about 9 seconds under 100 MB and up to 4 minutes for 5 GB.” — Scanning and retention setup, Scanning [E24]
15. [Database] **If the scan fails, downloads are blocked** (Partly there) (today only)
  Pain: A bad file can be downloaded for up to 4 minutes.
  > “Files are shown to the customer before the scan finishes; downloads are blocked only if the scan fails.” — Scanning and retention setup, Scanning [E23]
16. [Database] **File is marked ready only after a clean scan** (Planned) (planned)
  > “Files are shown to the customer before the scan finishes; downloads are blocked only if the scan fails.” — Scanning and retention setup, Scanning [E23]
17. [Web app] **Customer sees 'Ready' or a plain message if it was rejected** (Planned) (planned)
- **Designer note (For information): Tell people what is happening.** Today a big upload shows a spinner with no end.
  We suggest: Show bytes sent, time left, and a clear message if the connection drops.
  Question: Should a dropped upload resume by itself, or ask first?
  > “Customers ask for a progress bar and the ability to resume after a dropped connection.” — Team discussion, Product manager, from support tickets [E8]
- **Security and privacy note (Must decide): Signed links must be narrow.** A link that allows any path, or lasts hours, would let anyone write files into our storage.
  We suggest: Links last 10 minutes, cover one path, and set a size limit.
  Question: Is 10 minutes long enough for the slowest customers, given uploads resume in pieces?
  > “Signed links must expire in minutes and only allow one file path.” — Team discussion, Security engineer [E9]
- **Analyst note (Should decide): One status field for every file.** Uploading, checking, ready and rejected must mean the same thing on every page.
  We suggest: Write the four states down and use them in the app, support page and alerts.
  Question: Do we need a separate state for files waiting on a fallback upload?
  > “Files are shown to the customer before the scan finishes; downloads are blocked only if the scan fails.” — Scanning and retention setup, Scanning [E23]
- **Engineer note (Must decide): The proxy is the bottleneck.** Servers hold a connection for the whole upload. That is why everything slowed down.
  We suggest: Do direct uploads first; it is independent of the provider choice.
  Question: Do we agree to separate the two decisions: direct uploads now, provider later?
  > “Half our servers were just shovelling bytes. Nothing else could get through.” — Incident review: slow uploads, On-call engineer [E2]
  > “The real problem is the proxy, not the provider. Direct uploads fix the timeouts wherever the files live.” — Team discussion, Backend lead [E7]
- **Customer voice note (Should decide): Customers asked for two things.** A progress bar and resuming after a dropped connection. Neither needs a new provider.
  We suggest: Ship both with direct uploads, and tell the 31 customers who raised tickets.
  Question: Do we contact the customers who reported the problem when the fix ships?
  > “Support received 31 tickets. Most from customers uploading video.” — Incident review: slow uploads, Support [E4]
  > “Customers ask for a progress bar and the ability to resume after a dropped connection.” — Team discussion, Product manager, from support tickets [E8]
- **Designer note (For information): Show time left, not just percent.** A producer could not tell whether the upload was stuck.
  We suggest: Show percent, speed and time left, updated every two seconds.
  Question: Is time left accurate enough on weak connections to show it?
  > “Just show me how far along it is. I can't tell if it's stuck.” — Support tickets, sample of 31, Agency producer [E13]
- **Customer voice note (Must decide): Starting again from zero is the real pain.** The videographer lost two hours re-uploading the same file; four tickets came from hotel or train wifi.
  We suggest: Make resume the first thing the trial measures.
  Question: Do we promise resume in the help pages before the trial ends?
  > “I lost two hours re-uploading the same file three times.” — Support tickets, sample of 31, Wedding videographer [E12]
  > “19 of 31 tickets were video uploads over 200 MB; 8 said it got to 90% and then failed.” — Support tickets, sample of 31, Ticket tags [E11]
- **Customer voice note (Should decide): Strict firewalls could lock some customers out.** A school office asked if the new way would work behind their firewall.
  We suggest: Keep the old path as a fallback and tell support how to spot it.
  Question: How long do we keep the old proxy path running as a fallback?
  > “Our firewall blocks some sites. Will the new way still work here?” — Support tickets, sample of 31, School office [E14]
- **Product owner note (For information): Keep the fallback small.** A permanent second upload path doubles what we support.
  We suggest: Keep the fallback for six months, then review who still uses it.
  Question: Who reviews the fallback numbers in six months?
  > “Our firewall blocks some sites. Will the new way still work here?” — Support tickets, sample of 31, School office [E14]
- **Security and privacy note (Must decide): Nothing is downloadable before it is scanned.** With direct uploads, a file lands in storage before we have looked at it.
  We suggest: Upload into a holding area; move it to the live area only after a clean scan.
  Question: Who builds and tests the holding area before the 5% trial?
  > “Nobody has tested how virus scanning works if files no longer pass through our servers.” — Team discussion, Open point [E10]
- **Engineer note (Must decide): We must answer completion messages quickly.** Provider B retries for 24 hours if we do not answer; slow answers cause duplicates.
  We suggest: Answer at once and do the scan in a background job; ignore duplicates by upload id.
  Question: Who owns the completion endpoint and its alerts?
  > “Upload completion messages go to a web address we choose; they retry for 24 hours.” — Provider B call notes and draft terms, Notifications [E21]
- **Designer note (Should decide): Say plainly why a file was rejected.** Customers see 'Error' today, which looks like our fault.
  We suggest: Show 'This file was blocked because it may contain a virus' and what to do next.
  Question: Do we tell free-plan users the scanner's reason, or only that it was blocked?
  > “Files are shown to the customer before the scan finishes; downloads are blocked only if the scan fails.” — Scanning and retention setup, Scanning [E23]

### Downloading and sharing
A customer or someone they share with downloads a file.

1. [Customer] **Customer clicks Download, or opens a share link** (Works today)
2. [Our servers] **Our servers check they may see the file** (Works today)
3. [Our servers] **Our servers make a signed download link** (Works today)
  > “Signed links must expire in minutes and only allow one file path.” — Team discussion, Security engineer [E9]
4. [Storage provider] **Storage sends the file to the browser** (Works today)
  Pain: This is where the bill grows.
  > “Data out: $90 per TB today; $0 to our CDN with provider B.” — Storage providers compared, Comparison table [E5]
  > “Our storage bill grew 22% last quarter, mostly from data transfer out, not storage.” — Incident review: slow uploads, Costs [E3]
5. [Storage provider] **Popular files could come from the CDN instead** (Missing)
  A moment that matters.
  > “18% of files are downloaded more than 10 times and make up 80% of data out.” — Upload numbers, April, Downloads [E18]
  > “Data out: $90 per TB today; $0 to our CDN with provider B.” — Storage providers compared, Comparison table [E5]
6. [Database] **We count the download** (Works today)
7. [Customer] **A file still being scanned cannot be downloaded** (Planned)
  > “Files are shown to the customer before the scan finishes; downloads are blocked only if the scan fails.” — Scanning and retention setup, Scanning [E23]
- **Finance note (Must decide): Every download costs money today.** $90 per TB of data out is most of the bill growth.
  We suggest: Measure data out per customer plan so we know who drives it.
  Question: Should heavy-download plans pay more?
  > “Data out: $90 per TB today; $0 to our CDN with provider B.” — Storage providers compared, Comparison table [E5]
  > “Our storage bill grew 22% last quarter, mostly from data transfer out, not storage.” — Incident review: slow uploads, Costs [E3]
- **Security and privacy note (Should decide): Never cache private files.** A cache mistake could show one customer's file to another.
  We suggest: Cache only files marked public or shared; check permission for everything else.
  Question: Who reviews the cache rules before the test?
  > “18% of files are downloaded more than 10 times and make up 80% of data out.” — Upload numbers, April, Downloads [E18]
- **Customer voice note (For information): A short wait to download is fine if it is explained.** Customers accept 'Checking' if they can see it.
  We suggest: Show 'Checking for viruses, usually under 15 seconds'.
  Question: Do we let the uploader download their own file before the scan?
  > “Files are shown to the customer before the scan finishes; downloads are blocked only if the scan fails.” — Scanning and retention setup, Scanning [E23]
  > “Scanning takes about 9 seconds under 100 MB and up to 4 minutes for 5 GB.” — Scanning and retention setup, Scanning [E24]

### Deleting a file
A customer deletes a file, or closes their account.

1. [Customer] **Customer deletes a file** (Works today)
2. [Database] **File is marked deleted and hidden** (Works today)
3. [Background jobs] **After 30 days a job removes it from storage** (Works today)
  > “Our terms promise deleted files are gone within 30 days, including backups.” — Scanning and retention setup, Retention [E25]
4. [Storage provider] **At provider B, deleted files sit in a recycle area for 7 more days** (Missing)
  A moment that matters.
  > “Provider B keeps deleted files 7 days in a recycle area unless turned off.” — Provider B call notes and draft terms, Deletes [E20]
  > “Our terms promise deleted files are gone within 30 days, including backups.” — Scanning and retention setup, Retention [E25]
5. [Storage provider] **During a move, the file may exist at both providers** (Missing)
  Pain: A deleted file could survive at the old provider.
  > “Our terms promise deleted files are gone within 30 days, including backups.” — Scanning and retention setup, Retention [E25]
6. [Background jobs] **Account closure deletes everything after 14 days** (Works today)
  > “Our terms promise deleted files are gone within 30 days, including backups.” — Scanning and retention setup, Retention [E25]
7. [Database] **We log that the file is gone** (Partly there)
- **Security and privacy note (Must decide): The recycle area breaks our deletion promise.** Provider B keeps deleted files 7 days unless it is turned off; our terms promise 30 days in total.
  We suggest: Turn the recycle area off, or purge 7 days early.
  Question: Which do we choose: turn it off, or purge early?
  > “Provider B keeps deleted files 7 days in a recycle area unless turned off.” — Provider B call notes and draft terms, Deletes [E20]
  > “Our terms promise deleted files are gone within 30 days, including backups.” — Scanning and retention setup, Retention [E25]

### Moving existing files to provider B
Copying 180 TB without customers noticing, if we decide to move.

1. [Our servers] **Ask provider B for free transfer in writing** (Missing)
  A moment that matters.
  > “Free one-time transfer needs a written request and approval, usually 2 to 3 weeks.” — Provider B call notes and draft terms, Transfer [E19]
  > “Moving 180 TB at current transfer prices would cost about $16,000 once. Provider B offers free one-time transfer over 100 TB, on request.” — Storage providers compared, Notes under the table [E6]
2. [Our servers] **Legal checks the new region against customer contracts** (Missing)
  > “Their EU region is in a different country from our current one. Legal must check our customer contracts.” — Provider B call notes and draft terms, Region [E22]
3. [Storage provider] **Create buckets at provider B with new names** (Planned)
  > “Bucket names at provider B are global; ours must be renamed.” — Provider B call notes and draft terms, Setup [E26]
4. [Background jobs] **Copy new uploads to both providers for a month** (Planned)
  > “Their onboarding team suggests writing new files to both providers for at least a month and comparing checksums on every file before switching reads.” — Provider B call notes and draft terms, Onboarding advice [E28]
5. [Background jobs] **Copy older files in batches overnight** (Planned)
  > “18% of files are downloaded more than 10 times and make up 80% of data out.” — Upload numbers, April, Downloads [E18]
6. [Background jobs] **Compare checksums for every file** (Planned)
  > “Their onboarding team suggests writing new files to both providers for at least a month and comparing checksums on every file before switching reads.” — Provider B call notes and draft terms, Onboarding advice [E28]
7. [Our servers] **Switch reads to provider B, then writes** (Planned)
8. [Storage provider] **Keep the old copy for 30 days, then delete it** (Planned)
  > “Our terms promise deleted files are gone within 30 days, including backups.” — Scanning and retention setup, Retention [E25]
- **Finance note (Should decide): No written transfer, no move.** Moving 180 TB costs about $16,000 without the free transfer.
  We suggest: Send the written request this week; it takes 2 to 3 weeks.
  Question: Who sends the request, and do we wait for it before any other work?
  > “Free one-time transfer needs a written request and approval, usually 2 to 3 weeks.” — Provider B call notes and draft terms, Transfer [E19]
  > “Moving 180 TB at current transfer prices would cost about $16,000 once. Provider B offers free one-time transfer over 100 TB, on request.” — Storage providers compared, Notes under the table [E6]
- **Security and privacy note (Must decide): A new country needs a legal check.** Provider B's EU region is in a different country, and some contracts name the country.
  We suggest: Ask legal for a list of affected customers before any copy starts.
  Question: Do we need to tell customers before their files move country?
  > “Their EU region is in a different country from our current one. Legal must check our customer contracts.” — Provider B call notes and draft terms, Region [E22]
- **Engineer note (Should decide): Dual writes double the risk of half-done uploads.** For a month every upload goes to two places.
  We suggest: Treat the old provider as the source of truth until the switch; log every mismatch.
  Question: Do we pause the move if mismatches pass 0.1%?
  > “Their onboarding team suggests writing new files to both providers for at least a month and comparing checksums on every file before switching reads.” — Provider B call notes and draft terms, Onboarding advice [E28]
- **AI agent teammate note (For information): Checksum reports are a good job for an agent.** Comparing 180 TB of checksums is long and repetitive.
  We suggest: Let an agent run the comparison and flag only mismatches.
  Question: Who acts on a mismatch: the agent, or a person?
  > “Their onboarding team suggests writing new files to both providers for at least a month and comparing checksums on every file before switching reads.” — Provider B call notes and draft terms, Onboarding advice [E28]
  > “Moving 180 TB at current transfer prices would cost about $16,000 once. Provider B offers free one-time transfer over 100 TB, on request.” — Storage providers compared, Notes under the table [E6]

### When something goes wrong
A storage outage, a stuck upload, or a missed completion message.

1. [Storage provider] **Storage provider has an outage** (Partly there)
  > “Uploads over 200 MB timed out for about 40 minutes.” — Incident review: slow uploads, Summary [E1]
2. [Web app] **Customer sees a plain message and their upload pauses** (Planned)
  > “I lost two hours re-uploading the same file three times.” — Support tickets, sample of 31, Wedding videographer [E12]
3. [Background jobs] **A completion message never arrives** (Missing)
  > “Upload completion messages go to a web address we choose; they retry for 24 hours.” — Provider B call notes and draft terms, Notifications [E21]
4. [Background jobs] **Stuck files are checked against storage and fixed or cleaned up** (Missing)
5. [Our servers] **On-call is alerted when large-upload failures pass 2%** (Missing)
  A moment that matters.
  > “Support received 31 tickets. Most from customers uploading video.” — Incident review: slow uploads, Support [E4]
  > “Failure rate for uploads over 200 MB: 6.2% in busy hours, 1.4% at night.” — Upload numbers, April, Failures [E16]
6. [Web app] **Support can see a customer's recent uploads and why they failed** (Missing)
  > “Support received 31 tickets. Most from customers uploading video.” — Incident review: slow uploads, Support [E4]
- **Analyst note (Should decide): Decide what counts as stuck.** Completion messages retry for 24 hours, so 'stuck' must be longer than that.
  We suggest: Call a file stuck after 26 hours in 'uploading'.
  Question: Is 26 hours too long for customers waiting on a file?
  > “Upload completion messages go to a web address we choose; they retry for 24 hours.” — Provider B call notes and draft terms, Notifications [E21]
- **AI agent teammate note (For information): An agent can clean up stuck uploads.** Checking each stuck record against storage is routine and rule-based.
  We suggest: Let an agent fix or remove stuck records nightly and post a summary.
  Question: Should the agent delete stuck records itself, or only list them for a person?
  > “Upload completion messages go to a web address we choose; they retry for 24 hours.” — Provider B call notes and draft terms, Notifications [E21]
- **Engineer note (Should decide): No alert today.** Support found the incident from tickets; nobody was paged.
  We suggest: Alert on large-upload failure rate, not on server errors alone.
  Question: What failure rate should wake someone at night?
  > “Support received 31 tickets. Most from customers uploading video.” — Incident review: slow uploads, Support [E4]
  > “Failure rate for uploads over 200 MB: 6.2% in busy hours, 1.4% at night.” — Upload numbers, April, Failures [E16]
- **AI agent teammate note (For information): An agent can draft the first support reply.** Most tickets ask the same three things.
  We suggest: Draft a reply from the customer's upload history for support to check and send.
  Question: Are we comfortable with an agent reading upload history to draft replies?
  > “Support received 31 tickets. Most from customers uploading video.” — Incident review: slow uploads, Support [E4]
  > “19 of 31 tickets were video uploads over 200 MB; 8 said it got to 90% and then failed.” — Support tickets, sample of 31, Ticket tags [E11]

## Options

The outcome at the top, then the problems that stand in its way, the ideas for each, and the quick tests that would prove an idea.

- Outcome: **Big uploads always finish, and the transfer bill falls**: By the September budget review.
- **Product owner note (Should decide): Two outcomes, two clocks.** Timeouts hurt customers now. The bill matters by September.
  We suggest: Fix timeouts this month; decide the provider in July with test results in hand.
  Question: Is July the right month to make the provider decision?
  > “Uploads over 200 MB timed out for about 40 minutes.” — Incident review: slow uploads, Summary [E1]
  > “Our storage bill grew 22% last quarter, mostly from data transfer out, not storage.” — Incident review: slow uploads, Costs [E3]
- **Finance note (For information): September is the deadline that matters.** Finance wants the bill down before the September review.
  We suggest: Plan so that caching or the move shows in the August bill.
  Question: Is the August bill the one we judge by?
  > “Finance wants the transfer bill down before the September budget review.” — Team discussion, Finance [E27]
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
Fixes the timeouts no matter which provider we use; uploads over 200 MB are 71% of all bytes.

- As a customer uploading a large video on a weak connection, I want the upload to resume where it stopped, so I do not start again.
  - Done when: a 2 GB upload survives a 30-second disconnect
  - Done when: the progress bar matches the bytes received
  - Done when: our servers handle no file bytes

- As a producer uploading a 4 GB video, I want to see how far along it is, so I know it is not stuck.
  - Done when: a progress bar shows percent and time left
  - Done when: it updates at least every 2 seconds

- As a school office behind a strict firewall, I want uploads to still work, so we are not locked out.
  - Done when: if the storage address cannot be reached within 5 seconds, the upload falls back to the old path
  - Done when: support can see which customers used the fallback

### G2: Scan files that never touch our servers (impact 4/5, effort 2/5)
Today scanning assumes we saw the upload, and a bad file can be downloaded for up to 4 minutes.

- As the security engineer, I want every upload scanned before anyone can download it, so direct uploads add no risk.
  - Done when: a file is not downloadable until its scan passes
  - Done when: an infected test file is quarantined and the customer is told

- As a customer, I want to know my file is being checked, so a short wait makes sense.
  - Done when: the file shows 'Checking' until the scan passes
  - Done when: files under 100 MB are ready within 15 seconds

### G4: Serve popular files from the CDN (impact 4/5, effort 2/5)
18% of files cause 80% of data out; caching them cuts the bill with either provider.

- As finance, I want popular downloads to stop counting as data out, so the bill falls before September.
  - Done when: public and shared files are served from the CDN
  - Done when: data out falls at least 30% in the first month

- As a security engineer, I want private files never cached, so nobody gets someone else's file.
  - Done when: only files marked public or shared go to the CDN
  - Done when: a private file request always checks permission first
- **Product owner note (Must decide): Caching may beat moving.** Caching popular files cuts most data out without moving anything.
  We suggest: Run the one-week caching test before deciding on provider B.
  Question: If caching cuts data out by 30%, do we still move?
  > “18% of files are downloaded more than 10 times and make up 80% of data out.” — Upload numbers, April, Downloads [E18]
  > “Data out: $90 per TB today; $0 to our CDN with provider B.” — Storage providers compared, Comparison table [E5]

### G5: Deletes reach every copy (impact 4/5, effort 2/5)
Our terms promise deleted files are gone within 30 days; provider B keeps a 7-day recycle area and a move means two copies.

- As a customer who deleted a file, I want it gone everywhere within 30 days, as the terms promise.
  - Done when: provider B's recycle area is off, or our purge runs 7 days early
  - Done when: deletes during the move go to both providers
  - Done when: a monthly check finds no deleted file older than 30 days

### G6: Know about failures before customers tell us (impact 3/5, effort 2/5)
Support found out about the 2 May incident from 31 tickets.

- As on-call, I want an alert when large uploads start failing, so I can act in minutes, not hours.
  - Done when: an alert fires when failures over 200 MB pass 2% for 10 minutes
  - Done when: the alert links to a page showing the failing step

- As support, I want to see a customer's recent uploads and why they failed, so I can answer the ticket.
  - Done when: a read-only page lists the last 20 uploads with status and error
  - Done when: it never shows file contents
- **Analyst note (For information): Measure the same thing before and after.** Failure rates differ a lot between busy hours and night.
  We suggest: Report busy-hour and night rates separately.
  Question: Do we judge the trial on busy-hour rates only?
  > “Failure rate for uploads over 200 MB: 6.2% in busy hours, 1.4% at night.” — Upload numbers, April, Failures [E16]

### G3: Move existing files to provider B (impact 3/5, effort 4/5)
Cuts the data-out bill; only worth it if the free transfer is granted.

- As finance, I want the move to cost nothing up front, so the saving shows before the September review.
  - Done when: provider B confirms free transfer in writing
  - Done when: every file's checksum matches after the copy
  - Done when: downloads switch over with no broken links

- As the engineering lead, I want to switch back within an hour, so a bad move does not become an outage.
  - Done when: reads and writes switch by one setting per customer group
  - Done when: a dry run of switching back is done before the move
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
- If caching cuts data out by 30%, do we still move? (Product owner, on Serve popular files from the CDN)
- Do we agree to separate the two decisions: direct uploads now, provider later? (Engineer, on Our servers pass the bytes on to storage)
- Do we promise resume in the help pages before the trial ends? (Customer voice, on On weak wifi the upload fails and starts again from zero)
- Who owns the completion endpoint and its alerts? (Engineer, on Storage tells us the upload finished; a job scans it)
- Is 10 minutes long enough for the slowest customers, given uploads resume in pieces? (Security and privacy, on Our servers check the customer may upload, and issue a signed link for one file)
- Which do we choose: turn it off, or purge early? (Security and privacy, on At provider B, deleted files sit in a recycle area for 7 more days)
- Do we need to tell customers before their files move country? (Security and privacy, on Legal checks the new region against customer contracts)
- Should heavy-download plans pay more? (Finance, on Storage sends the file to the browser)
- Who builds and tests the holding area before the 5% trial? (Security and privacy, on Storage tells us the upload finished; a job scans it)
- How much must data out fall by September for this to count as fixed? (Finance, on Data out costs keep growing)

### Should decide
- Who asks provider B, and by when? (Finance, on Move existing files to provider B)
- Are we willing to run two providers for a few months during the move? (Engineer, on Move files to provider B)
- How long do we keep the old proxy path running as a fallback? (Customer voice, on Some office firewalls may block the storage address)
- Do we tell free-plan users the scanner's reason, or only that it was blocked? (Designer, on Customer sees 'Ready' or a plain message if it was rejected)
- Do we need a separate state for files waiting on a fallback upload? (Analyst, on A file record is created in 'uploading' state)
- Is 26 hours too long for customers waiting on a file? (Analyst, on A completion message never arrives)
- Do we pause the move if mismatches pass 0.1%? (Engineer, on Copy new uploads to both providers for a month)
- What failure rate should wake someone at night? (Engineer, on On-call is alerted when large-upload failures pass 2%)
- Who reviews the cache rules before the test? (Security and privacy, on Popular files could come from the CDN instead)
- Who sends the request, and do we wait for it before any other work? (Finance, on Ask provider B for free transfer in writing)
- Do we contact the customers who reported the problem when the fix ships? (Customer voice, on Browser uploads straight to storage in pieces, with a progress bar)
- Is July the right month to make the provider decision? (Product owner, on Big uploads always finish, and the transfer bill falls)
- Are those the right pass marks for the trial? (Analyst, on Ship to 5% of video uploads for two weeks)

### For information
- Who signs off the switch-over once the agent's report is clean? (AI agent teammate, on Move existing files to provider B)
- Do we judge the trial on busy-hour rates only? (Analyst, on Know about failures before customers tell us)
- Is time left accurate enough on weak connections to show it? (Designer, on Browser uploads straight to storage in pieces, with a progress bar)
- Who reviews the fallback numbers in six months? (Product owner, on Some office firewalls may block the storage address)
- Should the agent delete stuck records itself, or only list them for a person? (AI agent teammate, on Stuck files are checked against storage and fixed or cleaned up)
- Are we comfortable with an agent reading upload history to draft replies? (AI agent teammate, on Support can see a customer's recent uploads and why they failed)
- Who acts on a mismatch: the agent, or a person? (AI agent teammate, on Compare checksums for every file)
- Is the August bill the one we judge by? (Finance, on Big uploads always finish, and the transfer bill falls)
- Do we let the uploader download their own file before the scan? (Customer voice, on A file still being scanned cannot be downloaded)
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

### D4: Do we run the one-week caching test before deciding on provider B?
Status: Open. Owner: Engineering lead. Due: 2026-06-10.
Options: Yes, test caching first; No, decide on B now.

### D5: How do we keep the 30-day deletion promise at provider B?
Status: Open. Owner: Security engineer. Due: 2026-06-20.
Options: Turn the recycle area off; Purge 7 days early.

## Did it work?

- **Failed large uploads** Before: About 6% during busy hours. Target: Below 1%. Not measured yet.

- **Data out cost per month** Before: Up 22% last quarter. Target: Down 30% by September. Not measured yet.

- **Time from upload to 'Ready' for files under 100 MB** Before: Shown at once, scanned later. Target: Under 15 seconds, scanned first. Not measured yet.

- **Upload tickets per month** Before: 31 in the incident week. Target: Fewer than 5. Not measured yet.

## Sources

- [S1] Incident review: slow uploads (document, 2026-05-04)
- [S2] Storage providers compared (data, 2026-05-12)
- [S3] Team discussion (meeting, 2026-05-15)
- [S4] Support tickets, sample of 31 (document, 2026-05-09)
- [S5] Upload numbers, April (data, 2026-05-06)
- [S6] Provider B call notes and draft terms (document, 2026-05-14)
- [S7] Scanning and retention setup (document, 2026-05-10)

## Words we use

- **signed link**: A web address that lets one browser upload or download one file for a few minutes, without a password.
- **proxy**: When our servers pass every byte between the customer and storage, instead of the customer talking to storage directly.
- **resumable upload**: An upload sent in pieces, so a dropped connection only loses the last piece.
- **data out**: Files sent from storage to anyone outside it. Providers charge for this.
- **CDN**: A network of servers close to customers that keeps copies of popular files, so they download faster and cost less.
- **checksum**: A short fingerprint of a file. If two copies have the same checksum, they are the same.
- **holding area**: A place where new files wait, unseen by anyone else, until the virus scan passes.
- **recycle area**: Where a provider keeps deleted files for a few days in case they were deleted by mistake.

## Who is speaking

- **Designer**: Will people understand this and find their way without help?
- **Analyst**: Is it clear what must be true, for whom, and how we will measure it?
- **Engineer**: What do we build first, what could break, and how do we test it?
- **Product owner**: What is in the first version, what do we cut, and what does success look like?
- **Security and privacy**: Who can see what, what do we keep, and what happens if it leaks?
- **Customer voice**: Would the people we serve choose this, and would they need a manual?
- **AI agent teammate**: What can an agent do on its own, and what needs a person's OK?
- **Finance**: What does it cost to build and run, and when does it pay back?
