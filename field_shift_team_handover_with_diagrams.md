# Field Shift

## Project Progress, Data Foundation & Proposed API Design

**Project:** Field Shift --- Adapting Farms with NASA Data\
**Pilot study area:** Agricultural land near Guelma city, Guelma Wilaya,
Algeria\
**Document purpose:** Give the team a concise, shared understanding of
the work completed, the proposed system design, and the next development
steps.

------------------------------------------------------------------------

## 1. Project in One Minute

Field Shift is a farmer decision-support prototype. It will use
environmental and soil information together with farmer-provided crop
history and priorities to compare crop-rotation strategies.

The system should: - compare at least three crop-rotation strategies; -
score them against the farmer's priorities; - explain benefits,
trade-offs, risks, and evidence; - show missing information and
uncertainty.

**It supports farmer and agronomist decisions; it does not replace
agronomic expertise.**

## 2. Study Area

The pilot polygon has been divided into four field units:

  Field ID              Area
  ----------- --------------
  FIELD_001         11.86 ha
  FIELD_002          4.88 ha
  FIELD_003          5.78 ha
  FIELD_004          7.60 ha
  **Total**     **30.12 ha**

These are analysis units in the pilot study. The crops currently grown
in these fields have not been verified. Crop history must therefore be
collected from farmers or reliable farm records.

------------------------------------------------------------------------

## 3. Data Collected

### Data pipeline

``` mermaid
flowchart TD
    A["Study area polygon + 4 fields"] --> B["NASA POWER<br/>Climate data"]
    A --> C["Sentinel-2<br/>Vegetation indices"]
    A --> D["SoilGrids<br/>Soil estimates"]
    B --> E["Cleaning and aggregation"]
    C --> E
    D --> E
    E --> F["Integrated field-month dataset"]
    F --> G["EDA and temporal analysis"]
    G --> H["Feature engineering"]
    H --> I["Prepared features for future model"]
```

### 3.1 NASA POWER --- Climate

-   Daily data collected from **2024-01-01 to 2025-12-31**.
-   Sampling point: latitude **36.4750**, longitude **7.4659**.
-   Variables: mean, maximum and minimum temperature; precipitation;
    relative humidity; solar radiation.
-   Prepared daily data: **731 records**, with no missing values in the
    collected period.
-   Monthly aggregation: **24 records**.

**Limitation:** two years are not a long-term climate normal and cannot
establish a climate trend. The point-based climate series is shared as
regional context across the four nearby fields.

### 3.2 Sentinel-2 --- Vegetation

Monthly metrics prepared for each field:

-   NDVI --- vegetation greenness/activity indicator.
-   EVI --- enhanced vegetation index.
-   NDMI --- vegetation/canopy moisture-related indicator.

Prepared table: **96 records** (24 months × 4 fields).

Exploratory overall averages: - NDVI: approximately **0.530** - EVI:
approximately **0.366** - NDMI: approximately **0.086**

**Limitation:** NDVI does not identify crop type by itself. The monthly
image count is not a direct measure of clear-pixel coverage or image
quality.

### 3.3 SoilGrids --- Soil

Soil estimates were sampled using field centroids/nearest pixels after
the initial polygon extraction returned missing values.

Selected estimates for the 0--5 cm layer:

  Property                   FIELD_001   FIELD_002--004
  --------------------- -------------- ----------------
  Clay                           34.1%            35.2%
  Sand                           31.4%            31.0%
  Silt                           34.6%            33.8%
  pH                               7.1              7.0
  Soil organic carbon        23.9 g/kg        24.9 g/kg
  CEC                     22.5 cmol/kg     23.0 cmol/kg

**Limitations:** SoilGrids has a nominal resolution of 250 m. These are
gridded estimates, not laboratory tests. FIELD_002, FIELD_003 and
FIELD_004 returned the same sampled coordinates/values in the current
extraction; this does not prove their soils are identical. Verify
nitrogen units/scaling against the original metadata before using that
variable.

------------------------------------------------------------------------

## 4. Data Preparation and Analysis Completed

### Integrated dataset

File:

`data/guelma_integrated_field_monthly_2024_2025.csv`

-   **96 rows × 41 columns**
-   Combines field identifiers/areas, Sentinel-2 metrics, climate
    variables and soil attributes.

