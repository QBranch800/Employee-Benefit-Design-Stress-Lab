# Benefit Design Stress Lab

> An interactive workforce-benefits simulator that helps an employer compare health-plan designs, estimate employer savings, reveal employee affordability risks, and find better-balanced alternatives.

## 1. Project summary

Benefit Design Stress Lab is a portfolio project for Health and Benefits, Human Capital, and data advisory work. It answers a practical question:

> If an employer changes its health-benefit plan, how will the change affect company spending and the financial burden experienced by different employee groups?

The user creates or uploads a fictional workforce, defines the current benefit plan, and builds one or more alternative plans. The application applies the same plan rules to each employee under consistent healthcare-use scenarios. It then compares:

- estimated annual employer premium contributions;
- estimated employee premium contributions;
- modelled employee out-of-pocket spending;
- total employee healthcare burden as a share of salary;
- the number and characteristics of employees facing high burden; and
- the trade-off between employer savings and employee affordability.

The app does not select a plan automatically or predict an individual's health. It is a transparent scenario-analysis and decision-support tool. Its purpose is to show how an apparently attractive average saving can create very different outcomes across a workforce.

## 2. Why the project matters

Benefits decisions involve competing goals. Employers want financially sustainable plans, while employees need meaningful and affordable coverage. A design that reduces employer spending may increase payroll deductions, deductibles, or out-of-pocket exposure for employees. Average figures can conceal that the impact is concentrated among lower-paid workers, employees with family coverage, or people with greater healthcare needs.

A useful advisory analysis therefore needs to answer more than “Which plan is cheapest?” It should also ask:

- Who pays more under each option?
- How large is the increase relative to income?
- Which employee groups are most exposed?
- Can the employer achieve most of the saving with a less harmful design?
- How sensitive are the conclusions to uncertain healthcare use?

Benefit Design Stress Lab makes these trade-offs visible through an interactive, reproducible application.

## 3. Positioning and originality

This is not a generic healthcare-cost predictor, benefits chatbot, or employee recommendation engine. Its distinctive focus is **benefit-plan stress testing**:

1. Apply proposed plan rules to a synthetic workforce.
2. Measure both aggregate cost and distributional impact.
3. Identify groups that become materially worse off.
4. Stress-test conclusions across alternative utilisation assumptions.
5. Suggest design adjustments that improve the cost-affordability balance.

The working title was subject to a preliminary exact-name web search, which did not surface a matching product at the time of writing. This is not trademark or legal clearance. A new search and appropriate legal checks would be required before commercial use.

## 4. Project objectives

### Core objectives

1. Build a transparent model for comparing employer-sponsored health-plan scenarios.
2. Generate or ingest a safe, synthetic employee population.
3. Calculate employer and employee plan costs consistently.
4. Measure affordability across salary bands and coverage tiers.
5. Expose the distributional effects hidden by workforce averages.
6. Present results through a clear Streamlit decision-support interface.
7. Make assumptions, formulas, limitations, and excluded uses explicit.
8. Produce a reproducible GitHub repository with tests and documentation.

### Portfolio objectives

- Demonstrate understanding of employee-benefits consulting questions.
- Show data cleaning, modelling, scenario analysis, and visualisation skills.
- Translate technical results into an advisory recommendation.
- Demonstrate responsible handling of sensitive workforce and health-related data.
- Build something more decision-oriented than a standard machine-learning notebook.

## 5. Intended users

The demonstration users are:

- a benefits consultant comparing plan designs;
- an HR or rewards analyst preparing an internal business case;
- a finance partner assessing potential employer savings;
- a people leader concerned about affordability and workforce impact; or
- a recruiter reviewing the project as evidence of analytics and advisory capability.

The MVP is an educational demonstration. It is not intended for employees to choose personal coverage or for organisations to make real benefit decisions without qualified actuarial, legal, tax, clinical, and benefits advice.

## 6. The central example

Consider an employer with 500 employees.

### Current plan

```yaml
annual_premium_employee_only: 6000
annual_premium_family: 15000
employer_contribution_percentage: 80
individual_deductible: 500
coinsurance_after_deductible: 20
individual_out_of_pocket_maximum: 3000
```

### Proposed plan

```yaml
annual_premium_employee_only: 5000
annual_premium_family: 12500
employer_contribution_percentage: 70
individual_deductible: 1500
coinsurance_after_deductible: 30
individual_out_of_pocket_maximum: 5000
```

