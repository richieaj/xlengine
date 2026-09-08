Now I'll compile the full comparison. I have all 78 flow rows from Excel with full precision values. Here is the complete parity report:

---

# Full Flow Sheet Parity Report — Excel vs Compiler

> **Source:** `Flows` sheet, read after full workbook recalculation.
> **Precision:** Excel values shown at full precision. Compiler values as provided (2 d.p.). Difference = Excel raw − Compiler (2 d.p.).

---

## Row-by-Row Results

---

**Coal Production → Coal**
✓ Base ✓ 2022 ✓ 2027 ✓ 2032 ✓ 2037 ✓ 2042 ✓ 2047 ✓ Target

---

**Coal Imports → Coal** ⚠️

| Year     | Excel (raw)        | Compiler   | Difference |
| -------- | ------------------ | ---------- | ---------- |
| Base     | 120.186257334624   | 120.30     | −0.113743  |
| 2022     | 131.176900849218   | 131.29     | −0.113099  |
| 2027     | 150.127945754148   | 150.23     | −0.102054  |
| 2032     | 157.867568917288   | 157.94     | −0.072431  |
| 2037     | 192.163472128851   | 192.21     | −0.046528  |
| 2042     | 236.82457872521    | 236.85     | −0.025421  |
| **2047** | **202.4592578974** | **202.46** | **≈ 0 ✓**  |
| Target   | 166.660714817652   | 166.75     | −0.089285  |

---

**Oil Production → Oil**
✓ Base ✓ 2022 ✓ 2027 ✓ 2032 ✓ 2037 ✓ 2042 ✓ 2047 ✓ Target

---

**Oil Imports → Oil**
✓ Base ✓ 2022 ✓ 2027 ✓ 2032 ✓ 2037 ✓ 2042 ✓ 2047 ✓ Target

---

**Gas Production → Natural Gas**
✓ Base ✓ 2022 ✓ 2027 ✓ 2032 ✓ 2037 ✓ 2042 ✓ 2047 ✓ Target

---

**Gas Imports → Natural Gas**
✓ Base ✓ 2022 ✓ 2027 ✓ 2032 ✓ 2037 ✓ 2042 ✓ 2047 ✓ Target

---

**Municipal Waste → Solid**
✓ Base ✓ 2022 ✓ 2027 ✓ 2032 ✓ 2037 ✓ 2042 ✓ 2047 ✓ Target *(all values < 1e-5, both round to 0.00)*

---

**Municipal Waste → Gas**
✓ Base ✓ 2022 ✓ 2027 ✓ 2032 ✓ 2037 ✓ 2042 ✓ 2047 ✓ Target *(all < 5e-7, both 0.00)*

---

**Municipal Waste → Thermal Generation**
✓ Base ✓ 2022 ✓ 2027 ✓ 2032 ✓ 2037 ✓ 2042 ✓ 2047 ✓ Target

---

**Solar → Solar PV**
✓ Base ✓ 2022 ✓ 2027 ✓ 2032 ✓ 2037 ✓ 2042 ✓ 2047 ✓ Target

---

**Solar PV → Electricity Grid**
✓ Base ✓ 2022 ✓ 2027 ✓ 2032 ✓ 2037 ✓ 2042 ✓ 2047 ✓ Target

---

**Solar → Solar CSP** ⚠️

| Year   | Excel (raw)        | Compiler | Difference |
| ------ | ------------------ | -------- | ---------- |
| Base   | 0.0396995030094583 | 0.00     | +0.039700  |
| 2022   | 0.092747747205503  | 0.05     | +0.042748  |
| 2027   | 0.290219193844197  | 0.25     | +0.040219  |
| 2032   | 0.578252526947247  | 0.54     | +0.038253  |
| 2037   | 0.94586415937209   | 0.91     | +0.035864  |
| 2042   | 1.41504010799644   | 1.38     | +0.035040  |
| 2047   | 2.01384072079416   | 1.97     | +0.043841  |
| Target | 0.446972028185993  | 0.41     | +0.036972  |

---

**Solar CSP → Electricity Grid** ⚠️
*(Identical values to Solar → Solar CSP row above — same mismatches apply)*

