import argparse
import json
import logging
import subprocess
import sys
import tempfile
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

repoRoot = Path(__file__).resolve().parents[1]
artifactName = "GDS_logs"
gdsWorkflow = "gds"
metricsRelPath = Path("runs/wokwi/final/metrics.json")
configRelPath = Path("runs/wokwi/resolved.json")
setupCornerPrefix = "timing__setup__ws__corner:"
holdCornerPrefix = "timing__hold__ws__corner:"
missingText = "n/a"
columnGap = "  "


@dataclass(frozen=True)
class RunInfo:
    runId: int
    commit: str
    date: str


@dataclass(frozen=True)
class Metric:
    label: str
    key: str
    unit: str = ""
    scale: float = 1.0
    decimals: int = 0


areaMetrics = (
    Metric("Standard cells", "design__instance__count__stdcell"),
    Metric("Standard-cell area", "design__instance__area__stdcell", "µm²", decimals=2),
    Metric("Die area", "design__die__area", "µm²", decimals=2),
    Metric("Utilization", "design__instance__utilization", "%", scale=100.0, decimals=2),
    Metric("Wire length", "route__wirelength", "µm"),
)

setupSlack = Metric("Setup worst slack", "timing__setup__ws", "ns", decimals=3)
holdSlack = Metric("Hold worst slack", "timing__hold__ws", "ns", decimals=3)

checkMetrics = (
    Metric("Setup violations", "timing__setup_vio__count"),
    Metric("Hold violations", "timing__hold_vio__count"),
    Metric("Routing DRC errors", "route__drc_errors"),
    Metric("Magic DRC errors", "magic__drc_error__count"),
    Metric("LVS errors", "design__lvs_error__count"),
    Metric("Antenna violating nets", "antenna__violating__nets"),
)

areaLogMetrics = (
    areaMetrics[0], areaMetrics[1], areaMetrics[3], setupSlack, holdSlack,
    checkMetrics[3], checkMetrics[4],
)


def runGh(args: list[str]) -> str:
    result = subprocess.run(
        ["gh", *args], cwd=repoRoot, check=True, capture_output=True, text=True
    )
    return result.stdout


def findLatestRunId() -> int:
    output = runGh([
        "run", "list", "--workflow", gdsWorkflow, "--status", "success",
        "--limit", "1", "--json", "databaseId",
    ])
    runs = json.loads(output)
    if not runs:
        raise LookupError(f"no successful '{gdsWorkflow}' run found")
    return int(runs[0]["databaseId"])


def getRunInfo(runId: int) -> RunInfo:
    output = runGh(["run", "view", str(runId), "--json", "headSha,createdAt"])
    info = json.loads(output)
    return RunInfo(runId=runId, commit=info["headSha"][:7], date=info["createdAt"][:10])


def downloadLogs(runId: int, destination: Path) -> None:
    runGh(["run", "download", str(runId), "-n", artifactName, "-D", str(destination)])


def loadJson(path: Path) -> dict[str, Any]:
    with path.open() as handle:
        data: dict[str, Any] = json.load(handle)
    return data


def formatValue(value: Any, metric: Metric) -> str:
    if value is None:
        return missingText
    return f"{float(value) * metric.scale:.{metric.decimals}f}"


def formatMetric(metrics: dict[str, Any], metric: Metric) -> str:
    return formatValue(metrics.get(metric.key), metric)


def checkStatus(metrics: dict[str, Any], metric: Metric) -> str:
    value = metrics.get(metric.key)
    if value is None:
        return missingText
    return "PASS" if value == 0 else "FAIL"


def renderTable(
    title: str, headers: Sequence[str], rows: Sequence[Sequence[str]], alignments: str
) -> str:
    widths = [max(len(cell) for cell in column) for column in zip(headers, *rows)]

    def renderRow(cells: Sequence[str]) -> str:
        padded = (
            cell.rjust(width) if align == ">" else cell.ljust(width)
            for cell, width, align in zip(cells, widths, alignments)
        )
        return columnGap.join(padded).rstrip()

    rule = columnGap.join("─" * width for width in widths)
    return "\n".join([title, "", renderRow(headers), rule, *map(renderRow, rows)])


