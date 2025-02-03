# diveplan/core/dive.py
from dataclasses import dataclass
from typing import List, Tuple

from diveplan.utils import constants, physics
from diveplan.core import gas
from diveplan.core.decomodels.abstract_deco_model import AbstractDecoModel
from diveplan.core.decomodels.zhl16c import ZHL16C


@dataclass
class DiveStep:
    """Represents a single step in a dive plan.

    Attributes:
        time (float): Duration of the step in minutes.
        start_depth (float): Starting depth of the step in meters.
        end_depth (float): Ending depth of the step in meters.
        gas_cylinder (gas.GasCylinder): Gas cylinder used during this step.

    """

    time: float
    start_depth: float
    end_depth: float
    gas_cylinder: gas.GasCylinder

    @property
    def type(self):
        """str: Type of the dive step ('descent', 'ascent', or 'const')."""
        if self.end_depth > self.start_depth:
            return "descent"
        elif self.end_depth < self.start_depth:
            return "ascent"
        else:
            return "const"

    def get_ambient_pressure_at_sample(self, sample_time: float) -> float:
        """Calculates ambient pressure at a specific time during the dive step.

        Args:
            sample_time (float): Time elapsed since the beginning of the step (in minutes).

        Returns:
            float: Ambient pressure at the sample time, in bar.

        """
        depth_at_sample = self.start_depth + (sample_time / self.time) * (
            self.end_depth - self.start_depth
        )
        return physics.depth_to_ambient_pressure(depth_at_sample)