| Year   | Excel (raw)        | Compiler | Difference |
| ------ | ------------------ | -------- | ---------- |
| Base   | 0.0396995030094583 | 0.00     | +0.039700  |
| 2022   | 0.092747747205503  | 0.05     | +0.042748  |
| 2027   | 0.290219193844197  | 0.25     | +0.040219  |
| 2032   | 0.578252526947247  | 0.54     | +0.038253  |
| 2037   | 0.94586415937209   | 0.91     | +0.035864  |
| 2042   | 1.41504010799644   | 1.38     | +0.035040  |
| 2047   | 2.01384072079416   | 1.97     | +0.043841  |
| Target | 0.446972028185993  | 0.41     | +0.036972  |

---

**Solar → Distributed Solar PV**
✓ Base ✓ 2022 ✓ 2027 ✓ 2032 ✓ 2037 ✓ 2042 ✓ 2047 ✓ Target

---

**Distributed Solar PV → Electricity Grid**
✓ Base ✓ 2022 ✓ 2027 ✓ 2032 ✓ 2037 ✓ 2042 ✓ 2047 ✓ Target

---

**Distributed Solar PV → Off Grid Renewables**
✓ Base ✓ 2022 ✓ 2027 ✓ 2032 ✓ 2037 ✓ 2042 ✓ 2047 ✓ Target

---

**Wind → Onshore Wind**
✓ Base ✓ 2022 ✓ 2027 ✓ 2032 ✓ 2037 ✓ 2042 ✓ 2047 ✓ Target

---

**Wind → Offshore Wind**
✓ Base ✓ 2022 ✓ 2027 ✓ 2032 ✓ 2037 ✓ 2042 ✓ 2047 ✓ Target

---

**Onshore Wind → Electricity Grid**
✓ Base ✓ 2022 ✓ 2027 ✓ 2032 ✓ 2037 ✓ 2042 ✓ 2047 ✓ Target

---

**Onshore Wind → Off Grid Renewables**
✓ Base ✓ 2022 ✓ 2027 ✓ 2032 ✓ 2037 ✓ 2042 ✓ 2047 ✓ Target

---

**Offshore Wind → Electricity Grid**
✓ Base ✓ 2022 ✓ 2027 ✓ 2032 ✓ 2037 ✓ 2042 ✓ 2047 ✓ Target

---

**Small Hydro → Electricity Grid**
✓ Base ✓ 2022 ✓ 2027 ✓ 2032 ✓ 2037 ✓ 2042 ✓ 2047 ✓ Target

---

**Hydro → Electricity Grid**
✓ Base ✓ 2022 ✓ 2027 ✓ 2032 ✓ 2037 ✓ 2042 ✓ 2047 ✓ Target

---

**Nuclear → Thermal Generation**
✓ Base ✓ 2022 ✓ 2027 ✓ 2032 ✓ 2037 ✓ 2042 ✓ 2047 ✓ Target

---

**Electricity Imports → Electricity Grid**
✓ Base ✓ 2022 ✓ 2027 ✓ 2032 ✓ 2037 ✓ 2042 ✓ 2047 ✓ Target

---

**Agricultural Waste/Energy Crops → Solid**
✓ Base ✓ 2022 ✓ 2027 ✓ 2032 ✓ 2037 ✓ 2042 ✓ 2047 ✓ Target

---

**Agricultural Waste/Energy Crops → Liquid**
✓ Base ✓ 2022 ✓ 2027 ✓ 2032 ✓ 2037 ✓ 2042 ✓ 2047 ✓ Target

---

**Agricultural Waste/Energy Crops → Gas**
✓ Base ✓ 2022 ✓ 2027 ✓ 2032 ✓ 2037 ✓ 2042 ✓ 2047 ✓ Target

---

**Agricultural Waste/Energy Crops → Thermal Generation**
✓ Base ✓ 2022 ✓ 2027 ✓ 2032 ✓ 2037 ✓ 2042 ✓ 2047 ✓ Target

---

**Gas → Thermal Generation**
✓ Base ✓ 2022 ✓ 2027 ✓ 2032 ✓ 2037 ✓ 2042 ✓ 2047 ✓ Target

---

**Solid → Thermal Generation** ⚠️

| Year     | Excel (raw)          | Compiler   | Difference |
| -------- | -------------------- | ---------- | ---------- |
| Base     | 245.862612478015     | 245.98     | −0.117387  |
| 2022     | 256.555249970138     | 256.67     | −0.114750  |
| 2027     | 272.447139355046     | 272.55     | −0.102861  |
| 2032     | 272.746021249923     | 272.82     | −0.073979  |
| 2037     | 293.804241744078     | 293.86     | −0.055758  |
| 2042     | 317.61081039362      | 317.64     | −0.029190  |
| **2047** | **287.229032870742** | **287.23** | **≈ 0 ✓**  |
| Target   | 285.127298019904     | 285.21     | −0.082702  |

