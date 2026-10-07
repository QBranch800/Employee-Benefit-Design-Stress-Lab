# Method and limitations

Benefit Design Stress Lab applies health-plan rules to every employee in a workforce and compares the results across plans. The calculations are exact under the simplified rules described here. That does not make them suitable for pricing a real plan: the rules leave out much of what a real plan does, and the demonstration data is synthetic.

## What is calculated

For each employee under each plan:

```text
employer premium contribution = annual premium × employer contribution %
employee premium contribution = annual premium − employer premium contribution

spending subject to deductible = min(allowed cost, deductible)
remaining spending             = max(allowed cost − deductible, 0)
cost sharing before the cap    = spending subject to deductible
                                 + coinsurance % × remaining spending
out-of-pocket spending         = min(cost sharing before the cap, out-of-pocket maximum)

allowance paid by employer     = min(out-of-pocket spending, employer allowance)
employee out-of-pocket         = out-of-pocket spending − allowance paid by employer

total employee burden          = employee premium contribution + employee out-of-pocket
burden percentage              = total employee burden ÷ annual salary × 100
employer cost                  = employer premium contribution + allowance paid by employer
```

Allowed cost is the value of covered healthcare the employee used in the year. Premiums, deductibles, coinsurance, maximums, and allowances are set separately for each coverage tier.

A plan can also give lower-paid employees a higher employer contribution. Employees earning below the chosen salary receive the higher of that rate and their tier's normal rate, so this support can never reduce what the employer pays for them.

### Worked example

An employee earns 38,000, has family coverage, and uses 9,000 of covered healthcare.

| | Current plan | Proposed plan |
|---|---:|---:|
| Family premium | 15,000 | 12,500 |
| Employer contribution | 80% | 70% |
| Deductible, coinsurance, maximum | 1,000, 20%, 6,000 | 3,000, 30%, 10,000 |
| Employer premium contribution | 12,000 | 8,750 |
| Employee premium contribution | 3,000 | 3,750 |
| Out-of-pocket spending | 1,000 + 20% × 8,000 = 2,600 | 3,000 + 30% × 6,000 = 4,800 |
| Total employee burden | 5,600 | 8,550 |
| Burden as a share of salary | 14.7% | 22.5% |

The employer saves 3,250 on this employee. The employee pays 2,950 more, which is 7.8 percentage points of salary.

## Workforce data

Each row is one employee.

| Field | Meaning |
|---|---|
| `employee_id` | Anonymous identifier, unique per row |
| `annual_salary` | Used to measure affordability |
| `salary_band` | Below 40k, 40k–59k, 60k–79k, 80k–119k, 120k and above |
| `coverage_tier` | `employee_only` or `family` |
| `utilisation_tier` | `low`, `medium`, or `high` healthcare use |
| `annual_allowed_cost` | Covered healthcare used in the year |
| `age_band`, `region` | Optional; kept for reference and not used in any calculation |

### Synthetic workforce

The generator draws from explicit distributions with a fixed random seed, so the same settings always produce the same workforce. Every distribution is an assumption chosen to look plausible. None is calibrated to a real employer, country, or year.

- **Salaries** follow a lognormal distribution around the chosen median, limited to the chosen lowest and highest salary.
- **Family coverage** is more likely in the middle age bands, scaled so the overall share is close to the chosen value.
- **Healthcare use** is assigned independently of age, salary, and region. The model deliberately does not infer health from demographic characteristics.
- **Allowed cost** starts from an assumed yearly amount for each level of use (defaults: 600 low, 3,500 medium, 18,000 high, for one employee-only member). Family coverage multiplies it by 2.6. Each employee's cost then varies around the amount for their level, in a way that keeps the average for each level unchanged.

### Uploaded workforce

An uploaded CSV is checked before it is used:

- Required columns must be present and complete.
- Duplicate employee IDs are rejected. They are never silently dropped.
- Salaries must be greater than zero. Allowed costs cannot be negative.
- Coverage and use tiers must be supported values. Capitalisation, spaces, and hyphens are forgiven.
- Salary bands are recomputed from salary.
- Columns the model does not use are dropped with a warning, because they may identify people.

## Comparing plans

The first plan is the baseline. Every employee keeps the same allowed cost under every plan, so any difference between plans comes from plan design alone.

- **Change in burden** is measured for each employee against their own baseline result.
- An employee is **better off** or **worse off** when their yearly burden changes by more than the unchanged tolerance (default 50). Otherwise they are **unchanged**.
- An employee is **above the threshold** when their burden percentage is strictly greater than the affordability threshold (default 10% of salary). Exactly at the threshold does not count.

The affordability threshold is a scenario parameter chosen by the user. It is not a legal, regulatory, or clinical standard.

## Segments and privacy

Results are reported by salary band, by coverage tier, and by both together. A segment with fewer than the minimum group size (default 10) has its figures withheld. Its headcount is still shown. Small groups can identify individuals and reveal their healthcare use.

The **most affected segment** is the salary band and coverage tier combination, among those large enough to report, with the largest median rise in burden as a share of salary.

Exports contain aggregate results only. Anonymised data can still identify people when several attributes are combined, so real workforce data should not be used without proper governance.

## Stress assumptions

Stress is applied to the workforce once, in this order, before any plan is evaluated:

1. **Coverage mix.** A chosen share of employees switches between employee-only and family coverage. Their allowed cost is multiplied or divided by the family multiplier.
2. **High use.** A chosen share of low and medium users becomes high users. Their allowed cost rises to at least the assumed high-use amount for their coverage tier.
3. **Healthcare cost change.** Every allowed cost is scaled by the chosen percentage. Premiums are scaled too, if selected.
4. **Salary growth.** Salaries are scaled and salary bands recomputed.

