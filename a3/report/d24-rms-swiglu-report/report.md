# nanochat training report

Generated: 2026-03-05 06:46:19

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

Run started: 2026-03-05 06:46:22

---

## Base model training
timestamp: 2026-03-05 09:47:44

- run: 8h100_d24_rms_swiglu
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
- Number of parameters: 1,384,207,920
- Number of FLOPs per token: 4.945112e+09
- Calculated number of iterations: 7308
- Number of training tokens: 7,662,993,408
- Tokens : Scaling params ratio: 10.4999
- DDP world size: 8
- warmup_ratio: 0.0000
- warmdown_ratio: 0.5000
- final_lr_frac: 0.0000
- Minimum validation bpb: 0.7552
- Final validation bpb: 0.7552
- CORE metric estimate: 0.2539
- MFU %: 46.89%
- Total training flops: 3.789436e+19
- Total training time: 169.50m
- Peak memory usage: 62397.80MiB


## Base model evaluation
timestamp: 2026-03-05 09:56:00

- model: base_model (step 7308)
- CORE metric: 0.2504
- train bpb: 0.7547
- val bpb: 0.7552
- hellaswag_zeroshot: 0.3332
- jeopardy: 0.1880
- bigbench_qa_wikidata: 0.5194
- arc_easy: 0.5477
- arc_challenge: 0.1445
- copa: 0.3400
- commonsense_qa: 0.0407
- piqa: 0.4255
- openbook_qa: 0.1867
- lambada_openai: 0.4339
- hellaswag: 0.3351
- winograd: 0.3040
- winogrande: 0.1397
- bigbench_dyck_languages: 0.1280
- agi_eval_lsat_ar: 0.1141
- bigbench_cs_algorithms: 0.3879
- bigbench_operators: 0.1762
- bigbench_repeat_copy_logic: 0.0312
- squad: 0.3764
- coqa: 0.2746
- boolq: -0.0929
- bigbench_language_identification: 0.1743
- sample 0: <|bos|>The capital of France is Paris, and the capital of France is Paris. The capital of France is Paris
- sample 1: <|bos|>The chemical symbol of gold is Au. It is a soft, malleable, ductile, silvery
- sample 2: <|bos|>If yesterday was Friday, then tomorrow will be Saturday. If yesterday was Sunday, then tomorrow will be Monday. If yesterday was
- sample 3: <|bos|>The opposite of hot is cold. The opposite of cold is hot. The opposite of hot is cold.
- sample 4: <|bos|>The planets of the solar system are: Mercury, Venus, Earth, Mars, Jupiter, Saturn, Uranus, Neptune
- sample 5: <|bos|>My favorite color is blue. I love the blue sky, the blue sea, the blue sky.
- sample 6: <|bos|>If 5*x + 3 = 13, then x is a perfect square. If x is a perfect square, then x is a perfect
- unconditioned 0: <|bos|>The announcement in July 2020 was the one and only for the entire world. And it seemed as if by making and using technology, men would bring themselves to true happiness in the here and now. Suddenly we read that “The internet was our new home” being released on the slogan “Roboacyan” following the meal served at the UN headquarters with the world’s leaders to fuel a new generation of business done via video chat. Within a short stretch of time, technology started bringing us closer to a better tomorrow.
So far 2023 represents half of a decade that has passed in where technology pervaded virtually by
- unconditioned 1: <|bos|>New York Times, April 11, 2019
Parents recognize that mental illness affects children, but they aren’t sure how to even begin an early-detection process with a child who may show the signs.
“Most parents don’t know where to start,” recalled Randi Coopersmith, director of the Vanderbilt Clinic for Children with Schizophrenia and other Central Coast mental health professionals meeting as host Laura Snider and John Capotreschi of the Smithsonian Channel’s April 12 “REVEL BURNER” documentary guided fathers, pediatricians, psychiatrists, psychologists and other practitioners.
Coosmith said
- unconditioned 2: <|bos|>Learn how to develop formulas including a wide variety of formulas we will use on a daily basis from the math we use in everyday dealings to use in our home being able to use certain functions including percents, logarithms and arithmetic functions we know especially easy. Calculators practice worksheets These worksheets will enable students to practice incorporating new mathematical concepts in various formats it doesn't matter how old or in which grade your students are not will learn, and you can use the area function to practice yourself, or have the students take a series of tests. Types of functions such as sine, triangle and circle functions are most often illustrated and demonstrated on calculators.