The proposed plan is less expensive for the employer, but employees contribute a greater share and face more cost when they use healthcare.

### Illustrative output

```text
Employer premium contribution
Current plan:              $4,200,000
Proposed plan:             $3,780,000
Estimated saving:            $420,000 (10.0%)

Average employee annual burden
Current plan:                  $2,480
Proposed plan:                 $3,160
Average increase:                $680

Employees above the selected 10% burden threshold
Current plan:                       7%
Proposed plan:                     21%

Most affected segment
Employees earning below $40,000 with family coverage

Potential adjustment
Increase the employer premium contribution for the lowest salary band.
This retains an estimated $285,000 saving while reducing the share of
employees above the threshold to 9%.
```

These figures are examples of the interface, not research findings or promises about real-world outcomes.

## 7. Key definitions

### Employer premium contribution

The portion of the insurance premium paid by the employer.

```text
Employer premium contribution
= annual premium × employer contribution percentage
```

### Employee premium contribution

The portion deducted from the employee's pay.

```text
Employee premium contribution
= annual premium × (1 − employer contribution percentage)
```

### Modelled out-of-pocket spending

The amount the employee pays for covered healthcare services under the simplified deductible, coinsurance, and out-of-pocket rules in the model.

### Total employee healthcare burden

```text
Total employee burden
= employee premium contribution + modelled out-of-pocket spending
```

### Burden as a share of salary

```text
Burden percentage
= total employee burden ÷ annual salary × 100
```

### Affordability threshold

A user-selected analytical threshold used to identify employees facing comparatively high costs. The application must not describe the default threshold as a universal legal, regulatory, or clinical standard. It is a scenario parameter and must be labelled accordingly.

## 8. Scope

### MVP — required

The minimum viable product will include:

- a reproducible synthetic workforce generator;
- optional upload of a correctly structured synthetic or anonymised CSV;
- one current plan and up to three alternative plan scenarios;
- employee-only and family coverage tiers;
- annual premiums and employer contribution percentages;
- simplified deductible, coinsurance, and out-of-pocket maximum rules;
- low, medium, and high healthcare-use scenarios;
- employer premium-cost calculations;
- employee premium and out-of-pocket calculations;
- affordability analysis by salary band and coverage tier;
- current-versus-proposed comparison charts;
- a plain-language summary of winners, losers, savings, and risks;
- exportable aggregate results;
- automated tests for the calculation engine; and
- a documented Streamlit application.

### Deliberate MVP exclusions

The first version will not include:

- real employee names or identifiers;
- diagnoses, prescriptions, medical records, or individual claims histories;
- legal or regulatory compliance determinations;
- network-contract modelling;
- provider-level recommendations;
- country-specific tax treatment;
- a complete actuarial-value calculation;
- flexible spending or health savings account tax modelling;
- coordination of benefits;
- complex family deductibles;
- real insurer quotations;
- individual health-risk scores;
- automatic plan selection; or
- an LLM dependency.

### Optional V2 features

- Monte Carlo simulation of uncertain annual healthcare spending;
- multi-objective plan optimisation;
- employer subsidies that vary by salary band;
- richer family tiers such as employee plus spouse or employee plus children;
- prescription and medical spending components;
- inflation and multi-year trend assumptions;
- benefit-utilisation clustering;
- scenario narratives generated from validated results;
- a natural-language question interface over aggregate results;
- configurable countries, currencies, and benefit structures; and
- secure integration with approved aggregate workforce data.

## 9. User flow

### Step 1: Create the workforce

The user chooses one of two options:

1. Generate a synthetic workforce by selecting headcount, salary distribution, coverage mix, and random seed.
2. Upload a CSV containing anonymous records that match the template.

The app validates the data and displays a workforce summary before continuing.

### Step 2: Define the current plan

The user enters premiums, employer contribution, deductible, coinsurance, and out-of-pocket maximum for each supported coverage tier.

### Step 3: Create alternatives

The user duplicates the current plan and changes selected assumptions, such as:

- employer contribution from 80% to 75%;
- deductible from $500 to $1,000;
- coinsurance from 20% to 25%; or
- family premium from $15,000 to $13,500.

### Step 4: Choose analysis assumptions

The user selects:

- currency;
- affordability threshold;
- healthcare-use scenario or simulation settings; and
- employee groups to compare.