Deductibles, coinsurance rates, and maximums stay fixed in money terms. When costs rise, employees therefore absorb a growing share of the bill.

The employees who switch are chosen at random with a fixed seed. A larger share always includes the employees chosen for a smaller share, so results for different shares are comparable.

## Assessment labels

Each alternative receives a label from two questions. Both limits are set by the user and shown with the results.

| | Share above threshold does not rise materially | Share above threshold rises materially |
|---|---|---|
| **Savings target met** | Balanced | Savings achieved; employee risk increased |
| **Savings target missed** | Affordability maintained; savings below target | Not preferred under selected objectives |

The savings target defaults to 5% of employer cost. A material rise defaults to more than 2 percentage points. Labels describe a plan against the chosen objectives. They do not select a plan.

## Tested adjustments

For a chosen alternative, the app builds adjustments that soften it and recalculates each one on the same workforce:

1. Employees earning below 60k keep at least the current plan's employer contribution rate.
2. The employer funds an allowance equal to the rise in the deductible.
3. Family coverage keeps the current plan's employer contribution rate.
4. The out-of-pocket maximum stays at the current level, or at the new deductible if that is higher.
5. The employer contribution falls only halfway to the proposal.

An adjustment is built only where it would change something. One is highlighted by a fixed rule: among adjustments that reduce the share above the threshold, take a Balanced one with the largest saving; otherwise the one that meets the savings target with the lowest share above the threshold; otherwise the one with the lowest share above the threshold.

## Sensitivity analysis

The sensitivity grid reruns the full comparison across combinations of healthcare cost change and share moved into high use. The contribution trade-off reruns one plan with the employer contribution set to each rate from 50% to 100%, applied to both coverage tiers. Both show whether a conclusion survives a change in assumptions.

## Uncertainty simulation

The single run gives every employee one assumed yearly cost. The simulation replays the year many times (500 by default) and recalculates every plan each time, to show how far the results could move with different luck in who needs care.

Each simulated year, an employee's allowed cost is built in three steps:

1. **Reshuffle.** The employee draws a cost at random, with replacement, from the costs of employees with the same coverage tier in the workforce, after any stress assumptions. The mix of low and high costs is preserved on average, the costs land on different people, and the number of high-cost cases varies from year to year.
2. **Individual variation.** The cost is multiplied by a random factor with an average of 1 and a chosen spread (25% by default), drawn independently for each employee and year from a lognormal distribution.
3. **Year-wide variation.** Every cost in that year is multiplied by one shared random factor with an average of 1 and a chosen spread (8% by default), also lognormal. This stands for years in which care is dearer or cheaper for everyone.

Salaries, coverage tiers, plan rules, and premiums stay fixed. Every plan is evaluated on the same simulated costs in each year, so differences between plans come from plan design and not from different draws. The random numbers come from a fixed seed, so the same settings always give the same simulated years. With all three steps switched off, every simulated year equals the single run.

For each plan the simulation reports:

- the typical year (the median) and the 5th and 95th percentiles of the employer's cost, the employer's saving, and the share of employees above the threshold;
- the share of years in which the saving meets the target, and in which the share above the threshold rises by more than the materiality limit;
- the share of years that earn the same assessment label as the single run;
- for each salary band and coverage tier, the average share of years in which an employee is above the threshold. Small groups are withheld as elsewhere.

What the simulation does not do:

- Years are independent. An employee with one costly year is no more likely to have another, which understates the risk for people with long-term conditions.
- A cost is drawn independently of salary, age, and region, as in the synthetic workforce.
- Premiums are not repriced in response to simulated costs. Where a plan has no employer allowance, the employer's cost is made up of premiums and is the same in every simulated year.
- The spreads are assumptions chosen by the user, not estimates from claims data. The ranges describe how the model behaves under those assumptions. They are not confidence intervals for a real workforce, and the simulation does not turn synthetic results into an actuarial forecast.

## Simplifications

Real plans include features this model leaves out:

- co-payments and service-specific rules;
- embedded or aggregate family deductibles (family amounts here are single values, by default twice the individual amounts);
- separate pharmacy benefits;
- provider networks, negotiated discounts, and exclusions;
- tax treatment, health savings accounts, and flexible spending accounts;
- coordination of benefits;
- coverage tiers beyond employee-only and family.

## Excluded uses

The tool must not be used to:

- deny coverage or services;
- set individual premiums;
- make employment decisions;
- identify individual employees expected to be expensive;
- infer diagnoses or medical conditions;
- replace actuarial advice;
- give personal financial, medical, tax, or legal advice;
- claim compliance with any jurisdiction's laws.

## Limitations

- Synthetic data cannot establish real-world accuracy.
- Healthcare use is uncertain and highly skewed. The single run gives each employee one assumed yearly cost. The uncertainty simulation varies it, under spreads that are assumed and not estimated from data.
- Premiums do not necessarily equal underlying claims costs, and the economics of fully insured and self-funded employers differ.
- Burden relative to salary is only one dimension of affordability. Household income and other resources are not modelled.
- Group averages and medians can conceal individual hardship.
- Any assessment depends on the objectives and assumptions the user selects.

## Verification

Automated tests check the calculations against five employees worked by hand, the boundary cases (spending exactly at the deductible, exactly reaching the maximum, contribution rates of 0% and 100%, an employee exactly at the threshold), and reconciliation of segment totals to workforce totals. They also check that the simulation reproduces the single run when all variation is switched off, gives the same years for the same seed, and matches a case whose probability is known. This verifies the arithmetic. It is not actuarial validation.
