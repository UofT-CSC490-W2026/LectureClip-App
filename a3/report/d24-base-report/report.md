# nanochat training report

Generated: 2026-03-06 05:25:05

## Environment

### Git Information
- Branch: master
- Commit: 83dccc2 (dirty)
- Message: Restore completion-only loss masking in SFT dataloader (#582)

### Hardware
- Platform: Linux
- CPUs: 64 cores (64 logical)
- Memory: 1024.0 GB
- GPUs: 8x NVIDIA H100 80GB HBM3
- GPU Memory: 633.4 GB total
- CUDA Version: 12.8
- Hourly Rate: $24.00/hour

### Software
- Python: 3.10.20
- PyTorch: 2.9.1+cu128


### Bloat
- Characters: 514,782
- Lines: 11,442
- Files: 47
- Tokens (approx): 128,695
- Dependencies (uv.lock lines): 3,618

Run started: 2026-03-06 05:25:08

---

## Tokenizer evaluation
timestamp: 2026-03-06 05:24:40

### Comparison with GPT-2

| Text Type | Bytes | GPT-2 Tokens | GPT-2 Ratio | Ours Tokens | Ours Ratio | Relative Diff % |
|-----------|-------|--------------|--------------|-------------|------------|-----------------|
| news | 1819 | 404 | 4.50 | 403 | 4.51 | +0.2% |
| korean | 893 | 745 | 1.20 | 797 | 1.12 | -7.0% |
| code | 1259 | 576 | 2.19 | 620 | 2.03 | -7.6% |
| math | 1834 | 936 | 1.96 | 1025 | 1.79 | -9.5% |
| science | 1112 | 260 | 4.28 | 258 | 4.31 | +0.8% |
| fwe-train | 4208518 | 900364 | 4.67 | 892476 | 4.72 | +0.9% |
| fwe-val | 4768657 | 1027270 | 4.64 | 1023546 | 4.66 | +0.4% |

### Comparison with GPT-4

| Text Type | Bytes | GPT-4 Tokens | GPT-4 Ratio | Ours Tokens | Ours Ratio | Relative Diff % |
|-----------|-------|--------------|--------------|-------------|------------|-----------------|
| news | 1819 | 387 | 4.70 | 403 | 4.51 | -4.1% |
| korean | 893 | 364 | 2.45 | 797 | 1.12 | -119.0% |
| code | 1259 | 309 | 4.07 | 620 | 2.03 | -100.6% |
| math | 1834 | 832 | 2.20 | 1025 | 1.79 | -23.2% |
| science | 1112 | 249 | 4.47 | 258 | 4.31 | -3.6% |
| fwe-train | 4208518 | 874799 | 4.81 | 892476 | 4.72 | -2.0% |
| fwe-val | 4768657 | 1001442 | 4.76 | 1023546 | 4.66 | -2.2% |


## Base model training
timestamp: 2026-03-06 08:14:24

- run: 8h100_d24_base
- device_type: 
- fp8: False
- fp8_recipe: tensorwise
- depth: 24
- aspect_ratio: 64
- head_dim: 128
- max_seq_len: 2048
- window_pattern: SSSL
- num_iterations: -1
- target_flops: -1.0000
- target_param_data_ratio: 10.5000
- device_batch_size: 16
- total_batch_size: -1
- embedding_lr: 0.3000
- unembedding_lr: 0.0040
- weight_decay: 0.2000
- matrix_lr: 0.0200
- scalar_lr: 0.5000
- adam_beta1: 0.8000
- adam_beta2: 0.9500
- warmup_ratio: 0.0000
- warmdown_ratio: 0.5000
- final_lr_frac: 0.0000
- resume_from_step: -1
- eval_every: 250
- eval_tokens: 20,971,520
- core_metric_every: 2000
- core_metric_max_per_task: 500
- sample_every: 2000
- save_every: 1000
- model_tag: None
- Number of parameters: 1,384,124,976
- Number of FLOPs per token: 4.945112e+09
- Calculated number of iterations: 7308
- Number of training tokens: 7,662,993,408
- Tokens : Scaling params ratio: 10.4999
- DDP world size: 8
- warmup_ratio: 0.0000
- warmdown_ratio: 0.5000
- final_lr_frac: 0.0000
- Minimum validation bpb: 0.7532
- Final validation bpb: 0.7532
- CORE metric estimate: 0.2478
- MFU %: 50.53%
- Total training flops: 3.789436e+19
- Total training time: 157.64m
- Peak memory usage: 62386.67MiB


## Base model evaluation
timestamp: 2026-03-06 08:24:46

- model: base_model (step 7308)
- CORE metric: 0.2389
- train bpb: 0.7528
- val bpb: 0.7533
- hellaswag_zeroshot: 0.3487
- jeopardy: 0.1710
- bigbench_qa_wikidata: 0.5104
- arc_easy: 0.5483
- arc_challenge: 0.1524
- copa: 0.3400
- commonsense_qa: 0.0448
- piqa: 0.4287
- openbook_qa: 0.1947
- lambada_openai: 0.4271
- hellaswag: 0.3432
- winograd: 0.3260
- winogrande: 0.1050
- bigbench_dyck_languages: 0.1170
- agi_eval_lsat_ar: 0.0707
- bigbench_cs_algorithms: 0.3864
- bigbench_operators: 0.1619
- bigbench_repeat_copy_logic: 0.0312
- squad: 0.3619
- coqa: 0.2587
- boolq: -0.2498
- bigbench_language_identification: 0.1782
- sample 0: <|bos|>The capital of France is Paris. It is the largest city in France and the 2nd largest city
- sample 1: <|bos|>The chemical symbol of gold is Au. It is a soft, yellow metal that is malleable and duct
- sample 2: <|bos|>If yesterday was Friday, then tomorrow will be Saturday. If tomorrow is Saturday, then tomorrow will be Sunday. If tomorrow is
- sample 3: <|bos|>The opposite of hot is cold. The opposite of cold is hot. The opposite of hot is cold.
- sample 4: <|bos|>The planets of the solar system are: Mercury, Venus, Earth, Mars, Jupiter, Saturn, Uranus, and
- sample 5: <|bos|>My favorite color is blue. I love the color of the sky, the sea, and the sky
- sample 6: <|bos|>If 5*x + 3 = 13, then x is
If 5*x + 3 = 13, then x is
- unconditioned 0: <|bos|>The Summary can be found here (Advanced, our second edition is online), more information about the basics of interpreting by radio and television can be found on our Communication and Doyenge pages here.
Generally speaking, the turn-the-clock/muzzle flash paradigm used on this page is the one commonly used in the UK to interpret a RC crosscheck, as it can be the easiest way to interpret if you have difficulty reading other portions of a scene. Within this general paradigm, however, you are bound to find other solutions that overcome your difficulty. In essence, your distance will dictate the way in which you interpret a scene, as some radio
- unconditioned 1: <|bos|>New York Times, Monday 11 July 2019
Parents fear that mental illness will affect their children
Parents Followbreak Mobile view, Monday 11 July 2019
SYDNEY — Sixteen-year-old Weeramika Chen has just learned of the mental illness of her entire family.
Her father and eight-year-old brother were both diagnosed with bipolar disorder, a lifelong disorder that causes periods of mania and depression. She said she knows her father well. She also knew the family of his Bipolar Girl neighbor.
Her father was treated with three of the mood-stabilizing drugs that are key to the U
- unconditioned 2: <|bos|>Inquiry Based Projects in the STEM Program for Kids
17.11.14 CultureClub VideosPermaculture & Permaculture Science
Description: “Learning’s ever-changing solution”
CultureClub has produced a series of short videos to help new teachers understand the concepts of CultureClub STEAM Science program, STEM program. Societas de Clase Haldoc in Guatemala. From Bacteria to Bird Behavior.
In addition, University of Washington offers Edubious, a resource for teachers. You can share your lectures, comments, notes, classroom activities and problems with other educators in the same discipline – it’s FREE
- unconditioned 3: <|bos|>Civil war over centuries-old sanctuary museum
by Patrick Kirkby
A prolific British writer cautions his editor against flattering the descendants of the enslaved Africans who carved the first African-American inscriptions in bricks and adobe on this front lawn at the Rhode Island State Capitol on Sunday morning.
Mary Murphy LeBaron, a director at the Rhode Island Historical Society and an 1990 graduate of the university, lives in the human history museum-cum-history-education center now in the making in 17th-century black enterprise Germantown.
An emeritus professor and author about the history of blacks in the United States.
LeBaron speaks
- unconditioned 4: <|bos|>Dialysis is an artificial method of filtering your blood if your kidneys fail to function properly. There are different forms of dialysis, but before your dialysis treatment begins, it's important for you to be fully aware of how the process will work. Dialysis is a very artificial process that necessitates detailed food restriction and fluid restrictions during the day. To successfully undergo dialysis, you must deviate from your regular dietary intake.
Protein and Cholesterol Renal Diet Plan
You must discontinue the consumption of meat, poultry and fish, along with hot dogs, hot dogs and deli meats, seafood, fish eggs and dairy products such as
- unconditioned 5: <|bos|>Freedom in the World
Freedom Rating (1 = best, 7 = worst)
Civil Liberties (1 = best, 7 = worst)
Political Rights (1 = best, 7 = worst)
In addition to other concerns, a shrinking youth population and declining working-age population are top priorities for Australia. Its economic base is also under stress. Indigenous Australians have enjoyed improved self-government rights, but non-Indigenous Australians have steadily tightened control over powers that had been previously owned by Indigenous social and business groups and elders.
Australia, whose population was 16.83 million, claimed independence in 1901
- unconditioned 6: <|bos|>SANEUM: Biosystematics of the family Asteraceae
1Department of Systematic Botany and Plant Pathology, and 7Institute of Functional Botany, Universitat Rovi and Aleksandrovich Klinici u Zhove in Vologda, Russia, 2Department of Architecture and Landscape Studies, Institute of Landscape Architecture and Planning, and 3Department of Biodiversity and Ecosystem Science, Institute of Evolutionary Biology, University of São Paulo (USP) in Ribeirão Preto, SP, Portugal.
The family Asteraceae is one of the most ancient families. The
- unconditioned 7: <|bos|>The bladder is located in the lower abdomen which is a part of the reproductive system. It is the part inside the abdomen where the urethra connects to a man’s genitals. The urethra is also the tube in a woman’s bladder that collects urine from the bladder to leave. The bladder serves as a storage that stores urine. It’s said that the best ever author Ts'ai Lun used his kettle to keep his urine. Most of the animals that use urine as a medium of storing urine are marsupials, mammals, reptiles, amphibians and birds.
A man's bladder will vary depending on how long it is, where it


## Chat evaluation sft
timestamp: 2026-03-06 08:52:22

- source: sft
- task_name: None
- dtype: bfloat16
- temperature: 0.0000
- max_new_tokens: 512
- num_samples: 1
- top_k: 50
- batch_size: 8
- model_tag: None
- step: None
- max_problems: None
- device_type: 
- ARC-Easy: 0.6031
- ARC-Challenge: 0.4573
- MMLU: 0.3795
- GSM8K: 0.0978
- HumanEval: 0.1220
- SpellingBee: 0.9961
- ChatCORE metric: 0.3560


## Summary

- Characters: 514,782
- Lines: 11,442
- Files: 47
- Tokens (approx): 128,695
- Dependencies (uv.lock lines): 3,618

| Metric          | BASE     | SFT      | RL       |
|-----------------|----------|----------|----------|
| CORE            | 0.2389   | -        | -        |
| ARC-Challenge   | -        | 0.4573   | -        |
| ARC-Easy        | -        | 0.6031   | -        |
| GSM8K           | -        | 0.0978   | -        |
| HumanEval       | -        | 0.1220   | -        |
| MMLU            | -        | 0.3795   | -        |
| ChatCORE        | -        | 0.3560   | -        |

Total wall clock time: 3h27m
