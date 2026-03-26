# nanochat training report

Generated: 2026-03-04 05:44:45

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
- Characters: 515,532
- Lines: 11,461
- Files: 47
- Tokens (approx): 128,883
- Dependencies (uv.lock lines): 3,618

Run started: 2026-03-04 05:44:49

---

## Base model training
timestamp: 2026-03-04 06:13:07

- run: 8h100_d16_swiglu
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
- Number of parameters: 536,840,224
- Number of FLOPs per token: 1.660760e+09
- Calculated number of iterations: 4703
- Number of training tokens: 2,465,726,464
- Tokens : Scaling params ratio: 10.4991
- DDP world size: 8
- warmup_ratio: 0.0000
- warmdown_ratio: 0.5000
- final_lr_frac: 0.0000
- Minimum validation bpb: 0.8398
- Final validation bpb: 0.8398
- CORE metric estimate: 0.1762
- MFU %: 39.90%
- Total training flops: 4.094980e+18
- Total training time: 21.69m
- Peak memory usage: 48501.58MiB


## Base model evaluation
timestamp: 2026-03-04 06:19:23

- model: base_model (step 4703)
- CORE metric: 0.1642
- train bpb: 0.8392
- val bpb: 0.8398
- hellaswag_zeroshot: 0.1798
- jeopardy: 0.0165
- bigbench_qa_wikidata: 0.3848
- arc_easy: 0.4349
- arc_challenge: 0.0614
- copa: 0.2400
- commonsense_qa: 0.1073
- piqa: 0.3177
- openbook_qa: 0.1093
- lambada_openai: 0.3276
- hellaswag: 0.1717
- winograd: 0.2015
- winogrande: 0.0292
- bigbench_dyck_languages: 0.1330
- agi_eval_lsat_ar: 0.1033
- bigbench_cs_algorithms: 0.3803
- bigbench_operators: 0.1619
- bigbench_repeat_copy_logic: 0.0312
- squad: 0.1577
- coqa: 0.1735
- boolq: -0.2941
- bigbench_language_identification: 0.1843
- sample 0: <|bos|>The capital of France is Paris. It is the largest city in France and the second largest in Europe.
- sample 1: <|bos|>The chemical symbol of gold is Au. It is a soft, malleable, malleable, mal
- sample 2: <|bos|>If yesterday was Friday, then tomorrow will be Saturday. If you are a fan of the “Saturday Night Live” show
- sample 3: <|bos|>The opposite of hot is cold. The opposite of cold is hot. The opposite of hot is cold.
- sample 4: <|bos|>The planets of the solar system are: Mercury, Venus, Earth, Mars, Jupiter, Saturn, Uranus, Neptune
- sample 5: <|bos|>My favorite color is red. I love it. I love it. I love it. I love
- sample 6: <|bos|>If 5*x + 3 = 13, then x is 5*x + 3 = 13. If x is 5
- unconditioned 0: <|bos|>The Summary can be found here (Advanced, our second online summary of the book). And the basics are gathered by John and Megan Isaacs in addition to Vol. V chapters 2 and 3 including Chapter 1 The Creation of a Moral Code and Chapter 2 The Old Testament Creation and Babylon. All of this is included on our facebook page for our first afternoon and it was well worth the time it took to look.
THE CREATIVE OF THE NEW TESTAMENT
The way to summarize the imagery is to look at the general message and understand the essential components to its message which will enable us to paraph
- unconditioned 1: <|bos|>New phenomenon first described in Australia goes further than previously hoped
Parents at The Mother of Hersby Middle School described the Followbreak Mobile Lab, a device that projects what would appear to be moves on a computer screen onto virtual reality images of animals moving in a virtual wildlife habitat.
Researchers at William & Mary's Albert Einstein School of Medicine in New York and Middlesex University in London describe a breakthrough research that hasn't been seen in this investigation form.
"The Independent Gathering was born from a sight word review," said Adam Britzsche, director of science and learning at the Albert Einstein School of Medicine in New York.
Britzsche said
- unconditioned 2: <|bos|>Learn how to develop formulas in Excel using simple and easy steps. Whether you’re a newbie or a professional, this guide will show you how to compile and run formulas and highlight features and calculations. By the end of this guide, you’ll be able to:
- Start building formulas with basic formulas and drag and drop them with a little guidance.
- Add formatting to formulas with options in the RX_NUM feature.
- Add formulas to help search area references with respect to records or ranges.
- Learn how to transfer type using the truncation command.
This guide also includes:
- Definitions and Writing Functions Using Excel.