### Step 5: Run the stress test

The calculation engine evaluates every employee under every plan using the same workforce and comparable utilisation assumptions.

### Step 6: Review results

The dashboard shows:

- employer savings;
- changes in employee burden;
- number of employees better or worse off;
- affected salary and coverage segments;
- sensitivity to healthcare use; and
- potential plan adjustments.

### Step 7: Export an advisory summary

The user downloads aggregate results as CSV and, optionally, a one-page summary. The export must not include row-level sensitive data by default.

## 10. Data design

### Synthetic workforce schema

| Field | Type | Example | Purpose |
|---|---|---|---|
| `employee_id` | string | `EMP-0001` | Synthetic identifier |
| `annual_salary` | number | `48000` | Affordability calculation |
| `salary_band` | category | `40k–59k` | Segment reporting |
| `coverage_tier` | category | `family` | Selects plan parameters |
| `age_band` | category | `35–44` | Optional aggregate analysis |
| `region` | category | `Region A` | Optional cost scenario |
| `utilisation_tier` | category | `medium` | Simplified spending scenario |
| `annual_allowed_cost` | number | `3200` | Modelled covered healthcare use |

The MVP should not include sex, ethnicity, disability status, diagnoses, or other sensitive fields unless there is a clearly justified and carefully governed analytical reason. They are unnecessary for the initial demonstration.

### Plan schema

| Field | Example | Notes |
|---|---:|---|
| `plan_name` | Proposed A | User-defined label |
| `coverage_tier` | Family | One row per tier |
| `annual_premium` | 15,000 | Total premium |
| `employer_contribution_pct` | 80% | Premium share paid by employer |
| `deductible` | 500 | Simplified individual equivalent |
| `coinsurance_pct` | 20% | Employee share after deductible |
| `out_of_pocket_max` | 3,000 | Maximum modelled cost sharing |

### Public-data strategy

The safest MVP does not need individual public health records. It should:

1. Generate a synthetic workforce with transparent distributions.
2. Use configurable, clearly labelled assumptions for healthcare utilisation.
3. Use public aggregate statistics only to calibrate plausible ranges where licensing permits.
4. Cite every external statistic with its geography, year, and definition.
5. Keep a fully synthetic demonstration mode so the project remains reproducible.

Potential sources for later calibration include national statistical agencies, public healthcare expenditure surveys, benefits surveys, and open government data. Statistics from one country or year must not be presented as universally applicable.

### Synthetic-data principles

- Synthetic records must not be derived by lightly modifying real employee records.
- The generator should use explicit probability distributions and a fixed seed.
- Relationships should be plausible but labelled as assumptions.
- The README should state that synthetic data cannot prove real-world effectiveness.
- Example outputs must not be described as client results.

## 11. Calculation engine

### Simplified cost-sharing calculation

For an employee with annual allowed healthcare spending `S`:

```text
Spending subject to deductible = min(S, deductible)

Remaining spending = max(S − deductible, 0)

Pre-cap employee cost sharing
= spending subject to deductible
 + coinsurance percentage × remaining spending

Employee out-of-pocket spending
= min(pre-cap employee cost sharing, out-of-pocket maximum)
```

Then:

```text
Employee total burden
= employee annual premium contribution
 + employee out-of-pocket spending
```

The same allowed-cost scenario should be used for an employee across all plans so differences are caused by plan design rather than inconsistent utilisation assumptions.

### Important simplifications

Real benefit plans may use co-payments, service-specific rules, embedded or aggregate family deductibles, separate pharmacy benefits, exclusions, network discounts, and other provisions. The MVP formula is an educational approximation. The interface and documentation must state this prominently.

### Negative and invalid values

The engine must reject:

- negative premiums, salaries, deductibles, spending, or maximums;
- employer contribution percentages outside 0–100%;
- coinsurance percentages outside 0–100%;
- out-of-pocket maximums below the deductible when the chosen simplified rules make that inconsistent;
- unsupported coverage tiers; and
- missing required values.

## 12. Scenario analysis

### Deterministic MVP scenarios

The MVP can assign each synthetic employee one of three annual allowed-cost scenarios:

- **Low use:** routine or limited utilisation;
- **Medium use:** moderate healthcare utilisation; and
- **High use:** substantial utilisation approaching or exceeding the out-of-pocket maximum.

