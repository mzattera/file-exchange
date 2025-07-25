"""
scenario_component.py

Python translation of `com.infosys.small.pnbc.ScenarioComponent`.

The class loads scenario definitions from a folder containing one or more
*.json* files.  Each file must contain a JSON array whose elements conform
to the schema defined by :class:`Scenario`.

The implementation mirrors the original Java semantics while embracing
Pythonic conventions and type hints.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

from pydantic import BaseModel, Field, ValidationError

# --------------------------------------------------------------------------- #
# Logging configuration (equivalent to Java SimpleLogger)
# --------------------------------------------------------------------------- #
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# Pydantic models mirroring the nested Java static classes
# --------------------------------------------------------------------------- #
class Output(BaseModel):
    type: str
    value: str


class ScenarioToolCall(BaseModel):
    tool_id: str = Field(alias="tool_id")
    input: Dict[str, Any]
    output: List[Output]

    model_config = {"populate_by_name": True}


class Scenario(BaseModel):
    id: str
    description: str
    success_criteria: str = Field(alias="success_criteria")
    tool_calls: List[ScenarioToolCall] = Field(alias="tool_calls")

    model_config = {"populate_by_name": True}


class ScenarioMetadata(BaseModel):
    id: str = Field(alias="id")
    description: str = Field(alias="description")

    model_config = {"populate_by_name": True}


# --------------------------------------------------------------------------- #
# Main component
# --------------------------------------------------------------------------- #
class ScenarioComponent:
    """
    Access-point for scenario definitions loaded from disk.

    Parameters
    ----------
    folder : str | os.PathLike
        Directory containing one or more JSON files with scenario definitions.
    """

    # ------------------------- construction ---------------------------- #
    def __init__(self, folder: str | os.PathLike) -> None:
        if folder is None:
            raise ValueError("folder must not be None")

        self.scenario_folder: Path = Path(folder)
        if not self.scenario_folder.is_dir():
            raise IOError(f"Scenario folder {self.scenario_folder} does not exist.")

        self._scenarios: List[Scenario] = []
        self._load_scenarios()

    # Factory mirroring Java getInstance() ----------------------------- #
    @classmethod
    def get_instance(cls) -> "ScenarioComponent":
        default = Path(
            "D:/Users/mzatt/Projects/DELETEME PnBC/pnbc-services/src/main/resources/scenarios"
        )
        return cls(default)

    # --------------------------- API ---------------------------------- #
    def list_scenarios(self) -> List[Scenario]:
        """Return a *copy* of all scenarios loaded in memory."""
        return list(self._scenarios)

    def get_scenario(self, scenario_id: str) -> Optional[Scenario]:
        """
        Return the scenario with *scenario_id*, or *None* if not found.
        """
        if scenario_id is None:
            raise ValueError("scenario_id must not be None")

        for s in self._scenarios:
            if scenario_id == s.id:
                return s
        return None

    def get_success_criteria(self, scenario_id: str) -> Optional[str]:
        """Return the success criteria for *scenario_id*, if available."""
        scenario = self.get_scenario(scenario_id)
        return None if scenario is None else scenario.success_criteria

    def get(
        self,
        scenario_id: str,
        tool_id: str,
        args: Mapping[str, Any],
    ) -> str:
        """
        Retrieve the **text** output for the specified tool invocation.

        The logic follows the original Java implementation:
        * If the scenario does not exist → return an *ERROR* string.
        * Iterate through tool calls, match both *tool_id* and *args*.
        * Concatenate the value of every output whose type is ``"text"``.
        * If no matching call is found → generic *ERROR* string.
        """
        if scenario_id is None or tool_id is None or args is None:
            raise ValueError("scenario_id, tool_id and args must not be None")

        scenario = self.get_scenario(scenario_id)
        if scenario is None:
            return f"ERROR: Scenario {scenario_id} does not exist."

        for call in scenario.tool_calls:
            if call.tool_id != tool_id:
                continue
            if not self._matched(call.input, args):
                continue
            return "".join(o.value for o in call.output if o.type == "text")

        return "ERROR: System failure, wrong API call parameters."

    # --------------------- internal helpers --------------------------- #
    def _load_scenarios(self) -> None:
        """Populate :pyattr:`_scenarios` from JSON files in *scenario_folder*."""
        files = [p for p in self.scenario_folder.iterdir() if p.suffix == ".json"]
        if not files:
            raise IOError("Scenario folder is empty or contains no *.json* files.")

        for file in files:
            try:
                with file.open(encoding="utf-8") as fh:
                    data = json.load(fh)
                self._scenarios.extend(Scenario.model_validate(o) for o in data)
            except (json.JSONDecodeError, ValidationError) as exc:
                logger.error("Error parsing scenario %s", file.name, exc_info=exc)
                raise

    # Map-normalisation & matching logic (verbatim port) --------------- #
    @staticmethod
    def _transform_map(raw: Mapping[str, Any]) -> Dict[str, str]:
        result: Dict[str, str] = {}
        for k, v in raw.items():
            new_key = "" if k is None else str(k).lower().strip()
            new_val = "" if v is None else str(v).lower().strip()
            result[new_key] = new_val
        return result

    @classmethod
    def _matched(cls, map1: Mapping[str, Any], map2: Mapping[str, Any]) -> bool:
        t1 = cls._transform_map(map1)
        t2 = cls._transform_map(map2)
        for k, v in t1.items():
            if k not in t2 or t2[k] != v:
                return False
        return True
