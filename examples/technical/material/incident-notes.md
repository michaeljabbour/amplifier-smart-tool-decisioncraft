# Incident review: slow uploads, 2 May (fictional)

- Uploads over 200 MB timed out for about 40 minutes. Our app servers proxy every byte
  to storage, so long uploads hold a server connection open.
- On-call engineer: "Half our servers were just shovelling bytes. Nothing else could get
  through."
- Support received 31 tickets. Most from customers uploading video.
- Our storage bill grew 22% last quarter, mostly from data transfer out, not storage.