The monetary values must be configurable and should be labelled assumptions rather than forecasts.

### Sensitivity analysis

The app should allow the user to test:

- a larger share of employees moving into the high-use tier;
- healthcare costs increasing by a selected percentage;
- salary growth differing from healthcare-cost growth;
- coverage mix changing; and
- employer contributions increasing or decreasing.

The purpose is to determine whether a recommendation remains reasonable when assumptions change.

### Monte Carlo simulation — V2

Instead of assigning one fixed annual cost to each employee, V2 can draw costs repeatedly from documented distributions. Each plan is evaluated across hundreds or thousands of simulated years.

Outputs could include:

- median employer cost;
- 5th and 95th percentile costs;
- probability that savings exceed the target;
- distribution of employees above the affordability threshold; and
- stability of group-level conclusions.

Simulation adds uncertainty analysis; it does not make synthetic outputs equivalent to actuarial forecasts.

## 13. Affordability and distributional analysis

### Core measures

- Average and median employee burden.
- Burden as a percentage of salary.
- Percentage of employees above the selected threshold.
- Change in burden from the current plan.
- Count and percentage better off, unchanged, or worse off.
- Results by salary band and coverage tier.
- Results across low-, medium-, and high-use scenarios.

### Distributional questions

The app should make it easy to answer:

- Does the proposed plan shift cost from the employer to employees?
- Are lower-paid employees affected more severely relative to income?
- Does family coverage create a disproportionate burden?
- Are savings dependent on optimistic healthcare-use assumptions?
- Can a targeted contribution reduce harm while retaining most savings?

### Responsible language

The app may report that one group has a higher modelled burden under stated assumptions. It must not claim that an employee is unhealthy, irresponsible, or likely to incur a specific medical condition. It must not turn synthetic categories into statements about real people.

## 14. Recommendation logic

### MVP approach

Recommendations should be transparent, rule-based, and traceable. For example:

```text
If employer savings target is achieved
and the share above the affordability threshold does not increase materially:
    label the scenario "Balanced"

If employer savings target is achieved
but affordability exposure increases materially:
    label the scenario "Savings achieved; employee risk increased"

If employer savings target is not achieved
and affordability also deteriorates:
    label the scenario "Not preferred under selected objectives"
```

The thresholds for “materially” must be user-configurable and displayed in the results.

### Suggested mitigations

The application can test, rather than merely assert, adjustments such as:

- a higher employer contribution for lower salary bands;
- an employer-funded deductible allowance;
- a lower family-coverage contribution rate;
- a lower out-of-pocket maximum; or
- a smaller reduction in the employer contribution.

Each suggestion should be recalculated and compared with the original proposal.

### Optimisation — V2

The optimisation problem can be expressed as:

```text
Minimise:
    employer annual premium cost

Subject to:
    share of employees above affordability threshold ≤ selected maximum
    average employee burden increase ≤ selected maximum
    required plan-value constraints are satisfied
```

A richer version could find a Pareto frontier showing scenarios where employer cost cannot be reduced further without worsening employee affordability.

The optimiser should propose options, not make the final decision.

## 15. Streamlit interface

### Page 1: Introduction

- One-sentence explanation.
- Clear educational-use disclaimer.
- Short diagram of the workflow.
- Button to load a demonstration scenario.

### Page 2: Workforce

- Synthetic workforce generator.
- CSV upload option.
- Data-validation results.
- Headcount, salary, coverage, and utilisation summaries.
- Downloadable CSV template.

### Page 3: Plan designer

- Current-plan form.
- Alternative-plan forms.
- Tooltips defining each field.
- Validation before scenarios can be saved.
- Copy-current-plan button to make comparison easier.

### Page 4: Stress test

- Affordability threshold control.
- Healthcare-cost inflation control.
- Utilisation-mix controls.
- Run-analysis button.

### Page 5: Results

- Employer cost and saving cards.
- Employee average and median burden cards.
- Number and percentage above threshold.
- Cost-versus-affordability scatter plot.
- Burden distribution plot.
- Impact by salary band and coverage tier.
- Winners-and-losers chart.
- Plain-language findings and tested mitigation.

### Page 6: Method and limitations

- Formulas.
- Data assumptions.
- Simplifications.
- Excluded uses.
- Model version and analysis timestamp.

## 16. Visualisations

Recommended visualisations include:

