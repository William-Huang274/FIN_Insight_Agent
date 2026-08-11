# Product Slot And Relationship Graph

- status: `pass`
- company_count: `603`
- product_slot_count: `6521`
- product_family_count: `79`
- node_count: `8187`
- edge_count: `25251`
- with_url_slot_count: `6521`
- with_family_bound_runtime_slot_count: `6517`

## Slot Status

| status | count |
| --- | ---: |
| bounded_context_slot | 103 |
| company_route_needs_family_binding | 4 |
| filings_taxonomy_slot | 1890 |
| official_surface_slot | 4392 |
| product_kpi_exact_slot | 132 |

## Edge Types

| relationship | count |
| --- | ---: |
| BELONGS_TO_FAMILY | 6521 |
| CHANNEL_OR_DISTRIBUTION_CONTEXT | 99 |
| COMPETES_WITH | 3420 |
| COMPLEMENTS_WITH | 18 |
| COMPONENT_INPUT_TO | 18 |
| ENABLES_PRODUCTION_FOR | 56 |
| FAMILY_HAS_PRODUCT_SLOT | 6521 |
| HAS_PRODUCT_FAMILY | 663 |
| HAS_PRODUCT_SLOT | 6521 |
| INFRASTRUCTURE_COMPLEMENT_TO | 27 |
| INFRASTRUCTURE_SUPPLIER_TO | 24 |
| INPUT_OR_COMPLEMENT_TO | 12 |
| IN_PRODUCT_FAMILY | 663 |
| MANUFACTURING_DEPENDENCY_FOR | 46 |
| OFFICIAL_CUSTOMER_DEPLOYMENT_EVENT | 222 |
| OFFICIAL_SUPPLY_CHAIN_RELATIONSHIP | 147 |
| PUBLIC_ORDER_OR_TENDER_CONTEXT | 273 |

## Sample Slots

