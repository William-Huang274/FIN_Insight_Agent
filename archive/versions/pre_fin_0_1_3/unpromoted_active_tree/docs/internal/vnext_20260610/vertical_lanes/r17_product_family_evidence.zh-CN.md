# R17 Product Family Evidence Runtime Rows

- schema_version: `finsight_r17_product_family_evidence_summary_v0_1`
- generated_at: `2026-06-23T19:09:16Z`
- status: `pass`
- runtime_row_count: `24`
- ticker_count: `5`

## By Source Role

```json
{
  "business_mix_operating_metric": 1,
  "customer_deployment_proxy": 2,
  "industry_operating_metric": 7,
  "product_benchmark_proxy": 2,
  "product_ecosystem_deployment_context": 1,
  "product_generation_edge": 1,
  "technical_product_spec": 10
}
```

## By Signal Authority

```json
{
  "business_mix_signal": 1,
  "customer_deployment_signal": 2,
  "ecosystem_deployment_signal": 1,
  "industry_operating_signal": 7,
  "technical_benchmark_signal": 2,
  "technical_fact": 10,
  "technical_generation_signal": 1
}
```

- thesis_driver_authority_row_count: `24`

## Source Status

```json
[
  {
    "exists": true,
    "file": "nvidia_h100.html",
    "row_count": 8
  },
  {
    "exists": true,
    "file": "nvidia_gb200_nvl72.html",
    "row_count": 5
  },
  {
    "exists": true,
    "file": "nvidia_xai_colossus.html",
    "row_count": 3
  },
  {
    "exists": true,
    "file": "microsoft_ar25.html",
    "row_count": 1
  },
  {
    "exists": true,
    "file": "asml_2025_annual_report.html",
    "row_count": 4
  },
  {
    "exists": true,
    "file": "tel_fy25q4_transcript.pdf",
    "row_count": 1
  },
  {
    "exists": true,
    "file": "honhai_fy2025_4q25.html",
    "row_count": 2
  }
]
```

## Policy

R17 product-family evidence rows add non-financial product/spec/proxy contracts and industry operating metric slots. Product/spec/proxy rows cannot support company financial exact facts; operating metric rows support only their cited company-disclosed metric/period, not Product-KPI exact revenue unless explicitly labeled as such.