1. **Cost-versus-affordability scatter plot**  
   Each plan is a point. The x-axis shows employer cost; the y-axis shows the percentage of employees above the affordability threshold.

2. **Employee-burden distribution**  
   Compare the current and proposed plans using box plots, violin plots, or histograms.

3. **Impact by salary band**  
   Show the median change in annual burden and burden percentage for each band.

4. **Coverage-tier comparison**  
   Compare employee-only and family coverage outcomes.

5. **Winners and losers**  
   Show counts of employees whose burden decreases, remains approximately unchanged, or increases.

6. **Sensitivity heatmap**  
   Show how results change under different cost-inflation and high-utilisation assumptions.

Every chart should include units, definitions, and accessible colour choices. Important distinctions must not depend on colour alone.

## 17. Technical architecture

```text
Synthetic generator or validated CSV
                 │
                 ▼
        Workforce validation
                 │
                 ├──────────────┐
                 ▼              ▼
         Current plan      Alternative plans
                 │              │
                 └──────┬───────┘
                        ▼
            Cost calculation engine
                        │
              ┌─────────┴─────────┐
              ▼                   ▼
       Employer analysis   Employee analysis
              │                   │
              └─────────┬─────────┘
                        ▼
          Affordability and segment tests
                        │
                        ▼
        Dashboard + advisory summary + export
```

The calculation logic must live in reusable Python modules, not inside Streamlit page code. This enables unit testing and prevents interface changes from silently altering results.

## 18. Recommended technology stack

| Area | Tool | Purpose |
|---|---|---|
| Language | Python 3.11+ | Core development |
| Data processing | pandas, NumPy | Workforce and plan calculations |
| Validation | Pydantic or Pandera | Input and schema validation |
| Interface | Streamlit | Interactive application |
| Charts | Plotly | Interactive comparisons |
| Testing | pytest | Calculation and application tests |
| Code quality | Ruff | Linting and formatting |
| Optimisation, V2 | SciPy or PuLP | Scenario optimisation |
| Simulation, V2 | NumPy/SciPy | Cost distributions and uncertainty |
| Packaging | `pyproject.toml` | Project configuration |
| Deployment | Streamlit Community Cloud or equivalent | Public demonstration |

Machine-learning libraries are unnecessary for the MVP unless a specific, defensible model is added. A transparent calculation and simulation engine is more appropriate than adding AI only for branding.

## 19. Suggested repository structure

```text
benefit-design-stress-lab/
├── .github/
│   └── workflows/
│       └── tests.yml
├── app/
│   ├── app.py
│   ├── pages/
│   │   ├── 1_workforce.py
│   │   ├── 2_plan_designer.py
│   │   ├── 3_stress_test.py
│   │   ├── 4_results.py
│   │   └── 5_methodology.py
│   └── components.py
├── data/
│   ├── README.md
│   ├── examples/
│   │   └── synthetic_workforce.csv
│   └── templates/
│       └── workforce_upload_template.csv
├── notebooks/
│   ├── 01_synthetic_workforce_design.ipynb
│   └── 02_scenario_validation.ipynb
├── reports/
│   └── figures/
├── src/
│   └── benefit_stress_lab/
│       ├── __init__.py
│       ├── config.py
│       ├── schemas.py
│       ├── synthetic.py
│       ├── validation.py
│       ├── plan_rules.py
│       ├── calculations.py
│       ├── affordability.py
│       ├── scenarios.py
│       ├── recommendations.py
│       └── reporting.py
├── tests/
│   ├── test_validation.py
│   ├── test_plan_rules.py
│   ├── test_calculations.py
│   ├── test_affordability.py
│   ├── test_scenarios.py
│   └── test_app_smoke.py
├── .gitignore
├── LICENSE
├── METHODOLOGY.md
├── README.md
├── pyproject.toml
└── requirements.txt
```

Exploration may happen in notebooks, but production calculations must be implemented and tested in `src/`.

## 20. Implementation plan

This schedule assumes approximately 6–10 focused hours per week.

### Week 1: Define the analytical model

- Finalise supported coverage tiers and plan rules.
- Write definitions and formulas.
- Design workforce and plan schemas.
- Create the repository and test framework.
- Document what the model deliberately excludes.

**Deliverable:** calculation specification and validated example inputs.

### Week 2: Build synthetic data and validation

