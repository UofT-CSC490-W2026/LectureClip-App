# nanochat training report

Generated: 2026-03-04 02:02:48

## Environment

### Git Information
- Branch: master
- Commit: 83dccc2 (clean)
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
- Python: 3.10.19
- PyTorch: 2.9.1+cu128


### Bloat
- Characters: 514,782
- Lines: 11,442
- Files: 47
- Tokens (approx): 128,695
- Dependencies (uv.lock lines): 3,618

Run started: 2026-03-04 02:02:51

---

## Tokenizer evaluation
timestamp: 2026-03-04 02:02:19

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
timestamp: 2026-03-04 02:26:21

- run: 8h100_d16_base
- device_type: 
- fp8: False
- fp8_recipe: tensorwise
- depth: 16
- aspect_ratio: 64
- head_dim: 128
- max_seq_len: 2048
- window_pattern: SSSL
- num_iterations: -1
- target_flops: -1.0000
- target_param_data_ratio: 10.5000
- device_batch_size: 32
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
- Number of parameters: 536,872,992
- Number of FLOPs per token: 1.660957e+09
- Calculated number of iterations: 4704
- Number of training tokens: 2,466,250,752
- Tokens : Scaling params ratio: 10.4999
- DDP world size: 8
- warmup_ratio: 0.0000
- warmdown_ratio: 0.5000
- final_lr_frac: 0.0000
- Minimum validation bpb: 0.8359
- Final validation bpb: 0.8359
- CORE metric estimate: 0.1649
- MFU %: 46.71%
- Total training flops: 4.096336e+18
- Total training time: 18.51m
- Peak memory usage: 48352.75MiB


## Base model evaluation
timestamp: 2026-03-04 02:32:54