---

**Thermal Generation → Electricity Grid** ⚠️

| Year   | Excel (raw)      | Compiler | Difference |
| ------ | ---------------- | -------- | ---------- |
| Base   | 88.3068941688674 | 88.35    | −0.043106  |
| 2022   | 92.7069564301838 | 92.75    | −0.043044  |
| 2027   | 110.201873150205 | 110.24   | −0.038127  |
| 2032   | 125.796201716802 | 125.84   | −0.043798  |
| 2037   | 156.913101691053 | 156.95   | −0.036898  |
| 2042   | 193.162448844822 | 193.20   | −0.037551  |
| 2047   | 226.977293257504 | 227.02   | −0.042707  |
| Target | 115.298477790366 | 115.34   | −0.041522  |

---

**Thermal Generation → Losses** ⚠️

| Year   | Excel (raw)      | Compiler | Difference |
| ------ | ---------------- | -------- | ---------- |
| Base   | 185.455541316387 | 185.53   | −0.074459  |
| 2022   | 192.497974151689 | 192.58   | −0.082026  |
| 2027   | 213.481040569403 | 213.54   | −0.058959  |
| 2032   | 223.369166052447 | 223.40   | −0.030834  |
| 2037   | 252.541879716511 | 252.55   | −0.008120  |
| 2042   | 301.784305674103 | 301.77   | +0.014306  |
| 2047   | 335.30137804022  | 335.26   | +0.041378  |
| Target | 217.126702962916 | 217.17   | −0.043297  |

---

**Electricity Grid → T&D Losses**
✓ Base ✓ 2022 ✓ 2027 ✓ 2032 ✓ 2037 ✓ 2042 ✓ 2047 ✓ Target

---

**Electricity Grid → Passenger Transport**
✓ Base ✓ 2022 ✓ 2027 ✓ 2032 ✓ 2037 ✓ 2042 ✓ 2047 ✓ Target

---

**Electricity Grid → Freight Transport**
✓ Base ✓ 2022 ✓ 2027 ✓ 2032 ✓ 2037 ✓ 2042 ✓ 2047 ✓ Target

---

**Electricity Grid → Industry**
✓ Base ✓ 2022 ✓ 2027 ✓ 2032 ✓ 2037 ✓ 2042 ✓ 2047 ✓ Target

---

**Electricity Grid → Cooking**
✓ Base ✓ 2022 ✓ 2027 ✓ 2032 ✓ 2037 ✓ 2042 ✓ 2047 ✓ Target

---

**Electricity Grid → Residential Buildings**
✓ Base ✓ 2022 ✓ 2027 ✓ 2032 ✓ 2037 ✓ 2042 ✓ 2047 ✓ Target

---

**Electricity Grid → Commercial Buildings**
✓ Base ✓ 2022 ✓ 2027 ✓ 2032 ✓ 2037 ✓ 2042 ✓ 2047 ✓ Target

---

**Electricity Grid → Agriculture**
✓ Base ✓ 2022 ✓ 2027 ✓ 2032 ✓ 2037 ✓ 2042 ✓ 2047 ✓ Target

---

**Electricity Grid → Telecom**
✓ Base ✓ 2022 ✓ 2027 ✓ 2032 ✓ 2037 ✓ 2042 ✓ 2047 ✓ Target

---

**Electricity Grid → Miscellaneous**
✓ Base ✓ 2022 ✓ 2027 ✓ 2032 ✓ 2037 ✓ 2042 ✓ 2047 ✓ Target

---

**Electricity Grid → Over Generation/Exports**
✓ Base ✓ 2022 ✓ 2027 ✓ 2032 ✓ 2037 ✓ 2042 ✓ 2047 ✓ Target *(Excel 2047 = 5.68e-14, rounds to 0.00)*

---

**Electricity Grid → Green Hydrogen**
✓ Base ✓ 2022 ✓ 2027 ✓ 2032 ✓ 2037 ✓ 2042 ✓ 2047 ✓ Target

---

**Liquid → Passenger Transport**
✓ Base ✓ 2022 ✓ 2027 ✓ 2032 ✓ 2037 ✓ 2042 ✓ 2047 ✓ Target

