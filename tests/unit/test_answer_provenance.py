"""The service half of the model pills: which model ANSWERED, and whether it searched.

The console shows two pills at the top right: the model that answered the last request, and
``Search`` when that answer used an online search tool. Both come from response headers the kit
emits (``install_answer_provenance`` in ``api/app.py``) for whatever the model adapters NOTED as
they called. Before a request is answered the pill shows ``generator_model`` from ``/healthz``,
so that value must be the model the bound adapter calls, never one a configuration flag names
while the adapter calls another.

The served triage route runs the deterministic engine, so it notes nothing and a response carries
neither header. The route is still proved to carry them the day it notes something, by standing a
noting engine in for the real one. The ``local`` generation stub notes its own name on every call;
the managed generation and adverse-media adapters refuse until a deployment configures them, so
they never answer and note nothing.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from hex_service_kit import provenance

from tprm_ddq import config
from tprm_ddq.adapters.local.generation import LocalGenerationAdapter
from tprm_ddq.api import app as app_module
from tprm_ddq.config import OFFLINE_STUB_MODEL
from tprm_ddq.domain.models import TriageInput, TriageResult
from tprm_ddq.domain.triage_service import TriageService

from tests import REPO_ROOT
from tests.conftest import local_settings
from tests.fixtures import sample_cases

ANSWERED_BY = "x-answered-by"
SEARCH_USED = "x-search-used"


def _triage(monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:
    # CI targets run the suite with no profile exported; the served app must still be `local`.
    monkeypatch.setenv("TPRM_DDQ_PROFILE", "local")
    client = TestClient(app_module.app, client=("127.0.0.1", 50000))
    case = sample_cases.ROUTINE_CASE
    response = client.post(
        "/v1/triage",
        json={"subject": case.subject, "text": case.text},
        headers={"X-Dev-Persona": "analyst"},
    )
    assert response.status_code == 200, response.text
    return dict(response.headers)


def test_a_deterministic_answer_names_no_model(monkeypatch: pytest.MonkeyPatch) -> None:
    """Nothing noted, nothing sent: the pill never invents a model the engine did not call."""
    headers = _triage(monkeypatch)
    assert ANSWERED_BY not in headers
    assert SEARCH_USED not in headers


class _AnsweringService(TriageService):
    """The real engine, plus what a model adapter that searched would note while it called."""

    def triage(self, case: TriageInput, *, actor: str) -> TriageResult:
        provenance.note_model("fake-answering-model")
        provenance.note_search()
        return super().triage(case, actor=actor)


def test_the_route_names_the_model_that_answered_and_that_it_searched(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(app_module, "TriageService", _AnsweringService)
    headers = _triage(monkeypatch)
    assert headers[ANSWERED_BY] == "fake-answering-model"
    assert headers[SEARCH_USED] == "true"
    # The next request is a fresh record: an answer never leaks into a later response.
    monkeypatch.setattr(app_module, "TriageService", TriageService)
    assert ANSWERED_BY not in _triage(monkeypatch)


def test_the_local_generation_stub_answers_as_the_name_the_pill_first_shows() -> None:
    adapter = LocalGenerationAdapter(local_settings())
    with provenance.scope() as record:
        adapter.draft_memo("Acme Holdings (FICTIONAL)", "HIGH", ("GAP-1",))
    assert record.models == [OFFLINE_STUB_MODEL]
    assert record.search_used is False
    assert local_settings().generator_model == OFFLINE_STUB_MODEL


def test_generator_model_is_the_setting_the_adapter_reads_and_no_flag_swaps_it() -> None:
    """The latent false banner: a flag that moved the pill but not the model that answered."""
    models = SimpleNamespace(
        reasoning="the-model-the-adapter-calls",
        hard_reasoning="a-model-nobody-calls",
        use_hard_reasoning=True,
    )
    named = config._model_from_settings(SimpleNamespace(models=models), "models.reasoning")
    assert named == "the-model-the-adapter-calls"


def test_the_hard_reasoning_flag_does_not_exist() -> None:
    settings_file = (REPO_ROOT / "config" / "settings.yaml").read_text(encoding="utf-8")
    assert "use_hard_reasoning" not in settings_file
    for source in sorted((REPO_ROOT / "src").rglob("*.py")):
        assert "use_hard_reasoning" not in source.read_text(encoding="utf-8"), source