def renderHeader(info: RunInfo, clockPeriodNs: float) -> str:
    title = f"GDS metrics: run {info.runId}"
    details = (
        f"Commit {info.commit}   Date {info.date}   "
        f"Clock {clockPeriodNs:g} ns ({1000.0 / clockPeriodNs:g} MHz)"
    )
    return "\n".join([title, "═" * max(len(title), len(details)), details])


def renderArea(metrics: dict[str, Any]) -> str:
    rows = [(metric.label, formatMetric(metrics, metric), metric.unit) for metric in areaMetrics]
    return renderTable("Area", ("Metric", "Value", "Unit"), rows, "<><")


def renderTiming(metrics: dict[str, Any]) -> str:
    corners = sorted(
        key.removeprefix(setupCornerPrefix) for key in metrics if key.startswith(setupCornerPrefix)
    )
    rows = [
        (
            corner,
            formatValue(metrics.get(setupCornerPrefix + corner), setupSlack),
            formatValue(metrics.get(holdCornerPrefix + corner), holdSlack),
        )
        for corner in corners
    ]
    rows.append(("Worst", formatMetric(metrics, setupSlack), formatMetric(metrics, holdSlack)))
    return renderTable(
        "Timing (slack in ns)", ("Corner", "Setup slack", "Hold slack"), rows, "<>>"
    )


def renderChecks(metrics: dict[str, Any]) -> str:
    rows = [
        (metric.label, formatMetric(metrics, metric), checkStatus(metrics, metric))
        for metric in checkMetrics
    ]
    return renderTable("Checks", ("Check", "Count", "Status"), rows, "<><")


def renderResult(metrics: dict[str, Any]) -> str:
    statuses = [checkStatus(metrics, metric) for metric in checkMetrics]
    failed = statuses.count("FAIL")
    missing = statuses.count(missingText)
    if failed:
        return f"Result: FAIL ({failed} of {len(statuses)} checks fail)"
    if missing:
        return f"Result: INCOMPLETE ({missing} of {len(statuses)} checks have no data)"
    return f"Result: PASS (all {len(statuses)} checks pass)"


def renderAreaLogRow(metrics: dict[str, Any], info: RunInfo) -> str:
    values = " | ".join(formatMetric(metrics, metric) for metric in areaLogMetrics)
    return "\n".join([
        "Area log row (Markdown, for docs/area_log.md)",
        "",
        "| Date | Commit | Run | Cells | Area (µm²) | Util (%) | Setup WS (ns) "
        "| Hold WS (ns) | DRC | LVS |",
        "|---|---|---|---|---|---|---|---|---|---|",
        f"| {info.date} | {info.commit} | {info.runId} | {values} |",
    ])


def renderReport(metrics: dict[str, Any], info: RunInfo, clockPeriodNs: float) -> str:
    sections = (
        renderHeader(info, clockPeriodNs),
        renderArea(metrics),
        renderTiming(metrics),
        renderChecks(metrics),
        renderResult(metrics),
        renderAreaLogRow(metrics, info),
    )
    return "\n\n".join(sections) + "\n"


def parseArgs() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download the GDS_logs artifact of a gds CI run and show its metrics."
    )
    parser.add_argument(
        "runId", type=int, nargs="?",
        help="GitHub Actions run ID (default: newest successful gds run)",
    )
    return parser.parse_args()


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    args = parseArgs()
    try:
        runId = args.runId if args.runId is not None else findLatestRunId()
        info = getRunInfo(runId)
        with tempfile.TemporaryDirectory() as tempDir:
            logsDir = Path(tempDir)
            logger.info("downloading %s for run %d", artifactName, runId)
            downloadLogs(runId, logsDir)
            metrics = loadJson(logsDir / metricsRelPath)
            clockPeriodNs = float(loadJson(logsDir / configRelPath)["CLOCK_PERIOD"])
    except FileNotFoundError as error:
        logger.error("file not found: %s (is gh installed?)", error.filename)
        return 1
    except subprocess.CalledProcessError as error:
        logger.error("gh failed: %s", error.stderr.strip())
        return 1
    except (LookupError, KeyError) as error:
        logger.error("%s", error)
        return 1
    sys.stdout.write(renderReport(metrics, info, clockPeriodNs))
    return 0


if __name__ == "__main__":
    sys.exit(main())