- unconditioned 3: <|bos|>Civil war over 140th anniversary
Africa has historically been the site of an array of upheavals for many countries and peoples: from brutal acts of wars to the aftermaths of war, the continent’s frontiers and economies have changed quite dramatically on multiple continents.
The international historian Lawrence Hill has written: “It is not underrated that this 19th century new world started with very mountainous landscapes, with no options for manoeuvre of the trade empires. Western influence on the continent, ever expanding, divided decision-making. The Casino Civil about it.”
The epicenter of such conflicts.
During the last 
- unconditioned 4: <|bos|>Dialysis means dialysis or interosseous endoc-endyrelics (IACE) or patient's dialysis. That is a process of removing harmful substances from the blood, which is happening through a needle and holding exchange fluids. These fluids must be removed very strictly and slow, to prevent the cake from entering the body and diseases. To achieve this purpose, many dialysis units have two different procedures; the small fraction leaving across a patient's abdomen, and the large fraction placing an external catheter under the abdomen using a washable piece (Ha3.0), through a bowel tube (60-wb) .
Dialysis
- unconditioned 5: <|bos|>Freedom for the people consists of : To the decision and seriousness to compensate and secure their land by the community through mutual accountability and intimacy, ensuring mutual unity in terms of winning elections and ensuring social inclusion for all.
What to do about MSW exclusion ?
MSW exclusion occur when the MSW claimant without their benefits file claims their legal claimant never lives in the home and they claim it is
a ‘clear breach’, and they claim it means that they are not getting medical care or shelter
outreach support for MSW
Comprised of: Registered Population: Person who is claimed because of discrimination (whether
- unconditioned 6: <|bos|>SANEYLETT WALKS - IMPROVASCING IN TRIBUNE AND CATHOLIC
A Ṭafo', or by “beneficial service”, means the use of bodily or mental labour to provide good finished goods to the Camel Cross sisters in Kenya. In tradition, a type of secret or “benefit of justice” would come in the form of a “beneficial servicee”. Mostly, it meant services provided by institutions, whether the priests, kenyili, ‘laamdarimu to the Lobedu tribe, the
- unconditioned 7: <|bos|>The bladder is located in the lower part of the abdomen in the vagina. It's a pouch-like structure inside the muscular organ that surrounds the muscular bladder. Above and beyond the bladder, is the cloaca or passageway, the part that connects the external and internal sphincter muscles.
The square and thatched basil fitted with sliding stones.
The form adapted to a particular environment (e.g. kettle, readiness, etc.).
Plants sprung out of the ground, forming upright twigs, attached by means of stems, consisting of cups, called clavicles, swarming with small flowers, referred to as spikelets.
Alka


## Chat evaluation sft
timestamp: 2026-03-04 06:41:34

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
- ARC-Easy: 0.4558
- ARC-Challenge: 0.3771
- MMLU: 0.3334
- GSM8K: 0.0478
- HumanEval: 0.0915
- SpellingBee: 0.9883
- ChatCORE metric: 0.2804


## Summary

- Characters: 515,532
- Lines: 11,461
- Files: 47
- Tokens (approx): 128,883
- Dependencies (uv.lock lines): 3,618

| Metric          | BASE     | SFT      | RL       |
|-----------------|----------|----------|----------|
| CORE            | 0.1642   | -        | -        |
| ARC-Challenge   | -        | 0.3771   | -        |
| ARC-Easy        | -        | 0.4558   | -        |
| GSM8K           | -        | 0.0478   | -        |
| HumanEval       | -        | 0.0915   | -        |
| MMLU            | -        | 0.3334   | -        |
| ChatCORE        | -        | 0.2804   | -        |

Total wall clock time: 0h56m
