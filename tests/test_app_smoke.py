from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

import components as ui
from benefit_stress_lab.scenarios import run_analysis

APP = Path(__file__).resolve().parents[1] / "app"
PAGES = [
    "pages/1_workforce.py",
    "pages/2_plan_designer.py",
    "pages/3_stress_test.py",
    "pages/4_results.py",
    "pages/5_methodology.py",
]


def open_page(page: str, *, with_demo: bool) -> AppTest:
    at = AppTest.from_file(str(APP / page), default_timeout=60)
    if with_demo:
        demo = ui.demo_state()
        for key, value in demo.items():
            at.session_state[key] = value
        at.session_state["analysis"] = run_analysis(
            demo["workforce"],
            demo["current_plan"],
            demo["alternatives"],
            demo["settings"],
            demo["assumptions"],
            demo["costs"],
        )
        at.session_state["inputs_version"] = 0
        at.session_state["analysis_inputs_version"] = 0
        at.session_state["run_id"] = 1
    return at.run()


def button(at: AppTest, label: str):
    return next(item for item in at.button if item.label == label)


def test_introduction_renders():
    at = AppTest.from_file(str(APP / "app.py"), default_timeout=60).run()
    assert not at.exception
    assert button(at, "Load demonstration") is not None


def test_demo_button_runs_the_analysis():
    at = AppTest.from_file(str(APP / "app.py"), default_timeout=60).run()
    button(at, "Load demonstration").click().run()
    assert not at.exception
    assert at.session_state["analysis"] is not None
    assert len(at.session_state["alternatives"]) == 3


@pytest.mark.parametrize("page", PAGES)
def test_pages_render_without_data(page):
    at = open_page(page, with_demo=False)
    assert not at.exception


@pytest.mark.parametrize("page", PAGES)
def test_pages_render_with_demo(page):
    at = open_page(page, with_demo=True)
    assert not at.exception


def test_results_open_on_the_focus_plan():
    at = open_page("pages/4_results.py", with_demo=True)
    assert at.selectbox[0].value == "B: Proposed Cost Shift"
    assert len(at.tabs) == 6
    assert not at.info


def test_results_switch_alternative():
    at = open_page("pages/4_results.py", with_demo=True)
    at.selectbox[0].select("A: Modest Adjustment").run()
    assert not at.exception
    assert at.session_state["focus_plan"] == "A: Modest Adjustment"


def test_changing_the_simulation_settings():
    at = open_page("pages/4_results.py", with_demo=True)
    assert at.session_state["simulation_settings"].individual_variation_pct == 25
    field = next(item for item in at.number_input if item.label == "Individual variation (%)")
    field.set_value(40.0)
    button(at, "Run the simulation").click().run()
    assert not at.exception
    assert at.session_state["simulation_settings"].individual_variation_pct == 40


def test_generating_a_workforce():
    at = open_page("pages/1_workforce.py", with_demo=False)
    button(at, "Generate workforce").click().run()
    assert not at.exception
    assert len(at.session_state["workforce"]) == 500
    assert any("Generated 500" in box.value for box in at.success)


def test_own_workforce_replaces_the_demo_plans():
    at = open_page("pages/1_workforce.py", with_demo=True)
    button(at, "Generate workforce").click().run()
    assert not at.exception
    assert [plan.name for plan in at.session_state["alternatives"]] == ["Proposed Plan"]
    assert at.session_state["analysis"] is None
    assert any("demonstration plans were replaced" in box.value for box in at.success)


def test_own_workforce_keeps_edited_plans():
    at = open_page("pages/1_workforce.py", with_demo=True)
    kept = at.session_state["alternatives"][:2]
    at.session_state["alternatives"] = kept
    button(at, "Generate workforce").click().run()
    assert not at.exception
    assert at.session_state["alternatives"] == kept
    assert at.session_state["analysis"] is not None


def test_copying_the_current_plan():
    at = open_page("pages/2_plan_designer.py", with_demo=False)
    button(at, "Duplicate current plan").click().run()
    assert not at.exception
    assert [plan.name for plan in at.session_state["alternatives"]] == [
        "Proposed Plan",
        "Alternative",
    ]


def test_invalid_plan_is_rejected():
    at = open_page("pages/2_plan_designer.py", with_demo=False)
    maximum = next(item for item in at.number_input if item.label == "Out-of-pocket maximum")
    maximum.set_value(100.0)
    button(at, "Save plan").click().run()
    assert not at.exception
    assert any("at least the deductible" in box.value for box in at.error)
    assert at.session_state["current_plan"].tiers["employee_only"].out_of_pocket_max == 3_000


def test_running_the_stress_test():
    at = open_page("pages/3_stress_test.py", with_demo=True)
    at.session_state["analysis"] = None
    at.run()
    button(at, "Run the stress test").click().run()
    assert not at.exception
    assert at.session_state["analysis"] is not None