- `000660.KS` `memory` `DBL`: `official_surface_slot` urls=3 evidence=1
- `000660.KS` `memory` `Memory / Storage Semiconductors`: `official_surface_slot` urls=3 evidence=2
- `000660.KS` `memory` `Products & Solutions 새창`: `official_surface_slot` urls=3 evidence=1
- `000660.KS` `memory` `SK hynix`: `official_surface_slot` urls=3 evidence=1
- `000660.KS` `memory` `SKhynix Main`: `official_surface_slot` urls=3 evidence=1
- `005930.KS` `foundry` `Foundry / Wafer Fabrication`: `official_surface_slot` urls=5 evidence=2
- `005930.KS` `memory` `Memory / Storage Semiconductors`: `official_surface_slot` urls=5 evidence=4
- `005930.KS` `memory` `Samsung Electronics`: `official_surface_slot` urls=5 evidence=1
- `1211.HK` `battery_charging_autonomy` `Battery / Charging / Autonomy`: `official_surface_slot` urls=8 evidence=3
- `1211.HK` `battery_charging_autonomy` `battery`: `bounded_context_slot` urls=8 evidence=2
- `1211.HK` `ev_vehicle_platform` `BYD ATTO 3`: `official_surface_slot` urls=7 evidence=2
- `1211.HK` `ev_vehicle_platform` `Battery / Charging / Autonomy`: `official_surface_slot` urls=7 evidence=3
- `1211.HK` `ev_vehicle_platform` `Electric Cars, Sedans and SUVs I BYD AUTO`: `official_surface_slot` urls=7 evidence=2
- `1211.HK` `ev_vehicle_platform` `General Auto / Mobility`: `official_surface_slot` urls=7 evidence=3
- `1211.HK` `ev_vehicle_platform` `HAN EV`: `official_surface_slot` urls=7 evidence=2
- `1211.HK` `ev_vehicle_platform` `battery`: `bounded_context_slot` urls=8 evidence=2
- `1211.HK` `ev_vehicle_platform` `electric vehicle`: `bounded_context_slot` urls=8 evidence=1
- `2308.TW` `power_cooling` `Fans and Thermal Management`: `official_surface_slot` urls=2 evidence=2
- `2308.TW` `power_cooling` `Power and Grid`: `official_surface_slot` urls=2 evidence=2
- `2308.TW` `power_cooling` `Power and System`: `official_surface_slot` urls=2 evidence=2
- `2308.TW` `power_grid_cooling` `Fans and Thermal Management`: `official_surface_slot` urls=2 evidence=2
- `2308.TW` `power_grid_cooling` `Power and Grid`: `official_surface_slot` urls=2 evidence=2
- `2308.TW` `power_grid_cooling` `Power and System`: `official_surface_slot` urls=2 evidence=2
- `2317.TW` `electronics_manufacturing_services` `Electronics Manufacturing / ODM`: `official_surface_slot` urls=6 evidence=5
- `2382.TW` `electronics_manufacturing_services` `Electronics Manufacturing / ODM`: `official_surface_slot` urls=8 evidence=5
- `300750.SZ` `battery_energy_storage_components` `Battery Recycling`: `official_surface_slot` urls=3 evidence=1
- `300750.SZ` `battery_energy_storage_components` `Brands`: `official_surface_slot` urls=3 evidence=1
- `300750.SZ` `battery_energy_storage_components` `Commercial Application`: `official_surface_slot` urls=3 evidence=1
- `300750.SZ` `battery_energy_storage_components` `General Energy / Industrials`: `official_surface_slot` urls=3 evidence=2
- `300750.SZ` `battery_energy_storage_components` `Hybrid Solutions`: `official_surface_slot` urls=3 evidence=1
- `300750.SZ` `battery_energy_storage_components` `Passenger Vehicles`: `official_surface_slot` urls=3 evidence=1
- `300750.SZ` `battery_energy_storage_components` `Service Brand`: `official_surface_slot` urls=3 evidence=1
- `300750.SZ` `battery_energy_storage_components` `Service Center`: `official_surface_slot` urls=3 evidence=1
- `300750.SZ` `battery_energy_storage_components` `Service Network`: `official_surface_slot` urls=3 evidence=1
- `300750.SZ` `battery_energy_storage_components` `Solution`: `official_surface_slot` urls=3 evidence=1
- `3231.TW` `electronics_manufacturing_services` `Electronics Manufacturing / ODM`: `official_surface_slot` urls=3 evidence=1
- `373220.KS` `battery_energy_storage_components` `General Energy / Industrials`: `official_surface_slot` urls=2 evidence=4
- `373220.KS` `battery_energy_storage_components` `LG에너지솔루션｜글로벌 배터리 리더, 미래 에너지 생태계 구축`: `official_surface_slot` urls=2 evidence=2
- `6146.T` `semicap_equipment` `Semicap Equipment`: `official_surface_slot` urls=5 evidence=5
- `6723.T` `analog_embedded_semiconductors` `2線式バスバッファ`: `official_surface_slot` urls=6 evidence=1
- `6723.T` `analog_embedded_semiconductors` `3相MOSFETドライバ、3相FETドライバ`: `official_surface_slot` urls=6 evidence=1
- `6723.T` `analog_embedded_semiconductors` `700V GaN System in Packageデジタルフライバックレギュレータ製品群は、最大100Wの電力供給とゼロスタンバイパワーをサポートします`: `official_surface_slot` urls=6 evidence=1
- `6723.T` `analog_embedded_semiconductors` `A/Dコンバータ（ADC） - ハイスピード`: `official_surface_slot` urls=6 evidence=2
- `6723.T` `analog_embedded_semiconductors` `AC/DCおよび絶縁型DC/DCコンバータ`: `official_surface_slot` urls=6 evidence=1
- `6723.T` `analog_embedded_semiconductors` `AIと現実世界をつなぐ架け橋`: `official_surface_slot` urls=6 evidence=2
- `6723.T` `analog_embedded_semiconductors` `AS-Interface製品`: `official_surface_slot` urls=6 evidence=1
- `6723.T` `analog_embedded_semiconductors` `ASIC & IP`: `official_surface_slot` urls=6 evidence=1
- `6723.T` `analog_embedded_semiconductors` `Analog / Embedded / Connectivity Semiconductors`: `official_surface_slot` urls=6 evidence=2
- `6723.T` `analog_embedded_semiconductors` `AnalogPAK`: `official_surface_slot` urls=6 evidence=1
- `6723.T` `analog_embedded_semiconductors` `Bluetooth Low Energy`: `official_surface_slot` urls=6 evidence=1
- `6723.T` `analog_embedded_semiconductors` `D/Aコンバータ（DAC）`: `official_surface_slot` urls=6 evidence=1
- `6723.T` `analog_embedded_semiconductors` `DC/DC パワーモジュール`: `official_surface_slot` urls=6 evidence=2
- `6723.T` `analog_embedded_semiconductors` `DDR4ソリューション`: `official_surface_slot` urls=6 evidence=1
- `6723.T` `analog_embedded_semiconductors` `DDR5ソリューション`: `official_surface_slot` urls=6 evidence=1
- `6723.T` `analog_embedded_semiconductors` `DECT`: `official_surface_slot` urls=6 evidence=1
- `6723.T` `analog_embedded_semiconductors` `EEPROM & PROM`: `official_surface_slot` urls=6 evidence=1
- `6723.T` `analog_embedded_semiconductors` `EHB（内蔵ホストブリッジ）`: `official_surface_slot` urls=6 evidence=1
- `6723.T` `analog_embedded_semiconductors` `FETドライバ`: `official_surface_slot` urls=6 evidence=1
- `6723.T` `analog_embedded_semiconductors` `FIFO製品`: `official_surface_slot` urls=6 evidence=1
- `6723.T` `analog_embedded_semiconductors` `ForgeFPGA低密度FPGA`: `official_surface_slot` urls=6 evidence=1

## Boundary

Product graph is provenance-backed. Competitive/supply-chain edges are retrieval and analyst-context edges unless an official/source-specific parser promotes them; no market share, sales, ASP, or undisclosed KPI authority is inferred.
