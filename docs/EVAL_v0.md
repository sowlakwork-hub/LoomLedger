# LoomLedger — Week 3 Evaluation (EVAL_v0)

## 1. Evaluation Overview

**Company:** KPR Mill Limited  
**Annual Report:** FY 2024–25  
**Evaluation type:** Document question answering and citation evaluation  
**Endpoint:** `POST /ask`  
**Evaluation questions:** 10

### Evaluation objectives

- Check whether the API retrieves relevant information from the annual report.
- Check factual accuracy of generated answers.
- Verify document and page citations.
- Identify unsupported claims and missing information.
- Evaluate whether the system can answer questions requiring information from multiple report pages.

---

## 2. Evaluation Questions

| ID | Evaluation question | Expected information | Relevant report pages |
|---|---|---|---|
| Q1 | What are KPR Mill's main business sectors? | Textiles, sugar, ethanol, automobiles, renewable power generation and education | 3 |
| Q2 | What textile products does KPR Mill manufacture? | Readymade knitted apparel, fabrics, cotton yarn varieties, melange yarns, viscose yarns and organic cotton products | 3 |
| Q3 | What are KPR Mill's textile manufacturing capacities? | Cotton yarn, viscose vortex yarn, fabrics, knitted apparel, fabric processing and printing capacities | 3 |
| Q4 | What are KPR Mill's installed sugar and ethanol capacities? | Sugar: 20,000 TCD; ethanol: 360 KLPD | 3 |
| Q5 | What is KPR Mill's renewable power generation capacity, including wind, solar and co-generation? | Renewable energy capacities and supporting details for wind, solar and co-generation | 3, 22, 82 |
| Q6 | What are KPR Mill's modernization and expansion priorities? | Spinning modernization, vortex spinning, garment expansion, solar power and market opportunities | 11, 48 |
| Q7 | What is KPR Mill's main CSR focus area? | Promotion of Education | 20 |
| Q8 | What energy conservation measures has KPR Mill implemented? | Energy-efficient fans and motors, VFDs, automation, solar power and power monitoring | 22, 82 |
| Q9 | What are the major opportunities and challenges for KPR Mill in the textile industry? | Global market trends, trade, government support, raw material costs, power costs, labor and competition | 47–50 |
| Q10 | What are the major risks faced by KPR Mill and how does it manage them? | Market, raw material, technology, logistics, disaster, financial and foreign exchange risks, including mitigation measures | 49, 137, 197 |

---

## 3. Scoring Rubric

Each question is evaluated out of 10 marks.

| Criterion | Maximum marks | Evaluation |
|---|---:|---|
| Relevance | 2 | Does the answer address the question? |
| Factual accuracy | 3 | Are the facts and numerical values correct? |
| Citation correctness | 3 | Do the cited document pages support the answer? |
| Groundedness | 2 | Is the answer supported by the annual report without unsupported claims? |
| **Total** | **10** | |

---

## 4. Evaluation Results

| Question | Score | Result |
|---|---:|---|
| Q1 – Business sectors | 10/10 | Passed |
| Q2 – Textile products | 10/10 | Passed |
| Q3 – Manufacturing capacities | 9/10 | Provisional |
| Q4 – Sugar and ethanol capacity | 6/10 | Needs improvement |
| Q5 – Renewable power | 7/10 | Incomplete |
| Q6 – Modernization and expansion | 9/10 | Passed with citation issue |
| Q7 – CSR focus | 10/10 | Passed |
| Q8 – Energy conservation | 10/10 | Passed |
| Q9 – Opportunities and challenges | 10/10 | Passed |
| Q10 – Company risks | 10/10 | Passed |
| **Total** | **91/100** | **91%** |

**Note:** Q3 remains provisional because one printing-capacity figure needs further verification. Q5 received credit for the wind and solar figures verified against pages 82 and 22, but the answer omitted co-generation capacity.

---

## 5. Detailed Evaluation Observations

### Q1 – Business sectors: 10/10