- Implement the workforce generator.
- Create configurable salary and coverage distributions.
- Add CSV validation.
- Produce a demonstration workforce.
- Verify reproducibility with fixed seeds.

**Deliverable:** safe synthetic dataset and input pipeline.

### Week 3: Build the calculation engine

- Calculate employer and employee premium contributions.
- Implement deductible, coinsurance, and out-of-pocket rules.
- Calculate total burden and burden percentage.
- Add tests for normal, boundary, and invalid cases.

**Deliverable:** tested current-plan calculations.

### Week 4: Add scenario comparison

- Compare current and alternative plans.
- Analyse salary and coverage segments.
- Implement deterministic stress scenarios.
- Add transparent recommendation rules.

**Deliverable:** end-to-end analytical outputs.

### Week 5: Build the Streamlit application

- Create workforce and plan forms.
- Add results cards and charts.
- Add example scenarios and error messages.
- Add aggregate exports.

**Deliverable:** working interactive application.

### Week 6: Validate and publish

- Complete tests and continuous integration.
- Perform manual calculation checks.
- Add methodology and responsible-use documentation.
- Create screenshots and a short demo.
- Deploy the application.

**Deliverable:** portfolio-ready MVP.

### Weeks 7–8: Optional V2

Choose only one substantial enhancement:

- Monte Carlo uncertainty simulation; or
- multi-objective plan optimisation.

Finishing one extension well is more valuable than partially implementing several.

## 21. Testing strategy

### Calculation tests

- Zero healthcare use produces zero out-of-pocket spending.
- Spending below the deductible is paid correctly under the simplified rules.
- Coinsurance is applied only after the deductible.
- Cost sharing never exceeds the out-of-pocket maximum.
- Employer and employee premium shares sum to the full premium.
- Total employee burden equals premium contribution plus out-of-pocket spending.
- Burden percentage uses the correct salary and handles invalid zero salary safely.

### Boundary tests

- Spending equals the deductible.
- Spending reaches the out-of-pocket maximum exactly.
- Employer contribution is 0% or 100%.
- Coinsurance is 0% or 100%.
- The employee is exactly at the affordability threshold.

### Validation tests

- Missing columns are reported clearly.
- Duplicate employee IDs are rejected or handled according to a documented rule.
- Negative or nonsensical values are rejected.
- Unsupported categories are reported.
- Empty files fail gracefully.

### Scenario tests

- The same employee utilisation assumptions are used across compared plans.
- Current-versus-current comparison produces no change.
- Aggregate results reconcile to employee-level calculations.
- Segment totals reconcile to the full workforce.
- Exported values match displayed results.

### Reproducibility tests

- A fixed seed generates identical synthetic data.
- Dependencies are pinned or locked.
- One documented command runs the full test suite.
- Continuous integration runs on each push.

## 22. Validation approach

The project should validate correctness in several ways:

1. Manually calculate at least five example employees and compare the results with the engine.
2. Test special cases where the expected result is obvious.
3. Reconcile row-level values with totals and segment summaries.
4. Ask a benefits-informed reviewer to inspect the terminology and assumptions if possible.
5. Clearly distinguish mathematical verification from real-world actuarial validation.

The app can be calculation-correct under its simplified assumptions without being suitable for actual plan pricing. Both facts should be stated.

## 23. Ethics, privacy, and responsible use

### Privacy

- Use synthetic data in the public demonstration.
- Do not commit real employee or claims data.
- Avoid direct identifiers and small-group reporting.
- Apply minimum group-size rules before displaying segment results.
- Export aggregates by default.
- Explain that anonymisation can fail when combinations of attributes identify individuals.

### Fairness

- Compare outcomes across salary and coverage groups.
- Do not infer health status from protected or demographic characteristics.
- Avoid optimisation that simply transfers costs to employees least able to absorb them.
- Make value judgements, such as affordability thresholds and acceptable trade-offs, visible and configurable.
- Keep a human decision-maker responsible for interpreting results.

### Excluded uses

The tool must not be used to:

- deny coverage or services;
- set individual premiums;
- make employment decisions;
- identify individual employees expected to be expensive;
- infer diagnoses or medical conditions;
- replace actuarial advice;
- provide personal financial, medical, tax, or legal advice; or
- claim compliance with a specific jurisdiction's laws.

## 24. Limitations

