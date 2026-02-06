"""Benchmark definitions - the canonical list of evaluations."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class BenchmarkConfig:
    """Configuration for a single benchmark evaluation."""

    id: str
    name: str
    short_name: str
    description: str
    hf_column: str
    module_path: str
    function_name: str


BENCHMARKS: tuple[BenchmarkConfig, ...] = (
    BenchmarkConfig(
        id="teleqna",
        name="TeleQnA",
        short_name="QnA",
        description="Question answering benchmark for telecom domain",
        hf_column="teleqna",
        module_path="evals.teleqna.teleqna",
        function_name="teleqna",
    ),
    BenchmarkConfig(
        id="telelogs",
        name="TeleLogs",
        short_name="Logs",
        description="Log analysis and troubleshooting benchmark",
        hf_column="telelogs",
        module_path="evals.telelogs.telelogs",
        function_name="telelogs",
    ),
    BenchmarkConfig(
        id="telemath",
        name="TeleMath",
        short_name="Math",
        description="Mathematical reasoning for telecom calculations",
        hf_column="telemath",
        module_path="evals.telemath.telemath",
        function_name="telemath",
    ),
    BenchmarkConfig(
        id="teletables",
        name="TeleTables",
        short_name="Tables",
        description="Table understanding and extraction benchmark",
        hf_column="teletables",
        module_path="evals.teletables.teletables",
        function_name="teletables",
    ),
    BenchmarkConfig(
        id="three_gpp",
        name="3GPP",
        short_name="3GPP",
        description="3GPP specification understanding benchmark",
        hf_column="3gpp_tsg",
        module_path="evals.three_gpp.three_gpp",
        function_name="three_gpp",
    ),
)

BENCHMARKS_BY_ID: dict[str, BenchmarkConfig] = {b.id: b for b in BENCHMARKS}
