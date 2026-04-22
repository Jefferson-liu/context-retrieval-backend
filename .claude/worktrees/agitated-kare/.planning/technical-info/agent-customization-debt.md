# Agent Customization Debt Log

## Known Limitations
- The janitor agent relies on convention-based stale file detection; ambiguous candidates still need manual confirmation.
- Temporary-looking top-level files can be either intentional diagnostics or stale artifacts, so safe automation currently stops short of deleting them.

## Follow-up Improvements
- Add repo-specific safe-delete allowlists/denylists to reduce ambiguity during cleanup.
- Add a cleanup checklist artifact template for repeatable audit trails.
- Add integration tests for `.agent.md` linting/validation if workflow automation is introduced.

## Missing Tests
- No automated test currently verifies agent behavior because `.agent.md` execution is runtime-driven by Copilot.