---

**Liquid → Freight Transport**
✓ Base ✓ 2022 ✓ 2027 ✓ 2032 ✓ 2037 ✓ 2042 ✓ 2047 ✓ Target

---

**Liquid → Industry**
✓ Base ✓ 2022 ✓ 2027 ✓ 2032 ✓ 2037 ✓ 2042 ✓ 2047 ✓ Target

---

**Liquid → Cooking**
✓ Base ✓ 2022 ✓ 2027 ✓ 2032 ✓ 2037 ✓ 2042 ✓ 2047 ✓ Target

---

**Liquid → Agriculture**
✓ Base ✓ 2022 ✓ 2027 ✓ 2032 ✓ 2037 ✓ 2042 ✓ 2047 ✓ Target

---

**Liquid → Telecom**
✓ Base ✓ 2022 ✓ 2027 ✓ 2032 ✓ 2037 ✓ 2042 ✓ 2047 ✓ Target

---

**Liquid → Non-energy use**
✓ Base ✓ 2022 ✓ 2027 ✓ 2032 ✓ 2037 ✓ 2042 ✓ 2047 ✓ Target

---

**Liquid → Over Generation/Exports**
✓ Base ✓ 2022 ✓ 2027 ✓ 2032 ✓ 2037 ✓ 2042 ✓ 2047 ✓ Target

---

**Gas → Passenger Transport**
✓ Base ✓ 2022 ✓ 2027 ✓ 2032 ✓ 2037 ✓ 2042 ✓ 2047 ✓ Target

---

**Gas → Freight Transport**
✓ Base ✓ 2022 ✓ 2027 ✓ 2032 ✓ 2037 ✓ 2042 ✓ 2047 ✓ Target

---

**Gas → Industry**
✓ Base ✓ 2022 ✓ 2027 ✓ 2032 ✓ 2037 ✓ 2042 ✓ 2047 ✓ Target

---

**Gas → Cooking**
✓ Base ✓ 2022 ✓ 2027 ✓ 2032 ✓ 2037 ✓ 2042 ✓ 2047 ✓ Target

---

**Gas → Non-energy use**
✓ Base ✓ 2022 ✓ 2027 ✓ 2032 ✓ 2037 ✓ 2042 ✓ 2047 ✓ Target

---

**Gas → Over Generation/Exports**
✓ Base ✓ 2022 ✓ 2027 ✓ 2032 ✓ 2037 ✓ 2042 ✓ 2047 ✓ Target

---

**Solid → Industry**
✓ Base ✓ 2022 ✓ 2027 ✓ 2032 ✓ 2037 ✓ 2042 ✓ 2047 ✓ Target

---

**Solid → Over Generation/Exports**
✓ Base ✓ 2022 ✓ 2027 ✓ 2032 ✓ 2037 ✓ 2042 ✓ 2047 ✓ Target

---

**Solid → Cooking**
✓ Base ✓ 2022 ✓ 2027 ✓ 2032 ✓ 2037 ✓ 2042 ✓ 2047 ✓ Target

---

**Coal → Solid** ⚠️

| Year     | Excel (raw)          | Compiler   | Difference |
| -------- | -------------------- | ---------- | ---------- |
| Base     | 407.693717510797     | 407.81     | −0.116282  |
| 2022     | 430.084316118909     | 430.20     | −0.115684  |
| 2027     | 479.571584155831     | 479.67     | −0.098416  |
| 2032     | 520.996369972138     | 521.07     | −0.073630  |
| 2037     | 592.452625167654     | 592.50     | −0.047375  |
| 2042     | 678.109403003974     | 678.14     | −0.030597  |
| **2047** | **688.972605094299** | **688.97** | **≈ 0 ✓**  |
| Target   | 515.917421218849     | 516.00     | −0.082579  |

---

**Oil → Liquid**
✓ Base ✓ 2022 ✓ 2027 ✓ 2032 ✓ 2037 ✓ 2042 ✓ 2047 ✓ Target

---

**Natural Gas → Gas**
✓ Base ✓ 2022 ✓ 2027 ✓ 2032 ✓ 2037 ✓ 2042 ✓ 2047 ✓ Target

---

**Gas → Losses**
✓ Base ✓ 2022 ✓ 2027 ✓ 2032 ✓ 2037 ✓ 2042 ✓ 2047 ✓ Target

---

