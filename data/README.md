# Data

Everything in this folder is synthetic. No file here is derived from real employees or claims.

| File | Contents |
|---|---|
| `examples/synthetic_workforce.csv` | 500 synthetic employees from the default generator settings (seed 2026) |
| `templates/workforce_upload_template.csv` | The column layout the upload page expects, with three example rows |

## Rules

- Never commit real workforce or claims data. `.gitignore` blocks everything in this folder except the files above.
- Do not include names, contact details, diagnoses, prescriptions, or any other identifying or medical detail in an upload. The app drops columns it does not use.
- Anonymised data can still identify people when several attributes are combined. Treat any real extract as sensitive even without names.

## Regenerating the files

```bash
python -c "from benefit_stress_lab.synthetic import generate_workforce; generate_workforce().to_csv('data/examples/synthetic_workforce.csv', index=False)"
python -c "from benefit_stress_lab.validation import workforce_template; workforce_template().to_csv('data/templates/workforce_upload_template.csv', index=False)"
```

The synthetic distributions are assumptions chosen to look plausible. They are not calibrated to any real employer, country, or year, and results built on them cannot establish real-world accuracy.
