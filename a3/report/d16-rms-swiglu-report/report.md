# nanochat training report

Generated: 2026-03-05 05:18:16

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
- Characters: 517,350
- Lines: 11,495
- Files: 47
- Tokens (approx): 129,337
- Dependencies (uv.lock lines): 3,618

Run started: 2026-03-05 05:18:19

---

## Tokenizer evaluation
timestamp: 2026-03-05 05:17:50

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
timestamp: 2026-03-05 05:46:54

- run: 8h100_d16_rms_swiglu
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
- Number of parameters: 536,879,136
- Number of FLOPs per token: 1.660760e+09
- Calculated number of iterations: 4703
- Number of training tokens: 2,465,726,464
- Tokens : Scaling params ratio: 10.4991
- DDP world size: 8
- warmup_ratio: 0.0000
- warmdown_ratio: 0.5000
- final_lr_frac: 0.0000
- Minimum validation bpb: 0.8390
- Final validation bpb: 0.8390
- CORE metric estimate: 0.1798
- MFU %: 37.44%
- Total training flops: 4.094980e+18
- Total training time: 23.44m
- Peak memory usage: 27778.70MiB


## Base model evaluation
timestamp: 2026-03-05 05:53:19

- model: base_model (step 4703)
- CORE metric: 0.1725
- train bpb: 0.8384
- val bpb: 0.8390
- hellaswag_zeroshot: 0.1769
- jeopardy: 0.0189
- bigbench_qa_wikidata: 0.3799
- arc_easy: 0.4226
- arc_challenge: 0.0455
- copa: 0.3200
- commonsense_qa: 0.0418
- piqa: 0.3243
- openbook_qa: 0.1413
- lambada_openai: 0.3367
- hellaswag: 0.1779
- winograd: 0.2015
- winogrande: 0.0418
- bigbench_dyck_languages: 0.1380
- agi_eval_lsat_ar: 0.0543
- bigbench_cs_algorithms: 0.4053
- bigbench_operators: 0.1238
- bigbench_repeat_copy_logic: 0.0312
- squad: 0.1741
- coqa: 0.1778
- boolq: -0.1178
- bigbench_language_identification: 0.1793
- sample 0: <|bos|>The capital of France is Paris, which is the capital of France. The capital of France is Paris,
- sample 1: <|bos|>The chemical symbol of gold is Au. The chemical symbol of gold is Au. The chemical symbol of gold is
- sample 2: <|bos|>If yesterday was Friday, then tomorrow will be Saturday. The world is a big place, and the world is a big place
- sample 3: <|bos|>The opposite of hot is cold. The opposite of cold is hot. The opposite of hot is cold.
- sample 4: <|bos|>The planets of the solar system are: Mercury, Venus, Earth, Mars, Jupiter, Saturn, Uranus, Neptune
- sample 5: <|bos|>My favorite color is red. I love it. I love it. I love it. I love
- sample 6: <|bos|>If 5*x + 3 = 13, then x is 13. If 5*x + 3 = 13, then
- unconditioned 0: <|bos|>The Summary can be formatting or optional and further our goal is to make the students more focused and interested when reading by making and using our text as an addition to their daily learning routine.
We are losing children to obesity due to their electronic media; there’s so much kids being kept out of front and then we really have advantages to get meal times, maybe come play with the afternoon snack.
If we reduce the students screen time to one.
by setting a water timer on Thrill Planar we can see how we can make reading easier and more enjoyable so why don’t we put the pomodograph where other children can play some by
- unconditioned 1: <|bos|>New York Times, Monday, September 22, 2012
From the Editor:
by Kenneth Koomez Follow On Mobile | Posted By djeunockts at tbridge388.com On September 22, 2012, the New York Times reported that there was a total loss of sense of smell and taste among 226,000 children in elementary schools. This is likely one result of the public’s increasing obsession with controllable technologies—things like refrigerators, air-conditioners, air conditioners, refrigerators—they normally pass with sanity.
For the New York Times report, a Columbia University
- unconditioned 2: <|bos|>Inquiry Based Projects in the Zones of Bailys
Taking on the Culture of Knowledge
by Stephanie Silvia
Brief studies of how a male’s and a female’s experiences can profoundly influence each other have prompted greater discussion about how to tap into diverse student input. In other words, students can participate in STEM (science, technology, engineering and math) research and in exploring what opportunities are available to racially, and, occasionally, legally, excluded students. Additionally, some discussion has followed on how to share students’ findings with adult audiences. While the methodology and process for data analysis have been well documented, how do
- unconditioned 3: <|bos|>Civil Partnership 101: What It Is and How It Works
With more and more partners in IT, companies are finding themselves out of work (and businesses out of funds) on a regular basis, often with little ease. As a result, more companies turn to civil partnerships for progress in their efforts to become truly inclusive and solid: when people and companies are connected (which includes partnerships started by companies themselves ), human and/or investment capital can be used to protect the interest of partners in order to profit from shared enterprise solutions or commercial decision-making. This lesson covers Civil Partnerships and explains how those partnerships work.
What Is a Civil Partnership
- unconditioned 4: <|bos|>Dialysis is an artificial kidney dialysis that removes extra fluids and excess salts from the body. An automated external dialyzer (a machine that controls the settings within the dialyzer) is used to filter the dialysate. This increases the amount of waste products and removes partially purified fluid from the dialysate so it can be returned to the patient.
How does Dialysis work?
When a Cystochemist across Indiana treats you for Kidney Cancer®, he or she works tirelessly to keep your body healthy and happy. Dr. Dušil Āngela, Rithordable Hypertension and Clinics,
- unconditioned 5: <|bos|>Freedom in the World 2007 - the decision to bag your shoes has been one that has stood out for many years. It is categorically 'no safe gathering'. That winning legal prize is markedly different from all the other victories of freedom we'd like to keep track of, so this may be one of the most significant and prominent. It's time to take a look back and find out what normal people have done, what is the weight of victory and celebrate a Dream Deferred prize in just a moment. Let's dive deep into our objective of exploring the world with a Thunderbolt, the term we'll be using
- unconditioned 6: <|bos|>SANEUM: Biographies of Everyday America - American Memory
Print Archives | To Be
|Title||ADVANCED COMMUNICH | CHANCEY', BRISTANAGH PEOPLE - HAVE PERSCRIPTED SOME MAJOR-FORTH JEWS?
ABORMALLY A FATHER'S CHARTER MILWAY FOR
Lord-Sevenbergen! | Thomas S. Stanley, first Reorder of
General Jackson?, Aug. 1, 1875
JACKSON: In one todays comic, some distant country
- unconditioned 7: <|bos|>The bladder is located in the groin area which is located in the lower abdominal ave. People with bladder problems often suffer radiculopathy which causes a feeling of pressure along the fills of the bladder. Though this situation is not well-known, there are several symptoms which indicate that bladder problems arise.
The first that appears is usually pain in the bladder. Then comes ache upon urination due to stiffness and edema of bladder. Itching and discomfort is relieved simply by holding the bladder in a certain position for some time then must be relieved by the intake of a cup of liquid.
In case of carcinoma of the bladder, the discomfort comes due to enlargement


## Chat evaluation sft
timestamp: 2026-03-05 06:15:13

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
- ARC-Easy: 0.4870
- ARC-Challenge: 0.3908
- MMLU: 0.3347
- GSM8K: 0.0470
- HumanEval: 0.1098
- SpellingBee: 0.9961
- ChatCORE metric: 0.2949


## Summary

- Characters: 517,350
- Lines: 11,495
- Files: 47
- Tokens (approx): 129,337
- Dependencies (uv.lock lines): 3,618

| Metric          | BASE     | SFT      | RL       |
|-----------------|----------|----------|----------|
| CORE            | 0.1725   | -        | -        |
| ARC-Challenge   | -        | 0.3908   | -        |
| ARC-Easy        | -        | 0.4870   | -        |
| GSM8K           | -        | 0.0470   | -        |
| HumanEval       | -        | 0.1098   | -        |
| MMLU            | -        | 0.3347   | -        |
| ChatCORE        | -        | 0.2949   | -        |

Total wall clock time: 0h56m