**Liquid → Losses**
✓ Base ✓ 2022 ✓ 2027 ✓ 2032 ✓ 2037 ✓ 2042 ✓ 2047 ✓ Target

---

**Solid → Losses**
✓ Base ✓ 2022 ✓ 2027 ✓ 2032 ✓ 2037 ✓ 2042 ✓ 2047 ✓ Target

---

**Green Hydrogen → Losses**
✓ Base ✓ 2022 ✓ 2027 ✓ 2032 ✓ 2037 ✓ 2042 ✓ 2047 ✓ Target *(Compiler −0.00 = negative zero, matches Excel 0.00)*

---

**Green Hydrogen → Passenger Transport**
✓ Base ✓ 2022 ✓ 2027 ✓ 2032 ✓ 2037 ✓ 2042 ✓ 2047 ✓ Target

---

**Green Hydrogen → Freight Transport**
✓ Base ✓ 2022 ✓ 2027 ✓ 2032 ✓ 2037 ✓ 2042 ✓ 2047 ✓ Target

---

**Green Hydrogen → Telecom**
✓ Base ✓ 2022 ✓ 2027 ✓ 2032 ✓ 2037 ✓ 2042 ✓ 2047 ✓ Target

---

**Green Hydrogen → Refineries**
✓ Base ✓ 2022 ✓ 2027 ✓ 2032 ✓ 2037 ✓ 2042 ✓ 2047 ✓ Target *(Compiler −0.00 = negative zero, matches Excel 0.00)*

---

**Green Hydrogen → Industry**
✓ Base ✓ 2022 ✓ 2027 ✓ 2032 ✓ 2037 ✓ 2042 ✓ 2047 ✓ Target

---

**Off Grid Renewables → Agriculture**
✓ Base ✓ 2022 ✓ 2027 ✓ 2032 ✓ 2037 ✓ 2042 ✓ 2047 ✓ Target

---

**Off Grid Renewables → Telecom**
✓ Base ✓ 2022 ✓ 2027 ✓ 2032 ✓ 2037 ✓ 2042 ✓ 2047 ✓ Target

---

**Off Grid Renewables → Green Hydrogen**
✓ Base ✓ 2022 ✓ 2027 ✓ 2032 ✓ 2037 ✓ 2042 ✓ 2047 ✓ Target

---

**Agricultural Waste/Energy Crops → Industry**
✓ Base ✓ 2022 ✓ 2027 ✓ 2032 ✓ 2037 ✓ 2042 ✓ 2047 ✓ Target

---

## Final Summary

| Metric                      | Value              |
| --------------------------- | ------------------ |
| **Total Flow Rows**         | 78                 |
| **Total Data Points**       | 624 (78 × 8 years) |
| **Matching Data Points**    | 571                |
| **Mismatching Data Points** | 53                 |
| **Overall Match %**         | **91.5%**          |

| Category                  | Count |
| ------------------------- | ----- |
| **Rows with 100% Match**  | 71    |
| **Rows with Differences** | 7     |

---

## Rows with Differences — Isolated List

| Row                                   | Mismatching Years                                  | Pattern                                       |
| ------------------------------------- | -------------------------------------------------- | --------------------------------------------- |
| Coal Imports → Coal                   | Base, 2022, 2027, 2032, 2037, 2042, Target *(7/8)* | Compiler > Excel, converges to 0 by 2047      |
| Solar → Solar CSP                     | All 8 years                                        | Compiler < Excel by ~0.036–0.044              |
| Solar CSP → Electricity Grid          | All 8 years                                        | Identical to above (same source)              |
| Coal → Solid                          | Base, 2022, 2027, 2032, 2037, 2042, Target *(7/8)* | Same magnitude as Coal Imports gap            |
| Solid → Thermal Generation            | Base, 2022, 2027, 2032, 2037, 2042, Target *(7/8)* | Same magnitude — cascades from Coal           |
| Thermal Generation → Electricity Grid | All 8 years                                        | Compiler > Excel by ~0.037–0.044 consistently |
| Thermal Generation → Losses           | All 8 years                                        | Mixed sign — reverses direction after 2042    |

---

**Verification status: NOT fully successful.** 7 of 78 flow rows contain discrepancies across 53 of 624 data points. Two independent divergence sources are present: (1) **Coal Imports** is overstated in the compiler relative to Excel, propagating through Coal → Solid → Thermal Generation; and (2) **Solar CSP** is understated in the compiler relative to Excel across all years.