- model: base_model (step 4704)
- CORE metric: 0.1588
- train bpb: 0.8353
- val bpb: 0.8359
- hellaswag_zeroshot: 0.1764
- jeopardy: 0.0260
- bigbench_qa_wikidata: 0.3921
- arc_easy: 0.4383
- arc_challenge: 0.0523
- copa: 0.3400
- commonsense_qa: 0.0274
- piqa: 0.3297
- openbook_qa: 0.1120
- lambada_openai: 0.3252
- hellaswag: 0.1768
- winograd: 0.1795
- winogrande: 0.0560
- bigbench_dyck_languages: 0.1280
- agi_eval_lsat_ar: -0.0109
- bigbench_cs_algorithms: 0.4106
- bigbench_operators: 0.1571
- bigbench_repeat_copy_logic: 0.0312
- squad: 0.1530
- coqa: 0.1665
- boolq: -0.3504
- bigbench_language_identification: 0.1758
- sample 0: <|bos|>The capital of France is Paris. It is the largest city in France and the capital of the country.
- sample 1: <|bos|>The chemical symbol of gold is Au. The chemical symbol of silver is Ag. The chemical symbol of copper is
- sample 2: <|bos|>If yesterday was Friday, then tomorrow will be Saturday. The day after yesterday, the day before tomorrow, the day after tomorrow
- sample 3: <|bos|>The opposite of hot is cold. The opposite of cold is hot. The opposite of hot is cold.
- sample 4: <|bos|>The planets of the solar system are: Mercury, Venus, Earth, Mars, Jupiter, Saturn, Uranus, Neptune
- sample 5: <|bos|>My favorite color is blue. It’s the color of the sky, the sky, the sky.
- sample 6: <|bos|>If 5*x + 3 = 13, then x is 5 and y is 3. If x = 5, then y
- unconditioned 0: <|bos|>The Summary View
Cold begins to take hold one day, for the novel opens. And the miracle of the flu begins and end on another day. And the reader finds themselves in a medieval power losing hand to the chivalrously serious; the priminarian, the being of the middle class and then the ridiculous chivalrously poor, continue to come to mind.
Mrs. Jones presents to King Arthur the Battle of Camber.
THE RAIN MEN OF THE NEWS Remember back in 1801, people reading this book remembered 2011. Harold and I had a summer closure in vacation which lasted four days, by
- unconditioned 1: <|bos|>New York Times, Monday 11 July 2019
Parents recognize second mental state
by Kenneth Koomez Followbreak Mobile
REMOCRACY, N.J. — If your little one struggles with a mental illness, there’s a good chance he cries or hears cries for other children. Some of my 20-year-old sons ended up in emergency rooms in elementary schools because they were unable to take their Amanda’s medication.
As long as children keep their fear to themselves — the mass of thought absorption — to forget that there’s another possible emotion lurking in their hearts — a blank stare — that can’t
- unconditioned 2: <|bos|>Inquiry Based Learning in the STEM Program
What is this program?
Our program breaks down learning into short, easy-to-understand pieces. For you to get to know each solution, you need the tools to use each one. Using tools creates a new way of learning as you collaborate with your peers and faculty to design STEM learning tools to meet the goals and expectations of the goals in the program. The aim is to learn together and, instead of being forced to learn separately yourself, now have the opportunity to learn in a way that will best serve you as a learner and educator.
What are the outcomes of this program?
“At
- unconditioned 3: <|bos|>Civil war over slavery
In recent years the factor which raised the relation between slavery and race has been intensely debated. The most prominent years of disputes have been those over the issue of slavery in the slave states, but further debate has often concentrated on the employment problems on plantations in the states formerly in slave-holding. Thus we have a materialistic reason and we are aware that one new issue raises seemingly still more problems. One arises from this materialism: are plantations now in the state in which they are supposed to be? - (paragraph 145).
Of about the same extent, however, there is another materialism which has
- unconditioned 4: <|bos|>Dialysis is an artificial kidney transplant that removes the waste in the blood from the patient. An automated patient monitoring system allows dialysis patients to work. Diet monitoring must be performed either by the dialysis patient themselves or by a healthcare professional. This increases the chance of complications. It is important to monitor blood pressure, heart rate, body mass, and oxygen content.
Anatomy of the Unit
A nephron is small tube that contains a number of tiny structures called nephrons. The nephrons are organized into two parts called the glomerulus and the tubule. The glomerulus is where the new blood is filtered while the tub
- unconditioned 5: <|bos|>Freedom in the World 2007: the Ramako Conflict
Famine, humiliation, torture and physical abuse characterize the political political situation in Indonesia in February 20071. However, the new trend of failing to fulfill pre-existing commitments to peace and stability, and allowing some of the violence witnessed since the establishment of the regime by a military coup in 1998 to rise from normal political activity, could leave Indonesians with considerable uncertainty and doubt as to the progress of reconciliation between the two major social factions namely, FAR and FGM.
The ongoing violence is especially evident, given that UNHCR (
- unconditioned 6: <|bos|>SANEUM: Biosystems Everywhere, Yes, Emerging Rangelands Are Actually Biome Deficit Missed
Posted 7 April 2008 | Updated 27 July 2008
You'll recall that we're talking about 22% of the world's land surface as being rangeland (yet less than 10% of all rangelands), not just the US and Mexico in the Piedmont area. And there are strong reasons why rangeland areas are vastly over-inflated: they're too small, too arid, and the sources of water supply to them are poor or none exist
- unconditioned 7: <|bos|>The bladder is located in the lower urinary tract, directly in front of the kidneys. It is the bag – like muscular organ that surrounds the patient by storing urine and ideas. The urethra is the tube that carries urine from the bladder to the outside of the body. It connects the bladder to the outside and that leads to the rectum. The prostate is contained within the bladder. Although the bladder has many other important functions, without it you would not simply pass urine. But many people do not expect an attack every single time because they are unaware that they have a problem.
Many different problems will affect the muscles within the urinary tract, from an


## Chat evaluation sft
timestamp: 2026-03-04 02:58:32

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
- ARC-Easy: 0.4285
- ARC-Challenge: 0.3686
- MMLU: 0.3287
- GSM8K: 0.0576
- HumanEval: 0.1037
- SpellingBee: 0.9844
- ChatCORE metric: 0.2744


## Summary

- Characters: 514,782
- Lines: 11,442
- Files: 47
- Tokens (approx): 128,695
- Dependencies (uv.lock lines): 3,618

| Metric          | BASE     | SFT      | RL       |
|-----------------|----------|----------|----------|
| CORE            | 0.1588   | -        | -        |
| ARC-Challenge   | -        | 0.3686   | -        |
| ARC-Easy        | -        | 0.4285   | -        |
| GSM8K           | -        | 0.0576   | -        |
| HumanEval       | -        | 0.1037   | -        |
| MMLU            | -        | 0.3287   | -        |
| ChatCORE        | -        | 0.2744   | -        |

Total wall clock time: 0h55m