### Exploratory analysis

Created and ran EDA scripts and plots, including:

-   NDVI by field
-   Monthly climate context
-   NDVI versus rainfall

### Temporal analysis

Created a corrected temporal workflow that produces:

-   seasonal vegetation summaries;
-   year-over-year seasonal comparisons;
-   rainfall--NDVI lag correlations;
-   same-month NDVI anomalies;
-   per-field time-series plots.

Season-year handling was corrected so December belongs to the following
winter. Incomplete winter periods must not be compared with complete
winters.

**Interpretation:** the analysis is exploratory. There are only 24
monthly observations per field, and the climate series is shared across
fields. Correlation does not demonstrate causation.

### Feature engineering

Script:

`feature_engineering_guelma.py`

Outputs:

-   `outputs/feature_engineering/guelma_field_month_features.csv`
-   `outputs/feature_engineering/guelma_field_season_features.csv`

Results: - Monthly features: **96 rows × 57 columns** - Seasonal
features: **36 rows**

Features include season/year fields, cyclical month encodings,
month-to-month vegetation-index changes, previous-three-month climate
summaries, image-count flags, soil texture checks, and
provenance/quality notes.

Validation found no duplicate field-month records and no missing values
in key NDVI fields. Only four complete winter records were available
(one per field); incomplete winter records were flagged.

------------------------------------------------------------------------

## 5. Proposed System Architecture

``` mermaid
flowchart TD
    A["Farmer / User"] --> B["Farm Decision Request<br/>JSON input"]
    B --> C["Input validation"]
    C --> D["Environmental dataset<br/>NASA POWER + Sentinel-2 + SoilGrids"]
    C --> E["Crop Catalog"]
    C --> F["Farmer crop history<br/>and preferences"]
    D --> G["Feature and data-quality layer"]
    E --> H["Crop and rotation evaluation"]
    F --> H
    G --> H
    H --> I["Suitability scoring"]
    I --> J["Compare 3 rotation strategies"]
    J --> K["Recommendation Response<br/>JSON output"]
    K --> L["Farmer-facing explanation"]
```

The Request carries farmer/farm information and references the
environmental dataset. Large environmental time series and the crop
catalog should be stored separately and referenced by ID, rather than
copied into every request.

------------------------------------------------------------------------

## 6. Proposed Request JSON

The Request is the information sent by the farmer/application to the
recommendation system.

**Important:** this is an example contract. The crop history below is
deliberately empty because the actual crops in the pilot fields are not
yet verified. The soil values are illustrative of the current SoilGrids
estimates for FIELD_001; they should be loaded with their provenance in
the implementation.

``` json
{
  "schema_version": "1.0",
  "request_id": "generated-unique-id",
  "language": "en",

  "farm": {
    "farm_id": "FARM_001",
    "country": "Algeria",
    "wilaya": "Guelma",
    "commune": "Guelma"
  },

  "planning": {
    "start_year": 2026,
    "start_season": "autumn",
    "planning_horizon_seasons": 3
  },

  "farmer_preferences": {
    "weights": {
      "water_saving": 35,
      "soil_improvement": 30,
      "income": 20,
      "risk_reduction": 10,
      "forage_value": 5
    },
    "preferred_crop_ids": [],
    "excluded_crop_ids": []
  },

  "fields": [
    {
      "field_id": "FIELD_001",
      "area_hectares": 11.86,

      "crop_history": [],

      "soil": {
        "ph": 7.1,
        "organic_carbon_g_kg": 23.9,
        "clay_percent": 34.1,
        "sand_percent": 31.4,
        "silt_percent": 34.6,
        "source": "SoilGrids",
        "resolution_m": 250,
        "measurement_type": "gridded_estimate"
      },

      "water": {
        "availability": "unknown",
        "irrigation_system": "unknown"
      }
    }
  ],

  "environmental_data": {
    "dataset_id": "guelma_integrated_field_monthly_2024_2025",
    "period": {
      "start": "2024-01-01",
      "end": "2025-12-31"
    },
    "sources": [
      "NASA_POWER",
      "COPERNICUS_SENTINEL_2",
      "SoilGrids"
    ]
  }
}
```