- The MVP uses simplified plan rules.
- Synthetic data cannot establish real-world accuracy.
- Healthcare use is uncertain and highly skewed.
- Public benchmarks may be specific to a country, year, or population.
- Premiums do not necessarily equal underlying claims costs.
- Fully insured and self-funded employer economics differ.
- Salary-based burden is only one dimension of affordability.
- Household income and other resources are not modelled.
- The same plan can have very different effects under different provider networks and coverage rules.
- Group averages may conceal individual hardship.
- Any recommendation depends on user-selected objectives and assumptions.

These limitations should appear in the app as well as the README.

## 25. README expectations

The README should include:

1. Project title and one-sentence explanation.
2. A screenshot or short GIF.
3. The business question and intended user.
4. A concrete current-versus-proposed example.
5. MVP and V2 feature lists.
6. Architecture diagram.
7. Workforce and plan schemas.
8. Core formulas.
9. Installation and run instructions.
10. Testing instructions.
11. Example findings.
12. Synthetic-data explanation.
13. Limitations and excluded uses.
14. Deployment link.
15. Licence and contribution guidance.

### Suggested README headline

> Stress-test employee health-plan changes before they become employee problems.

### Suggested README introduction

> Benefit Design Stress Lab is an interactive Python and Streamlit application for comparing employer health-plan scenarios. It estimates employer premium savings, models employee premium and out-of-pocket burden, identifies disproportionately affected workforce segments, and tests more balanced alternatives using fully synthetic demonstration data.

## 26. Demo expectations

The public demo should provide three pre-built scenarios:

### Scenario A: Balanced adjustment

A modest plan change produces employer savings with limited employee impact.

### Scenario B: Hidden affordability problem

Average costs appear acceptable, but lower-paid employees with family coverage experience a large burden increase.

### Scenario C: Targeted mitigation

A salary-based employer contribution recovers much of the affordability loss while preserving part of the saving.

A two-minute demonstration should show:

1. Loading the sample workforce.
2. Comparing the current and proposed plans.
3. Finding the affected employee segment.
4. Testing a mitigation.
5. Explaining the limitations.

## 27. Suggested GitHub description

> Interactive employee-benefits scenario modeller that compares employer cost, employee affordability, and distributional impact across health-plan designs using synthetic workforce data.

## 28. Suggested CV bullet

> Built **Benefit Design Stress Lab**, a Python and Streamlit decision-support application that models employer health-plan scenarios, quantifies premium and out-of-pocket impacts across a synthetic workforce, identifies affordability risks by salary and coverage segment, and tests plan adjustments that balance employer savings with employee outcomes.

Once the project is complete, replace general claims with verified evidence such as:

- number of automated tests;
- number of plan scenarios supported;
- runtime for a specified workforce size;
- deployed demo link; or
- a measured result from a clearly labelled synthetic case study.

## 29. Future enhancements

1. Monte Carlo healthcare-cost simulations.
2. Pareto-frontier plan optimisation.
3. Salary-based contribution strategies.
4. Multi-year medical-cost trend scenarios.
5. Separate medical and pharmacy spending.
6. More realistic family deductible structures.
7. Configurable minimum group sizes for privacy.
8. Scenario versioning and audit logs.
9. Aggregate benchmark comparison with licensed public data.
10. Automatically generated executive summaries based only on verified calculations.
11. A secure API for approved aggregate inputs.
12. Containerised deployment and automated releases.

## 30. Definition of done

The MVP is complete when a new user can:

1. Clone the repository and follow the setup instructions.
2. Generate a reproducible synthetic workforce or upload the template.
3. Define a current plan and at least one alternative.
4. Run the comparison without editing code.
5. See reconciled employer and employee cost results.
6. Identify which workforce segments are most affected.
7. Test at least one mitigation.
8. Understand every core formula and assumption.
9. Run the automated tests successfully.
10. Understand why the tool is educational rather than actuarial advice.

## 31. Recommended build decision

Build the transparent six-week MVP before adding predictive AI. The core value of this project is not an opaque model; it is the ability to convert benefits-plan rules into a defensible workforce-impact analysis and communicate the trade-offs clearly.

The first release should therefore prioritise:

- correct calculations;
- safe synthetic data;
- visible assumptions;
- meaningful segment analysis;
- clear advisory language;
- responsible limitations; and
- a polished interactive experience.

Once those foundations are reliable, Monte Carlo simulation or plan optimisation can provide a substantial and credible V2 extension.
