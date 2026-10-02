# Public Repository Release Checklist

Use this checklist before linking RoleRadar AI from a public portfolio or release. These are
release checks to perform and record; this document does not claim that they run automatically.

- [ ] Review the staged diff and confirm no credentials, local `.env` files, databases, CV inputs,
  generated CVs, private evidence, or local agent artifacts are included.
- [ ] Run GitHub secret scanning (including any available push protection) and resolve every alert.
- [ ] Enable and review GitHub dependency alerts for the default branch.
- [ ] Open every public README, portfolio, and repository link in a signed-out browser window.
- [ ] Confirm the default branch and GitHub CTA resolve without authentication.
- [ ] Confirm new commits use the GitHub `noreply` author email. Decide separately whether legacy
  history requires a destructive review before any rewrite or force-push.
- [ ] Run the documented test and lint commands, and attach only redacted evidence to the release.