### Request fields --- what they mean

  -----------------------------------------------------------------------
  Section                             Purpose
  ----------------------------------- -----------------------------------
  `farm`                              Identifies the farm and its
                                      administrative location.

  `planning`                          Defines when planning starts and
                                      how many seasons to consider.

  `farmer_preferences`                Defines the farmer's priorities and
                                      crop constraints.

  `fields`                            Describes each field, its crop
                                      history, soil and water situation.

  `environmental_data`                References the prepared
                                      environmental dataset.
  -----------------------------------------------------------------------

The example weights sum to 100. They are starting values only; farmers
should be able to adjust them. Crop IDs should come from the controlled
Crop Catalog. Unknown crop history must remain unknown, not be guessed.

------------------------------------------------------------------------

## 7. Proposed Response JSON

The Response is the result returned by the system after validating the
Request, evaluating possible rotations and comparing their suitability.

``` json
{
  "response_schema_version": "1.0",
  "request_id": "generated-unique-id",
  "model_version": "SI-Model-0.1",

  "analysis_summary": {
    "farm_id": "FARM_001",
    "field_id": "FIELD_001",
    "planning_horizon_seasons": 3
  },

  "data_quality": {
    "status": "incomplete",
    "missing_information": [
      "crop_history",
      "water_availability",
      "irrigation_system"
    ],
    "limitations": [
      "Climate data covers 2024-2025 only",
      "Soil properties are 250m gridded estimates"
    ]
  },

  "strategies": [
    {
      "strategy_id": "STRATEGY_A",
      "type": "current_practice_baseline",
      "crop_sequence": [],
      "overall_score": null,
      "criteria_scores": {
        "water_saving": null,
        "soil_improvement": null,
        "income": null,
        "risk_reduction": null,
        "forage_value": null
      },
      "advantages": [],
      "risks": [],
      "explanation": []
    },
    {
      "strategy_id": "STRATEGY_B",
      "type": "soil_focused",
      "crop_sequence": [],
      "overall_score": null,
      "criteria_scores": {},
      "advantages": [],
      "risks": [],
      "explanation": []
    },
    {
      "strategy_id": "STRATEGY_C",
      "type": "water_focused",
      "crop_sequence": [],
      "overall_score": null,
      "criteria_scores": {},
      "advantages": [],
      "risks": [],
      "explanation": []
    }
  ],

  "final_recommendation": {
    "recommended_strategy_id": null,
    "reason": null,
    "confidence": "insufficient_data",
    "conditions": [],
    "warnings": []
  },

  "next_actions": [
    "Collect crop history from the farmer",
    "Confirm water availability and irrigation",
    "Validate soil information where possible"
  ]
}
```

**The empty arrays and `null` scores are intentional.** This is a schema
proposal, not a real model result. If crop history is missing, Strategy
A cannot be presented as the farmer's actual current practice. The
system should report that the baseline is unavailable.

### Response structure

  -----------------------------------------------------------------------
  Section                             Purpose
  ----------------------------------- -----------------------------------
  `analysis_summary`                  States which farm/field was
                                      analysed.

  `data_quality`                      Reports missing information and
                                      dataset limitations.

  `strategies`                        Returns three comparable rotation
                                      options.

  `overall_score`                     Gives each strategy's aggregate
                                      suitability score.

  `criteria_scores`                   Shows the score for each farmer
                                      priority.

  `advantages`, `risks`,              Makes the result understandable and
  `explanation`                       auditable.

  `final_recommendation`              Identifies the preferred option,
                                      confidence and conditions.

  `next_actions`                      Lists information or checks still
                                      needed.
  -----------------------------------------------------------------------

------------------------------------------------------------------------

## 8. Proposed Suitability Index (SI)

For this project, we propose an operational **Suitability Index (SI)**
to compare strategies on a common 0--100 scale. This is our proposed
project methodology; it is not claimed to be the official expansion of
"SI" in the challenge description.

\[ SI = `\sum`{=tex}\_{i=1}\^{n} w_i s_i \]

Where: - (w_i) = normalized weight of criterion (i); - (s_i) = strategy
score for criterion (i), from 0 to 100; - the weights sum to 1 (or
100%).

Example farmer priorities:

  Criterion            Weight
  ------------------ --------
  Water saving            35%
  Soil improvement        30%
  Income                  20%
  Risk reduction          10%
  Forage value             5%

