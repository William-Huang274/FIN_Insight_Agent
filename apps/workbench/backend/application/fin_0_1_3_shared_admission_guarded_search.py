from __future__ import annotations

from pathlib import Path

from apps.workbench.backend.application.fin_0_1_2_s4_t03_executable_agentic_search import (
    Fin012S4T03SearchRunner,
    SourceTransport,
)
from sec_agent.shared_admission_ledger import SharedAdmissionConsumptionLedger


class Fin013SharedAdmissionGuardedSearchRunner(Fin012S4T03SearchRunner):
    """Current FIN 0.1.3 search boundary; a shared ledger is mandatory."""

    def __init__(
        self,
        *,
        repository_root: str | Path,
        runtime_root: str | Path,
        transport: SourceTransport,
        shared_admission_ledger: SharedAdmissionConsumptionLedger,
    ) -> None:
        if not isinstance(
            shared_admission_ledger,
            SharedAdmissionConsumptionLedger,
        ):
            raise TypeError("fin_0_1_3_shared_admission_ledger_required")
        super().__init__(
            repository_root=repository_root,
            runtime_root=runtime_root,
            transport=transport,
            shared_admission_ledger=shared_admission_ledger,
        )