- Correctly identified textiles, sugar, ethanol, automobiles, renewable power generation and education.
- Citation to page 3 was relevant.
- No significant factual issues.

### Q2 – Textile products: 10/10

- Correctly identified readymade knitted apparel, fabrics, cotton yarn varieties, melange yarns, viscose vortex yarns and organic cotton products.
- Citation to page 3 was relevant.
- Answer included useful product-level detail.

### Q3 – Manufacturing capacities: 9/10 (provisional)

- Correctly retrieved the major manufacturing capacities.
- Cited page 3.
- The High Fashion Garments Placement Printing capacity of 1,00,000 per day requires further verification.
- Keep the score provisional until that figure is checked.

### Q4 – Sugar and ethanol capacity: 6/10

- Sugar manufacturing capacity of 20,000 TCD was correct.
- Ethanol capacity was returned as 00 KLPD.
- The expected report value is 360 KLPD.
- The answer incorrectly described the source as containing a typographical error.

**Issue identified:** Numerical extraction and interpretation need improvement.

### Q5 – Renewable power: 7/10

- Wind capacity of 61.92 MW was verified against page 82.
- Solar capacity of 33.49 MW was verified against page 22.
- Co-generation capacity was not provided.
- The answer used relevant citations for the figures it included.

**Issue identified:** The answer was incomplete because it did not address all three requested power sources.

### Q6 – Modernization and expansion: 9/10

- Correctly identified spinning modernization, vortex spinning mill, garment capacity expansion, solar power and market monitoring.
- Inline references included pages 11 and 48.
- The structured citation array included page 11 but omitted page 48.

**Issue identified:** Structured citations should include all relevant pages referenced in the answer.

### Q7 – CSR focus: 10/10

- Correctly identified Promotion of Education.
- Explained the focus on quality education and literacy.
- Correct citation to page 20.

### Q8 – Energy conservation: 10/10

- Correctly identified energy-efficient fans and motors.
- Included IE3–IE5 motors, variable frequency drives and automation.
- Included solar power and power monitoring measures.
- Cited pages 22 and 82 appropriately.

### Q9 – Opportunities and challenges: 10/10

- Covered global sourcing shifts and trade tensions.
- Identified government support and industry growth opportunities.
- Covered raw material and energy costs, labor shortages, international competition and cotton production challenges.
- Relevant citations included pages 47, 48, 49 and 50.

### Q10 – Company risks: 10/10

- Covered market, raw material, technology, logistics, disaster, financial and foreign exchange risks.
- Included relevant mitigation strategies.
- Correctly identified forward contracts as a foreign exchange risk management measure.
- Relevant citations included pages 49, 137 and 197.

---

## 6. Initial Test Observations

### Strengths

1. The end-to-end document question-answering pipeline works.
2. The API retrieves relevant annual report information.
3. Answers include document and page citations.
4. The system can answer questions requiring information from multiple report pages.
5. The API returns structured citation data.

### Issues identified

1. **Numerical accuracy:** Incorrect ethanol capacity in Q4.
2. **Incomplete answers:** Co-generation capacity omitted in Q5.
3. **Citation completeness:** Q6 omitted page 48 from its structured citations array.
4. **Unverified capacity:** One Q3 printing-capacity figure requires further checking.
5. **Citation grounding:** Citation filtering confirms that a cited page belongs to the retrieved chunks, but does not independently prove that the page supports every factual claim.
6. **Retrieval quality:** Relevant information can exist on multiple pages, and the system should retrieve the most useful supporting sections.

---

## 7. Evaluation Conclusion

The initial evaluation achieved **91/100 (91%)** across 10 questions.

The system successfully demonstrates document-based question answering with structured citations. However, the evaluation identified areas requiring improvement, particularly numerical accuracy, answer completeness and citation completeness.

The evaluation score is an initial benchmark, not proof of complete factual reliability.

**Status:** Initial Week 3 evaluation completed.  
**Next focus:** Improve retrieval relevance, numerical accuracy and citation grounding before final Week 3 completion.
