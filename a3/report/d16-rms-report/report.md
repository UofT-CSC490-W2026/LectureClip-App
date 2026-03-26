# nanochat training report

Generated: 2026-03-04 17:30:25

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
- Characters: 517,360
- Lines: 11,495
- Files: 47
- Tokens (approx): 129,340
- Dependencies (uv.lock lines): 3,618

Run started: 2026-03-04 17:30:28

---

## Base model training
timestamp: 2026-03-04 17:58:39

- run: 8h100_d16_rms
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
- Number of parameters: 536,911,904
- Number of FLOPs per token: 1.660957e+09
- Calculated number of iterations: 4704
- Number of training tokens: 2,466,250,752
- Tokens : Scaling params ratio: 10.4999
- DDP world size: 8
- warmup_ratio: 0.0000
- warmdown_ratio: 0.5000
- final_lr_frac: 0.0000
- Minimum validation bpb: 0.8351
- Final validation bpb: 0.8351
- CORE metric estimate: 0.1802
- MFU %: 40.98%
- Total training flops: 4.096336e+18
- Total training time: 21.77m
- Peak memory usage: 27687.83MiB


## Base model evaluation
timestamp: 2026-03-04 18:05:17

- model: base_model (step 4704)
- CORE metric: 0.1762
- train bpb: 0.8345
- val bpb: 0.8351
- hellaswag_zeroshot: 0.1833
- jeopardy: 0.0217
- bigbench_qa_wikidata: 0.3899
- arc_easy: 0.4366
- arc_challenge: 0.0671
- copa: 0.3200
- commonsense_qa: 0.0674
- piqa: 0.3264
- openbook_qa: 0.1093
- lambada_openai: 0.3272
- hellaswag: 0.1771
- winograd: 0.2381
- winogrande: 0.0718
- bigbench_dyck_languages: 0.1480
- agi_eval_lsat_ar: 0.0815
- bigbench_cs_algorithms: 0.4205
- bigbench_operators: 0.1571
- bigbench_repeat_copy_logic: 0.0312
- squad: 0.1492
- coqa: 0.1670
- boolq: -0.1991
- bigbench_language_identification: 0.1853
- sample 0: <|bos|>The capital of France is Paris. The capital of France is Paris. The capital of France is Paris.
- sample 1: <|bos|>The chemical symbol of gold is Au. It is a soft, malleable, ductile, malle
- sample 2: <|bos|>If yesterday was Friday, then tomorrow will be Saturday. If tomorrow is Saturday, then today will be Sunday. If tomorrow is
- sample 3: <|bos|>The opposite of hot is cold. The opposite of cold is hot. The opposite of cold is hot.
- sample 4: <|bos|>The planets of the solar system are: Mercury, Venus, Earth, Mars, Jupiter, Saturn, Uranus, Neptune
- sample 5: <|bos|>My favorite color is red. I love it. I love it. I love it. I love
- sample 6: <|bos|>If 5*x + 3 = 13, then x is a prime number. If 5*x + 3 = 13,
- unconditioned 0: <|bos|>The Summary in Flight Curve (SSC)
Ruskin S1 was a stable 3-km by 2-km traveling median star in the constellation Canes Venatici. Spaced along the chassis axis of her.
Young's Arc:
Two of the nine regions of the Young's arc that cross the cross were placed on the canes.
Young's arc to 0:
Geocentric Equation: The plane of Earth's orbit on the center line of the orbit is known as Geocentric Equation (GCE) and represents an Earth-Sun distance of 933,886 kilometers.
Log
- unconditioned 1: <|bos|>New York Times, Monday, September 22, 2012 at 9:57 p.m.
Long after thebreakup of the North Vietnamese and U.S. Armies in 1945, the Vietnam War was running amuck. U.S.S.R. would define its response to the war both through its economy and through its new military structure.
In that regard, it wasn’t good practice to host the eyes of the United States as this Independent Gathering—especially presidential inaugural addresses—which served as smoke absorption devices to the enormous dust-up of war emotions that was in the air in the Pacific. Highlighting the U
- unconditioned 2: <|bos|>Learn how to develop formulas including a tutorial video series from Intel. Whether you’re a newbie or a professional, this video tutorial on using multiplication formulas is a stepping stone to learning multiplication and addition. By the end of this video series we’ll be able to:
- Recall the correct way of adding and subtracting powers with a multiplication problem using our Knowledge Base.
True or false in these equations: The answer to “Twelve and Four” is 2 = 8.
Name some problems in maths that use multiplication, division and addition.
Sample Video – The correct way to multiply and divide with multiplication and division problems. Copy
- unconditioned 3: <|bos|>Civil Partnership 101: What is it?
Defining Civil Partnership
Courts across the United States can declare many different things as civil partnership, depending on their jurisdiction. Civil partnerships can be formed between individuals, businesses, and organizations. Civil partnerships are usually formed in government agencies, although some types of business partnerships may have a civil partnership involved. In 1996, the Fair Employment and Housing Practices Act governed the various options available to a person seeking a civil partnership in a government agency, such as a federal agency or state agency.
Civil Partnerships and Civil Partnerships Provisions
Federal Civil Partnership
A federal civil partnership combines
- unconditioned 4: <|bos|>Dialysis means replacing your kidneys with a machine that exits the body through a glister only. The machine removes waste and excess water from your blood so your body can return it to it when needed.
To find out what dialysis options are available, you can use the DaVita website to search for local providers that treat dialysis diseases. To learn what dialysis options are available, you can look at Cybovhemia across Australia.
Dialysis is a general term for an automatic or controlled process that removes waste, excess fluid (such as blood by passing it through a machine called a hemodialysis machine) from your blood
- unconditioned 5: <|bos|>Freedom in the World 2011: Turkey in the 21st Century
U.S. State Department Report - 21/2011
Revised/Consolidated UN Contact Information available for trade, commerce, diplomatic, consular, cultural, military, educational, scientific, judicial, economic or security communication systems (www.travelingle.com). APPENDICES: France, Barbary Coast, Republic of Seychelles, Morocco, The Dream, Lebanon, Oman, Qatar, United Arab Emirates, United Kingdom
Revised/Consolidated UN Contact Information available for trade, commerce
- unconditioned 6: <|bos|>SANEUM: Barrio of Clairvera, Emerging from MASYSIN — locale of the origin of the custom, in Esquelṭ
– 1503. Statica, consisting of the castle Bragari (Barthand) Tower and the garden Camelond (Camargi); affirmed at the Conquest of the Romans by the Mautica (Madrigal) Family. Mared in a strong position, according to Federico Barraccani and Amusiano Razzani, the ‘Cerdos’, one to whom the legend appears. R
- unconditioned 7: <|bos|>The bladder is located in the lower urinary tract, a part of the reproductive system that lies in the abdomen – the muscular organ that stores urine and ensures healthy function and comfort. The urethra is the tube that carries urine from the bladder out from the body. The bladder acts like a tube as it stores and that in itself is rather strange and horrifying.
Educating a person on the reasons for bladder infections, giving proper examinations and diagnosis, knowing the types of problems people face, and a list of useful websites must be built on the basis of the facts of the case. Unfortunately, as education progresses, some evidence-based treatment disparities also come


## Chat evaluation sft
timestamp: 2026-03-04 18:54:56

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
- ARC-Easy: 0.4562
- ARC-Challenge: 0.3609
- MMLU: 0.3334
- GSM8K: 0.0500
- HumanEval: 0.1159
- SpellingBee: 0.9922
- ChatCORE metric: 0.2820


## Summary

- Characters: 517,360
- Lines: 11,495
- Files: 47
- Tokens (approx): 129,340
- Dependencies (uv.lock lines): 3,618

| Metric          | BASE     | SFT      | RL       |
|-----------------|----------|----------|----------|
| CORE            | 0.1762   | -        | -        |
| ARC-Challenge   | -        | 0.3609   | -        |
| ARC-Easy        | -        | 0.4562   | -        |
| GSM8K           | -        | 0.0500   | -        |
| HumanEval       | -        | 0.1159   | -        |
| MMLU            | -        | 0.3334   | -        |
| ChatCORE        | -        | 0.2820   | -        |

Total wall clock time: 1h24m
