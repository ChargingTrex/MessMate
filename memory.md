# memory.md — things to know before writing the next test

Hard-won notes for anyone (human or agent) touching MessMate's tests.
Append a new entry when a debugging session costs you more than a few minutes.

---

## Disabling rate limits: use `limiter.enabled`, not the config key

**Do this:**

```python
import app as app_module
app_module.limiter.enabled = False
```

**Not this — it silently does nothing:**

```python
app.config["RATELIMIT_ENABLED"] = False   # ← no effect after import
```

### Why

`app.py` builds the limiter at import time with `Limiter(..., app=app)`. That
constructor calls `init_app()`, which reads `RATELIMIT_ENABLED` **once** and
stores it on the instance. Setting the config key afterwards changes a value
nothing reads again. The instance attribute is the live switch.

### Why it costs so much time

The failure does not look like a rate limit. `/admin/login` and
`/committee/login` are capped at 10 and 20 per hour. Once a suite burns
through the admin cap, every later admin action gets a **429**, and the 429
handler renders a login page — so the test sees a redirect to `/admin/login`
and reports something like *"expected the roster, got the login page."*

That is indistinguishable from a broken session, a dropped cookie, or a bad
password. It also appears **only in the full run**, never when you run the
failing test alone, because a single test never exhausts the cap.

This cost a debugging cycle on the committee suites: eight checks failed at
once and looked like broken password-reset and bulk-add logic. Both were
fine. Symptoms to recognise:

- Tests pass individually, fail in a batch
- Failures cluster **after** the first several authenticated requests
- The failure is always "landed on a login page" rather than an assertion
  about content
- Earlier tests in the same run passed doing the very same thing

### Verify the switch actually took

```python
assert app_module.limiter.enabled is False
```

If a suite genuinely needs the limits live — `test_e2e_committee.py` J-tests
and `test_committee.py` P3-13 exercise real 429 behaviour — flip it on around
just that block and restore it in a `finally`, so nothing downstream inherits
a consumed budget:

```python
app_module.limiter.enabled = True
try:
    ...
finally:
    app_module.limiter.enabled = False
```

### Where this is already handled

- `test/test_committee.py` and `test/test_e2e_committee.py` set the instance
  attribute, with a comment saying why.
- `test/fake_server.py` disables it at boot, because the Robot UI suites sign
  in dozens of times and would otherwise trip the cap mid-run.

The general shape of the lesson: **an extension that reads config at
`init_app()` time will ignore config you set later.** Flask-Limiter is the one
that bites here, but check the same before trusting any post-import
`app.config[...]` change.