class Dive:
    """Represents a planned dive, including descent, bottom time, and ascent.

    Attributes:
        steps (List[DiveStep]): List of planned dive steps.
        ascent (List[DiveStep]): Calculated ascent profile (populated by `calculate_ascent()`).
        gas_cylinders (List[gas.GasCylinder]): List of gas cylinders available for the dive.
        gradient_factors (Tuple[int, int]): Gradient factors (GF Low, GF High) for the decompression model. Default is (100, 100).
        sample_rate (float): Sample rate in minutes for decompression calculations. Default is 0.1 minutes.
        deco_model (AbstractDecoModel): Decompression model used for the dive.  Defaults to ZHL16C.


    """

    def __init__(
        self,
        planned_steps: List[DiveStep],
        gas_cylinders: List[gas.GasCylinder],
        gradient_factors: Tuple[int, int] = (100, 100),
        sample_rate: float = 0.1,
    ):

        if any(step.time < 0 for step in planned_steps):
            raise ValueError("Time cannot be negative")

        self.steps: List[DiveStep] = planned_steps[:]
        self.ascent: List[DiveStep] = []

        if not gas_cylinders:
            raise ValueError("gas_cylinders cannot be empty.")
        self.gas_cylinders = gas_cylinders

        self.gradient_factors = gradient_factors
        self.sample_rate = sample_rate

        self.deco_model: AbstractDecoModel = ZHL16C(
            self.gradient_factors, self.sample_rate
        )

    def calculate_ascent(self):
        """Calculates the ascent profile based on the decompression model and appends it to `self.ascent`."""

        current_pressure = physics.depth_to_ambient_pressure(self.steps[-1].end_depth)
        surface_pressure = physics.depth_to_ambient_pressure(0.0)

        while current_pressure > surface_pressure:
            ceiling_pressure = physics.round_to_stop_pressure(
                self.deco_model.get_ceiling()
            )

            time = 1.0 if current_pressure == ceiling_pressure else 0.0

            ascent_step = DiveStep(
                time,
                physics.ambient_pressure_to_depth(current_pressure),
                physics.ambient_pressure_to_depth(ceiling_pressure),
                self.gas_cylinders[0],
            )
            self.ascent.append(ascent_step)

            self.deco_model.integrate_dive_step(ascent_step)
            current_pressure = physics.depth_to_ambient_pressure(ascent_step.end_depth)

        # Final ascent to surface if not exactly at 0 depth due to rounding
        if self.ascent[-1].end_depth != 0.0:
            last_ascent = DiveStep(
                0, self.ascent[-1].end_depth, 0.0, self.gas_cylinders[0]
            )
            self.ascent.append(last_ascent)

    def calculate_steps(self):
        """Calculates the dive steps, integrates them with the decompression model, and ensures the dive starts at the surface (0m)."""

        if self.steps[0].start_depth != 0.0:
            self.steps.insert(
                0, DiveStep(0, 0, self.steps[0].start_depth, self.steps[0].gas_cylinder)
            )
            self.steps[1].time -= self.steps[0].time # Adjust the time of the original first step


        for step in self.steps:
            self.deco_model.integrate_dive_step(step)

    def report(self):
        """Prints a human-readable dive report, including ascent profile."""

        symbol_map = {"descent": "▼", "ascent": "▲", "const": "-"}

        # Efficiently merge consecutive 'const' ascent steps to simplify the report
        for i, ascent_step in enumerate(self.ascent):
            if ascent_step.type == "const" and i > 0:
                previous_step = self.ascent[i - 1]
                if (
                    ascent_step.start_depth == previous_step.end_depth
                    and previous_step.type == "const"
                ):
                    self.steps[-1].time += ascent_step.time # Adjust the last step's duration if ascent is a continuation
                    continue

            self.steps.append(ascent_step) # Append the non-mergable ascent steps

        print(self.deco_model.name, self.gradient_factors)

        runtime = 0
        for step in self.steps:
            symbol = symbol_map.get(step.type, "?")
            depth = int(round(step.end_depth))
            time = int(round(step.time))
            runtime += time

            print(f"{symbol} {depth}m {time}min {runtime}min")

    def select_best_gas_cylinder(self, depth: float) -> gas.GasCylinder | None:
        """Selects the best gas cylinder for a given depth based on ppO2 limits and gas availability.

        Args:
            depth (float): Depth in meters.

        Returns:
            gas.GasCylinder | None: The most suitable gas cylinder or None if no suitable gas is found.

        Raises:
             ValueError: If the suggested cylinder is empty.
        """

        ambient_pressure = physics.depth_to_ambient_pressure(depth)

        suitable_cylinders = []

        for cylinder in self.gas_cylinders:
            mixture = cylinder.gas_mixture

            if (
                mixture.max_operating_pressure() >= ambient_pressure  # Check if the gas can be breathed at this depth
                and mixture.partial_pressure("O2", ambient_pressure)
                >= constants.MIN_PPO2  # Ensure ppO2 is above minimum
            ):
                suitable_cylinders.append(cylinder)

        if not suitable_cylinders:
            return None

        # Prioritize: Higher ppO2, then Higher ppHe
        best_cylinder = sorted(
            suitable_cylinders,
            key=lambda cyl: (
                cyl.gas_mixture.partial_pressure("O2", ambient_pressure),
                cyl.gas_mixture.partial_pressure("He", ambient_pressure),
            ),
            reverse=True,
        )[0]


        if best_cylinder.current_pressure <= 0:
            raise ValueError("No gas remaining in the suggested cylinder.")

        return best_cylinder

    def add_optimal_gas_cylinder(
        self,
        volume: float,
        working_pressure: float,
        end_depth: float,
        target_ppo2: float = constants.DECO_PPO2,
    ):
        """Adds a cylinder with an optimal gas mix for a target ppO2 at a given depth.

        Args:
            volume (float): Cylinder volume in liters.
            working_pressure (float): Cylinder working pressure in bar.
            end_depth (float): Target depth for the optimal mix, in meters.
            target_ppo2 (float): Target partial pressure of oxygen (ppO2) at the target depth, in bar. Defaults to `constants.DECO_PPO2`.

        Raises:
            ValueError: If it's impossible to create a mix with the desired parameters (e.g., O2 fraction > 1).


        """
        ambient_pressure = physics.depth_to_ambient_pressure(end_depth)
        end_pressure = physics.depth_to_ambient_pressure(end_depth)  # end_pressure is redundant
        ppn2 = end_pressure * constants.AIR_FN2  # Assuming constant ppN2 equivalent to air

        frac_o2 = target_ppo2 / ambient_pressure
        frac_he = max(1.0 - (ppn2 / ambient_pressure + frac_o2), 0.0) # Calculate the helium fraction

        if frac_o2 > 1.0:
            raise ValueError(
                "Impossible to create optimal mix: required o2 fraction would be above 100%."
            )

        mix = gas.GasMixture(frac_o2, frac_he)
        cylinder = gas.GasCylinder(volume, working_pressure, mix)
        self.gas_cylinders.append(cylinder)

