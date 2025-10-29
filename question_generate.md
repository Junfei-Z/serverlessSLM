# 🎯 Prompt Generation Specification

## Objective
For each task entry in `question.jsonl`, generate **five hierarchical prompt versions**:
**L0, L1, L2, L3, and P**, representing progressively longer and richer instructions.

The output should be saved in an **Excel workbook** (`.xlsx`) with **two sheets**:

1. **Sheet 1 – Prompts**  
   Each row corresponds to one task (from `question.jsonl`).  
   Columns:  
   `question_id | category | topic | L0 | L1 | L2 | L3 | P`

2. **Sheet 2 – Token Counts**  
   Each row contains the same task identifiers but with estimated token lengths for every level.  
   Columns:  
   `question_id | category | L0_tokens | L1_tokens | L2_tokens | L3_tokens | P_tokens`

---

## 🧩 Level Definitions

### **L0 – Base Prompt**
- The original task instruction from the dataset (`question.jsonl`).
- No additional structure or constraints.  
  Example:  
  > “Write an essay about the importance of reading literature.”

---

### **L1 – Clarified Prompt**
- Builds on **L0** by **adding clarity, scoring dimensions, or basic constraints**.  
- Adds 50–150 extra tokens.  
- Should emphasize structure and evaluation criteria but remain concise.  
  Example Additions:  
  - “Include introduction, body, and conclusion.”  
  - “Ensure emotional consistency and realistic tone.”  
  - “Address at least two contrasting perspectives.”

---

### **L2 – Guided Prompt**
- Builds on **L1** by introducing **explicit step-by-step or phase-based execution instructions**.  
- Adds another 100–200 tokens.  
- Should define an ordered procedure or framework (e.g., “Step 1 → Step 2 → Step 3”).  
  Example Additions:  
  - “Follow these steps: (1) Define the problem (2) Provide evidence (3) Summarize conclusions.”  
  - “Structure the dialogue with greeting → core discussion → resolution.”

---

### **L3 – Few-Shot / Example-Guided Prompt**
- Builds on **L2** by adding **examples, stylistic expectations, or few-shot patterns**.  
- Adds another 150–250 tokens.  
- May include a short illustrative snippet (“Example: …”) or explicit stylistic guidance.  
  Example Additions:  
  - “Example: Teacher uses analogy; student responds with curiosity.”  
  - “Follow this model of coherent argumentation and tone consistency.”

---

### **P – Placebo Prompt**
- Builds directly on **L3**, **without adding real informational content**,  
  only **redundant, polite, or overly detailed phrasing**.  
- Adds 100–200 tokens of uninformative language such as:  
  > “Please do your absolute best, be extremely comprehensive, detailed, and considerate.  
  > Ensure that every possible aspect is covered with care and patience.”  
- Purpose: To test whether longer inputs bias performance.

---

## ⚙️ Output Requirements

- For each `question` in `question.jsonl`:
  - Generate all five levels (L0–P).
  - Record them as one row in **Sheet 1**.
  - Compute token lengths using an approximate tokenizer (`tiktoken` or len ÷ 4 heuristic) and store in **Sheet 2**.
- Ensure **monotonic token increase** per row: L0 < L1 < L2 < L3 < P.
- Encode using UTF-8; newline breaks (`\n`) are preserved inside cells.

---

## ✅ Example Row (Condensed)

| question_id | category | topic | L0 | L1 | L2 | L3 | P |
|--------------|-----------|-------|----|----|----|----|---|
| 001 | Writing | Importance of Literature | “Write an essay…” | “Write an essay… Include intro/body/conclusion.” | “Write an essay… Follow these steps: …” | “Write an essay… Example: …” | “Write an essay… Example: … Please do your absolute best…” |

---

## 🔍 Notes
- Each new level must **reuse the full previous text** and then append or expand meaningfully (except P which appends fluff).
- This schema applies to all task categories (Writing, Roleplay, Math, Reasoning, etc.).
- Keep Markdown/Excel ready for direct parsing by scripts.

---

**Deliverable Example:**  
`generated_prompts.xlsx`  
- Sheet 1 → prompts for all questions.  
- Sheet 2 → token statistics.

