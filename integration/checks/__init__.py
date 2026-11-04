"""Complete-flow checks for the Rumi recovery console, split by responsibility.

Shared helpers (each imports only modules listed above it):

- `results`: the single `RECORDER` (check results + created run ids) and `record_check`
- `expectations`: expected agent identity, payment, recovered result, State fields
- `storage`: read/tamper one isolated run's history, ledger and run.json
- `assertions`: State and on-disk evidence assertions
- `http_client`: HTTP requests to the console under test
- `processes`: real `-m integration.serve` launcher processes

Scenarios and orchestration:

- `flow_scenarios`: startup/static/idle, exclusive bind, crash -> recover -> repeat -> refresh,
  restart persistence, new-run isolation, preserved Rumi checkout
- `refusal_scenarios`: evidence refusals, unsupported history, false-success edges,
  invalid requests
- `suite`: `main(argv)` behind `python -m integration.test_flow`
"""

__all__: list[str] = []