- unconditioned 3: <|bos|>Civil war over the three day museum: George Monbiot's view
Bernie Frey editor of Spiked
"George Monbiot makes a good case for the need to fund a museum on human stories."
George Monbiot is the BBC World Service's environment correspondent in India. As a director of the Environmental Defense Fund for 37 years, he is contributing editor of Spicy: the human environmentalist magazine.
In a speech to a group in Lucknow 60 years ago, a spectator asked: 'galaman' has attracted about 56,000 visits to the National Museum of India.
- unconditioned 4: <|bos|>Dialysis is an artificial method of filtering your blood exiting kidneys. Urine is produced as waste is processed. Medically, a dialysis machine acts like a tiny kidney filtering your blood, and producing urine that’s collected in a container. Dialysis is used to treat certain diseases, especially when your kidneys can’t function properly, and sometimes for short-term periods of time, like when you are temporarily immobile.
We have created a comprehensive dialysis treatment program here at InSight Hill Hospitals, depending on your case, and your health status.
3.1% – 90% of people who will receive dialysis will survive for
- unconditioned 5: <|bos|>Freedom in the World
Freedom Rating (1 = best, 7 = worst)
Civil Liberties (1 = best, 7 = worst)
Political Rights (1 = best, 7 = worst)
In 2010, president Luis Egas Moniz announced his new crackdown on left-wing and prominent political dissidents. Moniz and the armed forces harshly criticized critics of his policies, including those who criticized opposition polls and government corruption, and used police tactics to intimidate activists. As a result, FARC member and former presidential candidate Juan Carlos Izpisua Belmonte allegedly disappeared
- unconditioned 6: <|bos|>SANEUM: Biosystems > FS-002
Print version ISSN 0277-6659
Bull World Health Organ vol.83 n.8 Genebra Aug. 2002
Factor structure-based screening for protein-G nutritional deficiency in sea-turtle-Fed elkhorn disease?
ABORIGIAD A, BILLES A-M, MILLAY T, PIERCE M, ILLYe M, CLARREA C, GARAGAS Eus, KAQUI CRJMBURLE
to be todays editor.
From Medscape
- unconditioned 7: <|bos|>The bladder is located in the lower urinary tract. It stores urine until it exits. People with spinal cord injuries suffer radiculopathy which causes a feeling of pressure or pain in the legs, back or in the abdomen, caused by impaired nerve conduction. Spinal cord injuries often cause scarring in the bladder that leads to obstruction (sometimes treatable) and ultimately lowers the bladder’s capacity. Spinal edema is a cause of bladder obstruction. Most causes simply block the flow of urine into the bladder, causing the bladder must be distended.
Urologists have found that pressure on sensitive nerve bundles that have been injured, such as certain spinal injuries


## Chat evaluation sft
timestamp: 2026-03-05 10:24:43

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
- ARC-Easy: 0.6288
- ARC-Challenge: 0.5111
- MMLU: 0.3890
- GSM8K: 0.0796
- HumanEval: 0.1037
- SpellingBee: 0.9922
- ChatCORE metric: 0.3690


## Summary

- Characters: 517,350
- Lines: 11,495
- Files: 47
- Tokens (approx): 129,337
- Dependencies (uv.lock lines): 3,618

| Metric          | BASE     | SFT      | RL       |
|-----------------|----------|----------|----------|
| CORE            | 0.2504   | -        | -        |
| ARC-Challenge   | -        | 0.5111   | -        |
| ARC-Easy        | -        | 0.6288   | -        |
| GSM8K           | -        | 0.0796   | -        |
| HumanEval       | -        | 0.1037   | -        |
| MMLU            | -        | 0.3890   | -        |
| ChatCORE        | -        | 0.3690   | -        |

Total wall clock time: 3h38m
