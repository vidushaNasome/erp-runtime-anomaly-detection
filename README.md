# Unsupervised Detection of Behavioural Regressions in ERP Systems

**Field-level runtime traces · Odoo Community Edition 18 · Unsupervised anomaly detection**

This repository accompanies the research project **“Unsupervised Detection of Behavioural Regressions in ERP Systems from Field-Level Runtime Traces: A Controlled Evaluation in Odoo.”** It investigates whether machine-learning detectors trained only on normal enterprise resource planning (ERP) transactions can identify behavioural regressions that do not cause transactions to fail.

> **Scope:** Controlled experiments using synthetic procurement workflows in Odoo CE 18. Results demonstrate feasibility in this setting, **not production readiness**.

## Overview

ERP changes can silently alter quantities, suppliers, planned dates, or the order of operations while transactions still complete successfully. This project captures **ordered, field-level business-state changes** from executed procurement workflows and compares unsupervised detectors using a common evaluation protocol.

The experimental framework covers Odoo's **purchase, inventory, and accounting** modules. It runs Odoo CE 18 in Docker with PostgreSQL 15 and records transaction-level runtime traces through a custom instrumentation layer.

## Research questions

- Can detectors trained on normal traces identify application-level behavioural regressions?
- How do they generalise to legitimate workflow variants absent from training?
- How much do value transitions, user roles, event order, and unseen tokens matter?
- What happens to alert precision when anomalies are rare?
- How repeatable are results across splits, initialisations, and generation seeds?

## Trace representation

Each event captures a transaction identifier, sequence number, user role, ERP module, operation, table, field, business-value change, and additional execution context. Events are ordered within each transaction and encoded as categorical tokens:

```text
USER_ROLE:MODULE:ACTION:TABLE_NAME:FIELD_CHANGED:VALUE_OR_TRANSITION
```

Example:

```text
purchase_user:purchase:CREATE:purchase.order.line:product_qty:HIGH
manager:purchase:WRITE:purchase.order.line:date_planned:NO_DELAY>EXTRA_LONG_DELAY
```

Numerical values are mapped to fixed categorical bands; field updates retain old-to-new transitions. This makes silent changes observable without requiring predefined expected outputs for every transaction.

## Experimental scenarios and datasets

The scenario generator executes **15 procurement workflow types**:

| Group | IDs | Description |
| --- | --- | --- |
| Familiar normal | N1–N5 | Standard procurement, partial receipt, authorised supplier change, rescheduling, and order-line modification |
| Unseen legitimate | G1–G5 | Valid workflow variants excluded from training |
| Anomalous | A1–A5 | Extreme quantities, unexpected date updates, bill-before-receipt ordering, redundant writes, and supplier change during receipt |

| Dataset | Generation seeds | Composition | Transactions |
| --- | --- | --- | ---: |
| Training pool | 42, 60, 100, 120, 200 | N1–N5 only | 1,500 |
| TEST | 30 | 75 familiar normal + 75 unseen legitimate + 150 anomalous | 300 |
| TEST2 | 33 | Same scenario composition, independently generated | 300 |

The normal training pool is split into **1,200 fitting** and **300 validation** transactions for the main calibration. The two test sets are held out. All generated data are synthetic.

## Models

| Detector | Input representation | Anomaly score |
| --- | --- | --- |
| LSTM autoencoder | Ordered categorical token sequences | Mean token reconstruction cross-entropy |
| Isolation Forest | 49 engineered aggregate features (also evaluated with counts) | Negative `score_samples` |
| Local Outlier Factor (LOF) | Token counts or adjacent token-pair counts | Negative `score_samples` |
| One-class SVM | Token counts or adjacent token-pair counts | Negative `score_samples` |

All detectors are fitted on **normal transactions only**. Thresholds are calibrated using normal validation scores, with both 95th- and 99th-percentile operating points reported.

## Evaluation

The study covers seven experiment groups (E1–E7): overall detection, generalisation to unseen legitimate workflows, scenario-level analysis, trace-representation ablations, rare-anomaly prevalence, reproducibility, and additional detector/representation controls. Metrics include ROC-AUC, average precision, precision, recall, F1, false-positive rate, and scenario-level detection rates.

### Selected findings

Across five calibration splits on the primary test set:

| Detector | Mean ROC-AUC ± SD |
| --- | ---: |
| LOF — token-pair counts | **0.989 ± 0.002** |
| LOF — token counts | 0.920 ± 0.003 |
| One-class SVM — token pairs | 0.914 ± 0.006 |
| LSTM autoencoder | 0.893 ± 0.020 |
| Isolation Forest — engineered features | 0.732 ± 0.015 |

On the primary 300-transaction test set with the seed-42 calibration split, LOF on token pairs achieved **0.988 ROC-AUC** and **93.8% F1** (at its 99th-percentile threshold). The LSTM detected all 150 anomalous transactions but also flagged 34 normal transactions. For unseen legitimate workflows, the LSTM flagged **33/75**, compared with **2/75** for LOF on token pairs under the main thresholds.

**Important qualification:** LOF's strong results depended substantially on explicit unseen-token/pair counts. Removing explicit novelty counts reduced its ROC-AUC from **0.988 to 0.902**. The paper also reports sensitivity to calibration, representation, truncation, and low anomaly prevalence. These results should not be interpreted as proof of real-world deployment performance.

## Software environment

The experiments described in the paper used:

- Odoo Community Edition 18
- PostgreSQL 15 and Docker
- Python 3.13
- NumPy 2.4, pandas 2.2, scikit-learn 1.6, TensorFlow 2.21

Consult the repository's actual dependency and configuration files for exact installation and execution commands. **This README does not assume a particular folder layout or entry-point script**, since those were not supplied with the paper.

## Reproducing the experiments

1. Set up the Odoo CE 18 and PostgreSQL 15 environment using the repository's Docker/configuration files.
2. Install and enable the custom runtime-trace instrumentation.
3. Generate normal training workflows using seeds **42, 60, 100, 120, 200**.
4. Generate held-out TEST and TEST2 workflows using seeds **30** and **33**.
5. Construct ordered event tokens and the engineered/count-based representations.
6. Fit detectors on normal training transactions, calibrate thresholds on normal validation transactions, and evaluate both held-out sets.
7. Run the representation, novelty, event-order, prevalence, and repeatability analyses described in the paper.

**Repository maintainer:** Add exact shell commands and paths after uploading the implementation. The paper alone does not specify executable CLI entry points.

## Limitations

- The evaluation uses controlled, synthetic procurement workflows rather than live enterprise data.
- Legitimate workflows unseen during training can trigger false alarms.
- Some anomaly detection relies on novel tokens rather than learned behaviour alone.
- Certain recorded redundant-write effects are smaller than the intended injected perturbation.
- Results do not establish production readiness or generalisation to other ERP systems.

## Citation

If you use this repository or its experimental framework, please cite the accompanying research work.
## Availability and licensing

The accompanying paper describes the instrumentation, scenario generator, synthetic datasets, detector code, and generation seeds as repository materials. 

**License:** The repository maintainer intends to release their **original, independently owned code** under the [MIT License](LICENSE).