The scoring rules for each criterion still need to be defined using crop
requirements, rotation rules, available environmental data, water
conditions and agronomic validation. Do not assign arbitrary scores.

**Keep two outputs separate:** - **Suitability score:** how well the
strategy meets the selected criteria. - **Confidence level:** how
reliable the score is given data coverage and completeness.

A high suitability score does not necessarily mean high confidence.

------------------------------------------------------------------------

## 9. Three Strategy Types to Compare

``` mermaid
flowchart LR
    A["Strategy A<br/>Current-practice baseline"] --> D["Compare"]
    B["Strategy B<br/>Soil-focused rotation"] --> D
    C["Strategy C<br/>Water-focused rotation"] --> D
    D --> E["Rank + explain<br/>scores, trade-offs, risks"]
```

-   **A --- Current-practice baseline:** uses the farmer's existing
    rotation, only if crop history is supplied.
-   **B --- Soil-focused:** prioritizes soil improvement and crop
    diversification while respecting crop and water constraints.
-   **C --- Water-focused:** prioritizes water efficiency and resilience
    to water limitations.

These are comparison categories, not yet generated crop sequences. The
Crop Catalog and rotation rules must be built before the system can
generate scientifically defensible sequences.

------------------------------------------------------------------------

## 10. Current Project Files

Working directory:

`~/Desktop/FeildShit-SI-Model`

``` text
FeildShit-SI-Model/
├── data/
│   ├── guelma_fields_summary.csv
│   ├── guelma_nasa_power_daily_2024_2025.csv
│   ├── guelma_nasa_power_monthly_2024_2025.csv
│   ├── guelma_sentinel2_monthly.csv
│   ├── guelma_soilgrids_fields.csv
│   ├── guelma_study_area.geojson.geojson
│   └── guelma_integrated_field_monthly_2024_2025.csv
├── outputs/
│   └── feature_engineering/
├── venv/
├── merge_guelma_data.py
├── eda_guelma.py
├── temporal_analysis_guelma_v2.py
└── feature_engineering_guelma.py
```

------------------------------------------------------------------------

## 11. Progress and Remaining Work

### Completed

-   Defined the Guelma pilot study area and four field units.
-   Collected and prepared NASA POWER climate data for 2024--2025.
-   Prepared monthly Sentinel-2 NDVI, EVI and NDMI metrics.
-   Retrieved SoilGrids estimates and documented their resolution
    limitations.
-   Integrated the datasets into a field-month table.
-   Performed initial EDA and temporal analysis.
-   Engineered monthly and seasonal features and ran validation checks.
-   Drafted the farmer-facing Request JSON.
-   Drafted the system Response JSON.
-   Proposed an initial weighted Suitability Index framework.

### Remaining

1.  **Crop Catalog:** compile locally relevant crops and their
    calendars, water needs, soil effects, and rotation compatibility;
    validate with agronomic sources or experts.
2.  **Farmer data collection:** obtain crop history, irrigation and
    water availability.
3.  **Scoring methodology:** define transparent, evidence-based scoring
    rules for each criterion.
4.  **Rotation generator:** generate valid crop sequences using crop
    calendars and rotation constraints.
5.  **Recommendation engine:** rank strategies and produce explanations,
    risks and confidence.
6.  **Validation:** review results with farmers/agronomists and test on
    additional fields.

## 12. Scientific Guardrails

-   NDVI is not a crop classifier by itself.
-   Do not invent crop history or assume current crops.
-   Two years of climate observations do not establish a long-term
    climate trend.
-   Do not count the shared climate series as independent observations
    for each field.
-   SoilGrids estimates are not field-specific laboratory measurements.
-   Preserve data source, period, spatial resolution, units and
    uncertainty.
-   Do not turn missing values into zero.
-   Recommendations must be explainable and agronomically validated.

------------------------------------------------------------------------

## Team Handover --- Current Status

**What exists now:** a pilot-area data foundation, integrated
environmental dataset, exploratory and temporal analyses, engineered
features, and draft Request/Response contracts.

**What does not exist yet:** a validated crop catalog, scientifically
defined SI scoring functions, a working rotation generator, or a
validated recommendation engine.

**Next task:** build the Crop Catalog. It is the knowledge base required
before we can calculate crop suitability or generate reliable crop
rotations.
