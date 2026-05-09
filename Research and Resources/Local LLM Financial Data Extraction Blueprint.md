# **Technical Analysis of Logic-Constrained Financial Intelligence Extraction via Small Parameter Local Large Language Models**

The shift toward localized, high-performance financial intelligence extraction using small-parameter Large Language Models (LLMs) in the 8B to 14B range represents a critical evolution in quantitative analysis and data sovereignty. As financial institutions and independent research desks seek to mitigate the latency, cost, and privacy concerns associated with centralized cloud-based architectures, the demand for deterministic, programmatic parsing on consumer-grade or repurposed hardware has intensified.1 The "Logic Constraint" methodology prioritizes the conversion of raw, unstructured financial feeds into high-fidelity structured data by leveraging the inherent capabilities of models like Llama 3 and Qwen when they are strictly bound by formal grammars and specific sampling parameters.4

## **Architectural Foundations of Local Financial Inference**

The deployment of local inference engines such as llama.cpp and its derivative wrappers like Ollama forms the bedrock of modern edge-based financial NLP pipelines. Selecting the appropriate inference backend is not merely a matter of convenience but a fundamental performance decision. llama.cpp, as a raw C++ engine, provides unparalleled access to hardware-level optimizations across CPUs and GPUs, enabling granular control over memory mapping and thread allocation.1 In contrast, Ollama offers a container-like abstraction that facilitates rapid prototyping and model management but often introduces a significant performance tax.1 Investigations into the 2026 local AI ecosystem reveal that Ollama can incur a performance penalty as high as 80% on larger model architectures compared to the raw power of llama.cpp.4

| Architectural Attribute | llama.cpp (Raw Engine) | Ollama (Abstraction Wrapper) |
| :---- | :---- | :---- |
| Performance Overhead | Minimal (Direct C++ execution) | High (Up to 80% penalty on large models) |
| Configuration Depth | High (CLI flags, GBNF, RPC servers) | Moderate (Modelfiles, Environment variables) |
| Hardware Flexibility | Extreme (ARM, Raspberry Pi, Multi-node RPC) | Desktop-oriented (macOS, Windows, Linux) |
| API Interface | Customizable Server (OpenAI compatible) | Standardized Local REST API |
| Model Format | GGUF / GGML | Library-based / Modelfile |

For researchers operating on repurposed Linux hardware, the ability of llama.cpp to split model layers across heterogeneous GPUs and CPUs via an RPC server is a vital feature, allowing 120B parameter models to run at functional speeds even when individual workstation memory is constrained.4 The recent acquisition of the GGML/llama.cpp ecosystem by Hugging Face further signals a future where the gap between ease of use and raw performance continues to narrow, yet for maximum determinism in financial parsing, the raw CLI-driven approach remains the industry standard.4

### **Hardware and VRAM Allocation in Financial Parsing**

Running 8B to 14B parameter models locally requires a nuanced understanding of quantization and context window overhead. Financial parsing tasks involving dozens of RSS articles or lengthy 10-K filings necessitate expanded context windows, which consume VRAM exponentially.9 A standard Llama 3 8B model typically requires approximately 5GB to 8GB of VRAM depending on the quantization level (e.g., 4-bit vs 8-bit), but increasing the context window (num\_ctx) to 32,000 tokens can push this requirement to over 15GB.9

| Parameter Size | Quantization | Context Window (tokens) | Estimated VRAM Usage |
| :---- | :---- | :---- | :---- |
| 8B | 4-bit (Q4\_K\_M) | 2,048 | \~5.5 GB |
| 8B | 8-bit (Q8\_0) | 2,048 | \~8.5 GB |
| 8B | 4-bit (Q4\_K\_M) | 32,768 | \~12-15 GB |
| 14B | 4-bit (Q4\_K\_M) | 8,192 | \~11-13 GB |

For production pipelines where reliability is paramount, 4-bit quantization via Generative Post-Training Quantization (GPTQ) or GGUF formats is often preferred. This approach achieves an optimal balance between accuracy and memory efficiency, allowing models to reside entirely on-GPU for maximum inference speed.9

## **Programmatic Determinism: The GBNF and Logit Masking Paradigm**

To force a local LLM to act as a strict data parser rather than a conversational agent, the implementation must move beyond system prompting and into the domain of constrained decoding.5 While system prompts provide instructions, they do not physically prevent the model from generating conversational "fluff" or malformed JSON.15 The primary mechanism for ensuring programmatic reliability in llama.cpp is the GGML Backus-Naur Form (GBNF) grammar.5

GBNF operates by applying a mask to the model's output logits during each step of the decoding process. If the grammar specifies that the next character must be a quote or a colon, the engine effectively sets the probability of all other tokens to zero.14 This ensures that the output is syntactically valid by construction. For example, a GBNF grammar can enforce that the model only selects from a specific set of asset classes or strictly adheres to a numeric range for sentiment scoring.5

### **Grammar vs. System Prompting Effectiveness**

The comparative effectiveness of these methods is striking when applied to smaller models like Llama 3 8B. Smaller models are prone to "thinking" spills and repetitive tokens, especially when under-quantized.15 GBNF mitigates these failures by constraining the state space of the model to the defined schema.14

| Constraint Method | Mechanism | Output Reliability | Performance Impact |
| :---- | :---- | :---- | :---- |
| System Prompting | Probabilistic Instruction | Low (prone to hallucinations/fluff) | None |
| Few-Shot Prompting | Contextual Examples | Moderate (improves pattern matching) | Increased token usage |
| JSON Mode (API) | Internal Heuristics | High (format-specific) | Variable |
| GBNF Grammars | Logit Masking | Absolute (forced syntax compliance) | Low to Moderate (decoding overhead) |

While GBNF guarantees syntactic correctness, it does not guarantee semantic accuracy. A model might generate a perfectly formatted JSON object that misidentifies a dovish signal as hawkish.18 Therefore, the synergy between a highly constrained system prompt (for intent) and a GBNF file (for structure) is essential for a production-grade logic blueprint.17 Furthermore, research into Llama 3 models has identified that overly restrictive grammars can sometimes cause a reduction in GPU utilization or tokens per second compared to unconstrained generation, though the trade-off for valid data is typically acceptable in financial contexts.21

## **Financial Sentiment NLP Frameworks**

Financial sentiment analysis represents a specialized domain where general-purpose sentiment models often fail due to the intense context-dependency of economic rhetoric.23 In quantitative finance, the primary objective is often the zero-shot classification of central bank communications and corporate earnings calls into actionable metrics.12

### **Hawkish vs. Dovish Logic in LLM Prompting**

The distinction between "hawkish" (contractionary/inflation-focused) and "dovish" (expansionary/employment-focused) signals requires the model to interpret the same data point differently based on the prevailing economic climate.23 A "strong labor market" might be a dovish signal in a weak economy—indicating no need for further stimulus—but it becomes a hawkish signal in an overheated economy, suggesting a need for interest rate hikes to combat inflation.23

To quantify this, quants utilize specialized scoring frameworks. The Fed's Monetary Policy Reports (MPRs) are frequently analyzed using continuous stance scores ranging from \-2 (Extreme Dovish) to \+2 (Extreme Hawkish).25 The logic for these prompts often includes detailed definitions of the underlying channels of monetary policy:

* **Interest Rate Channel:** Market expectations of credit demand and rate adjustments.23  
* **Credit Channel:** Observations on loan growth and credit creation.23  
* **Asset Price Channel:** Wealth effects stemming from improved earnings expectations.23

Recent studies have introduced Delta-Consistent Scoring (DCS), which moves beyond isolated classification to track the *shift* in tone between consecutive FOMC meetings.26 This framework uses the temporal relationship between statements as a form of self-supervision, achieving up to 71.1% accuracy on sentence-level classification without manual labels.26

### **Supply Chain Risk and Severity Scaling**

Beyond central bank rhetoric, quants employ LLMs to rank the severity of supply chain disruptions on 1-10 scales.28 This requires the model to analyze historical breaches and security failures across dimensions of intent, nature, and impact.29

For these tasks, few-shot prompting has been shown to outperform Chain of Thought (CoT) reasoning in local 8B-30B models.12 Researchers found that sentiment and clarity (vagueness) tasks are less nuanced than hawkish/dovish detection, allowing local quantized models to exceed 75% accuracy when provided with 1-2 examples of high-impact versus low-impact events.12 The severity score is typically a synthesis of the disruption's duration, the criticality of the affected components, and the geopolitical context of the supplier.28

## **Token Efficiency and High-Throughput Pre-processing**

When processing large volumes of financial data—such as 50 RSS articles in a single context window—the "token diet" becomes a critical engineering constraint.31 Every superfluous token in the input increases the latency of the first token and consumes VRAM that could otherwise be allocated to a larger model or a longer history.4

### **Aggressive Text Pre-processing Workflows**

Effective pre-processing for local LLMs involves several stages of data reduction. While traditional NLP often focused on lowercasing and stemming, modern LLMs benefit more from structural cleaning and noise removal.32

1. **HTML Stripping and Content Extraction:** Raw scraped data from RSS feeds is laden with boilerplate, scripts, and navigation menus. Tools like Trafilatura are industry-leading for this task, as they intelligently identify the "main text" of an article while discarding extraneous elements.37 This can reduce the token count of a web page by 20-40%.32  
2. **Whitespace and Unicode Normalization:** Collapsing multiple spaces, tabs, and newlines into single characters and normalizing to NFC form ensures the model's internal attention is not wasted on formatting artifacts.32  
3. **Context-Specific Stopword Removal:** While generic stopword removal can sometimes hurt LLM comprehension, removing repetitive website banners, "click here" links, and social media sharing text is vital for financial feeds.35  
4. **Deduplication:** Financial news is highly redundant. Implementing MinHash or Jaccard similarity checks before feeding text to the LLM prevents the model from processing the same headline multiple times across different providers.32

| Pre-processing Step | Targeted Noise | Impact on Token Count | Best Tool |
| :---- | :---- | :---- | :---- |
| Boilerplate Removal | Headers, Footers, Sidebars | 30-50% reduction | Trafilatura |
| Whitespace Collapse | Tabs, excessive newlines | 5-15% reduction | sed / tr / Python |
| Deduplication | Identical/Near-identical news | Variable (High for RSS) | MinHash / LSH |
| HTML-to-Markdown | Script tags, styles, attributes | 20-40% reduction | html-to-markdown |

For a repurposed Linux box with a single RTX 3090 (24GB VRAM), these techniques are the difference between running a Llama 3 8B with a 32k context and being forced to use a much smaller, less capable model.10

## **Second-Order Synthesis and Multi-Pass Logic**

One of the most complex tasks for small LLMs is the synthesis of disparate events to identify "hidden risks" or second-order effects.42 A first-order effect is the immediate consequence of an event (e.g., a port strike delays shipping), while a second-order effect is the ripple effect (e.g., shipping delays lead to parts shortages, which trigger inflation, causing the central bank to maintain high interest rates).42

### **The "Synthesis" Prompting Strategy**

Small models (8B-14B) often lack the raw reasoning capacity to perform this synthesis in a single pass while maintaining strict JSON formatting.18 Researchers employ a multi-pass prompting or "agentic" workflow to overcome this.50

* **Pass 1: Analytical Reasoning.** The model is prompted to "think out loud" (CoT) and analyze 5 disparate events. The output is a prose analysis of potential intersections. The trigger phrase "Let's think step by step" is standard for eliciting this reasoning.48  
* **Pass 2: Structured Extraction.** A second, more constrained prompt takes the Pass 1 analysis as input and extracts the "hidden risk" into a structured JSON field.51

This "Evaluator-Optimizer" pattern increases reliability by decoupling the creative reasoning phase from the deterministic parsing phase.51 It mirrors the human investment process: fast heuristics for simple cases, and deliberate, multi-stage reasoning for complex ambiguity.50

### **Hidden Risk Logic Blueprint**

When prompting for second-order effects, quants use "Persona Variation" to surface different risks.55 For instance:

* **The Skeptic Agent:** Instructed to find flaws in market optimism and identify tail risks.55  
* **The Pragmatist Agent:** Focuses on actionable supply chain shifts.55  
* **The Second-Order Specialist:** Explicitly instructed to ignore first-order impacts and look for delayed consequences.47

By running these personas in parallel and then using a final "consensus" prompt to join the findings, researchers achieve a more robust and comprehensive risk assessment than any single prompt could provide.50

## **Implementation: The Logic Blueprint for Financial Intelligence**

To transition these research findings into a production system, developers must configure the local inference engine with maximum determinism and structured integrity.

### **Recommended Local API Parameters**

Maximum determinism is achieved by reducing the stochasticity of the token selection process.59

| Parameter | Recommended Setting | Technical Justification |
| :---- | :---- | :---- |
| temperature | 0.0 or 0.01 | Effectively enables greedy decoding; 0.01 stabilizes FP8 rounding.16 |
| top\_p | 0.01 to 0.1 | Restricts token selection to only the most probable candidates.16 |
| min\_p | 0.05 to 0.1 | Dynamically filters noise tokens based on the top token's probability.59 |
| num\_ctx | 16,384+ | Necessary for multi-document parsing; requires careful VRAM monitoring.10 |
| n\_predict | 512 | Prevents the model from generating conversational "trails" at the end of JSON.8 |
| repeat\_penalty | 1.1 | Discourages the model from repeating commas or null values in long arrays.15 |

The mathematical foundation of these parameters lies in the transformation of the logit vector ![][image1] into the probability distribution ![][image2] through the softmax function, scaled by temperature ![][image3]:

![][image4]  
As ![][image5], the highest logit ![][image6] dominates the distribution, ensuring the model's output is predictable and repeatable across identical runs.55

### **Highly Constrained System Prompt for Financial Entity Extraction**

The following prompt structure is designed to minimize conversational overhead and maximize data density.

### **SYSTEM ROLE**

You are a non-conversational, deterministic financial data parser. Your output must strictly adhere to the provided JSON schema.

### **EXECUTION RULES**

1. Output ONLY a valid JSON object.  
2. No conversational preambles, "fluff," or post-analysis explanations.  
3. If a field is not explicitly present in the source text, use "null".  
4. Do not summarize; extract precise values and entities.  
5. Adhere to the defined enums for classification tasks.

### **EXTRACTION DEFINITIONS**

* Impact Score: Integer scale (1-10) where 1 is negligible and 10 is systemic collapse.  
* Asset Class: \[Equities, Fixed Income, Commodities, Currencies, Crypto\].  
* Sentiment: \[Positive, Neutral, Negative\].  
* Policy Stance:.

### **INPUT TEXT**

{{raw\_scraped\_text}}

### **JSON Schema for Financial Intelligence Output**

This schema ensures that all extraction points are typed and validated, facilitating direct integration into quantitative trading systems or SQL databases.13

JSON

{  
  "type": "object",  
  "properties": {  
    "report\_timestamp": { "type": "string", "format": "date-time" },  
    "entities": {  
      "type": "array",  
      "items": {  
        "type": "object",  
        "properties": {  
          "name": { "type": "string" },  
          "asset\_class": { "type": "string", "enum": \["Equities", "Fixed Income", "Commodities", "Currencies", "Crypto"\] },  
          "sentiment": { "type": "string", "enum": \["Positive", "Neutral", "Negative"\] },  
          "impact\_score": { "type": "integer", "minimum": 1, "maximum": 10 }  
        },  
        "required": \["name", "asset\_class", "sentiment", "impact\_score"\]  
      }  
    },  
    "macro\_analysis": {  
      "type": "object",  
      "properties": {  
        "policy\_stance": { "type": "string", "enum": },  
        "hidden\_risk\_summary": { "type": "string", "description": "Synthesis of second-order effects from disparate events." }  
      }  
    }  
  },  
  "required": \["entities", "macro\_analysis"\]  
}

## **Security, Privacy, and "Shadow AI" Implications**

The decision to host 8B-14B models locally is frequently driven by the emergence of "Shadow AI" risks within the enterprise.44 Research shows that approximately 8.5% of workplace AI prompts contain sensitive information, with 46% of that data involving customer records or billing details.66 By moving financial intelligence parsing to a local Linux environment, institutions eliminate the "leak surface" where proprietary algorithms, internal contracts, or sensitive trade data might be used to train third-party models.65

Furthermore, local models are susceptible to prompt injection attacks, where malicious data in a scraped document might instruct the model to leak its system prompt or ignore its logic constraints.65 Developers must implement "Input Filters" and "Output Checks" at the API level to sanitize both the incoming scraped text and the generated JSON before it reaches downstream databases.43 This "Zero Trust" architecture ensures that the LLM remains a reliable, sandboxed tool within the broader financial data pipeline.

The transition to logic-constrained local LLMs represents a fundamental shift in AI architecture—from "generative" to "extractive" applications.68 By utilizing 8B-14B models not as writers, but as high-precision logit-masked engines, quants can build autonomous research systems that rival the reliability of human analysts while operating at a scale and speed that is otherwise impossible to achieve.54

#### **Works cited**

1. Llama.cpp vs Ollama: Choosing the Best Local LLM Tool in 2026 \- Openxcell, accessed April 13, 2026, [https://www.openxcell.com/blog/llama-cpp-vs-ollama/](https://www.openxcell.com/blog/llama-cpp-vs-ollama/)  
2. Help choosing between Ollama, llama.cpp, or something else for background LLM server (used with dictation) : r/LocalLLaMA \- Reddit, accessed April 13, 2026, [https://www.reddit.com/r/LocalLLaMA/comments/1mdma9a/help\_choosing\_between\_ollama\_llamacpp\_or/](https://www.reddit.com/r/LocalLLaMA/comments/1mdma9a/help_choosing_between_ollama_llamacpp_or/)  
3. Prompt Engineering and Format on LLMs in the Financial Domain \- ResearchGate, accessed April 13, 2026, [https://www.researchgate.net/publication/389505211\_Prompt\_Engineering\_and\_Format\_on\_LLMs\_in\_the\_Financial\_Domain](https://www.researchgate.net/publication/389505211_Prompt_Engineering_and_Format_on_LLMs_in_the_Financial_Domain)  
4. Ollama vs Llama.cpp: The Performance Reality \- YouTube, accessed April 13, 2026, [https://www.youtube.com/watch?v=AeowzDOmX\_U](https://www.youtube.com/watch?v=AeowzDOmX_U)  
5. Grammars (GBNF) \- llama.cpp \- Mintlify, accessed April 13, 2026, [https://www.mintlify.com/ggml-org/llama.cpp/advanced/grammars](https://www.mintlify.com/ggml-org/llama.cpp/advanced/grammars)  
6. GBNF grammars Projects \- AI Tinkerers \- Seattle, accessed April 13, 2026, [https://seattle.aitinkerers.org/technologies/gbnf-grammars](https://seattle.aitinkerers.org/technologies/gbnf-grammars)  
7. Llama.cpp Tutorial: A Complete Guide to Efficient LLM Inference and Implementation, accessed April 13, 2026, [https://www.datacamp.com/tutorial/llama-cpp-tutorial](https://www.datacamp.com/tutorial/llama-cpp-tutorial)  
8. How to set ollama temperature from command line \- GenAI Stack Exchange, accessed April 13, 2026, [https://genai.stackexchange.com/questions/699/how-to-set-ollama-temperature-from-command-line](https://genai.stackexchange.com/questions/699/how-to-set-ollama-temperature-from-command-line)  
9. llama 3.1 8b params downloaded from huggingface, strange num\_ctx behavior · Issue \#6817 \- GitHub, accessed April 13, 2026, [https://github.com/ollama/ollama/issues/6817](https://github.com/ollama/ollama/issues/6817)  
10. How does num\_ctx and model's context length work (together)? : r/ollama \- Reddit, accessed April 13, 2026, [https://www.reddit.com/r/ollama/comments/1j4egbh/how\_does\_num\_ctx\_and\_models\_context\_length\_work/](https://www.reddit.com/r/ollama/comments/1j4egbh/how_does_num_ctx_and_models_context_length_work/)  
11. How does num\_predict and num\_ctx work? : r/ollama \- Reddit, accessed April 13, 2026, [https://www.reddit.com/r/ollama/comments/1e4hklk/how\_does\_num\_predict\_and\_num\_ctx\_work/](https://www.reddit.com/r/ollama/comments/1e4hklk/how_does_num_predict_and_num_ctx_work/)  
12. Evaluating Local Language Models: An Application to Financial ..., accessed April 13, 2026, [https://www.kansascityfed.org/documents/9862/rwp23-12cookkazinnikhansenmcadam.pdf](https://www.kansascityfed.org/documents/9862/rwp23-12cookkazinnikhansenmcadam.pdf)  
13. PARSE: LLM Driven Schema Optimization for Reliable Entity Extraction \- arXiv, accessed April 13, 2026, [https://arxiv.org/html/2510.08623v1](https://arxiv.org/html/2510.08623v1)  
14. Grammars (GBNF) \- llama.cpp \- Mintlify, accessed April 13, 2026, [https://mintlify.com/ggml-org/llama.cpp/advanced/grammars](https://mintlify.com/ggml-org/llama.cpp/advanced/grammars)  
15. Llama.cpp vs Ollama \- Same model, parameters and system prompts but VASTLY different experiences : r/LocalLLaMA \- Reddit, accessed April 13, 2026, [https://www.reddit.com/r/LocalLLaMA/comments/1oppdxi/llamacpp\_vs\_ollama\_same\_model\_parameters\_and/](https://www.reddit.com/r/LocalLLaMA/comments/1oppdxi/llamacpp_vs_ollama_same_model_parameters_and/)  
16. non-deterministic output from Llama : r/PromptEngineering \- Reddit, accessed April 13, 2026, [https://www.reddit.com/r/PromptEngineering/comments/1icw35f/nondeterministic\_output\_from\_llama/](https://www.reddit.com/r/PromptEngineering/comments/1icw35f/nondeterministic_output_from_llama/)  
17. GBNF grammar VS Accuracy : r/LocalLLaMA \- Reddit, accessed April 13, 2026, [https://www.reddit.com/r/LocalLLaMA/comments/17ef035/gbnf\_grammar\_vs\_accuracy/](https://www.reddit.com/r/LocalLLaMA/comments/17ef035/gbnf_grammar_vs_accuracy/)  
18. Teaching an LLM to Write Assembly: GBNF-Constrained Generation for a Custom 8-Bit CPU, accessed April 13, 2026, [https://www.jamesdrandall.com/posts/gbnf-constrained-generation/](https://www.jamesdrandall.com/posts/gbnf-constrained-generation/)  
19. JSON-Schema to GBNF, accessed April 13, 2026, [https://adrienbrault.github.io/json-schema-to-gbnf/](https://adrienbrault.github.io/json-schema-to-gbnf/)  
20. Using Grammar | node-llama-cpp, accessed April 13, 2026, [https://node-llama-cpp.withcat.ai/guide/grammar](https://node-llama-cpp.withcat.ai/guide/grammar)  
21. Lllama 3 \*much\* slower with grammar · abetlen llama-cpp-python · Discussion \#1376, accessed April 13, 2026, [https://github.com/abetlen/llama-cpp-python/discussions/1376](https://github.com/abetlen/llama-cpp-python/discussions/1376)  
22. gbnf \- crates.io: Rust Package Registry, accessed April 13, 2026, [https://crates.io/crates/gbnf](https://crates.io/crates/gbnf)  
23. Interpreting Fedspeak with Confidence: A LLM-Based Uncertainty-Aware Framework Guided by Monetary Policy Transmission Paths, accessed April 13, 2026, [https://ojs.aaai.org/index.php/AAAI/article/view/40739/44700](https://ojs.aaai.org/index.php/AAAI/article/view/40739/44700)  
24. Interpreting Fedspeak with Confidence: A LLM-Based Uncertainty-Aware Framework Guided by Monetary Policy Transmission Paths \- arXiv, accessed April 13, 2026, [https://arxiv.org/html/2508.08001v2](https://arxiv.org/html/2508.08001v2)  
25. Hawkish or Dovish? That Is the Question: Agentic Retrieval of FED Monetary Policy Report, accessed April 13, 2026, [https://www.mdpi.com/2227-7390/13/20/3255](https://www.mdpi.com/2227-7390/13/20/3255)  
26. Mind the Shift: Decoding Monetary Policy Stance from FOMC Statements with Large Language Models \- arXiv, accessed April 13, 2026, [https://arxiv.org/html/2603.14313v1](https://arxiv.org/html/2603.14313v1)  
27. Daily Papers \- Hugging Face, accessed April 13, 2026, [https://huggingface.co/papers?q=continuous%20scores](https://huggingface.co/papers?q=continuous+scores)  
28. LLM03:2025 Supply Chain \- OWASP Gen AI Security Project, accessed April 13, 2026, [https://genai.owasp.org/llmrisk/llm032025-supply-chain/](https://genai.owasp.org/llmrisk/llm032025-supply-chain/)  
29. An Empirical Study on Using Large Language Models to Analyze Software Supply Chain Security Failures, accessed April 13, 2026, [https://davisjam.github.io/files/publications/SinglaAnandayuvarajKaluSchorlemmerDavis-LLMsForSupplyChainFailureAnalysis-SCORED2023.pdf](https://davisjam.github.io/files/publications/SinglaAnandayuvarajKaluSchorlemmerDavis-LLMsForSupplyChainFailureAnalysis-SCORED2023.pdf)  
30. 5 Best Tools to Turn Websites into AI-Ready Data | by David Fagbuyiro | Medium, accessed April 13, 2026, [https://medium.com/@davidfagb/5-best-tools-to-turn-websites-into-ai-ready-data-f6dad0f21b3e](https://medium.com/@davidfagb/5-best-tools-to-turn-websites-into-ai-ready-data-f6dad0f21b3e)  
31. Learn Preparing RSS Data for LLMs | Turning ODT into a Visual Workflow \- Codefinity, accessed April 13, 2026, [https://codefinity.com/courses/v2/508f89fc-4a9c-489a-9a42-91a84d72138f/457eea27-cdbf-4d26-9173-10839c0cf772/4fe6f9a6-05e7-44cf-bff7-d47dc48d1e39](https://codefinity.com/courses/v2/508f89fc-4a9c-489a-9a42-91a84d72138f/457eea27-cdbf-4d26-9173-10839c0cf772/4fe6f9a6-05e7-44cf-bff7-d47dc48d1e39)  
32. How to Clean Text for LLMs: The Complete Preprocessing Checklist (2025), accessed April 13, 2026, [https://thetexttool.com/blog/clean-text-for-llms-preprocessing-checklist-2025](https://thetexttool.com/blog/clean-text-for-llms-preprocessing-checklist-2025)  
33. Prompts to Profits: The Unit Economics of LLMs \- Petronella Technology Group, accessed April 13, 2026, [https://petronellatech.com/blog/prompts-to-profits-the-unit-economics-of-llms/](https://petronellatech.com/blog/prompts-to-profits-the-unit-economics-of-llms/)  
34. Top techniques to Manage Context Lengths in LLMs \- Agenta, accessed April 13, 2026, [https://agenta.ai/blog/top-6-techniques-to-manage-context-length-in-llms](https://agenta.ai/blog/top-6-techniques-to-manage-context-length-in-llms)  
35. Investigating Large Language Models' Linguistic Abilities for Text Preprocessing \- arXiv, accessed April 13, 2026, [https://arxiv.org/html/2510.11482v1](https://arxiv.org/html/2510.11482v1)  
36. Preprocessing Text for LLM Embeddings at Scale, accessed April 13, 2026, [https://cognoscerellc.com/preprocessing-text-for-llm-embeddings-at-scale/](https://cognoscerellc.com/preprocessing-text-for-llm-embeddings-at-scale/)  
37. HTML Preprocessing for LLMs \- DEV Community, accessed April 13, 2026, [https://dev.to/rosgluk/html-preprocessing-for-llms-3mk8](https://dev.to/rosgluk/html-preprocessing-for-llms-3mk8)  
38. Comparison of python trafilatura vs html2text libraries \- Web Scraping FYI, accessed April 13, 2026, [https://webscraping.fyi/lib/compare/python-html2text-vs-python-trafilatura/](https://webscraping.fyi/lib/compare/python-html2text-vs-python-trafilatura/)  
39. Fit 20% more context into your prompts using this lightweight pre-processor (Benchmarks included) : r/LocalLLaMA \- Reddit, accessed April 13, 2026, [https://www.reddit.com/r/LocalLLaMA/comments/1ppae98/fit\_20\_more\_context\_into\_your\_prompts\_using\_this/](https://www.reddit.com/r/LocalLLaMA/comments/1ppae98/fit_20_more_context_into_your_prompts_using_this/)  
40. Text pre-processing: Stop words removal using different libraries \- Medium, accessed April 13, 2026, [https://medium.com/data-science/text-pre-processing-stop-words-removal-using-different-libraries-f20bac19929a](https://medium.com/data-science/text-pre-processing-stop-words-removal-using-different-libraries-f20bac19929a)  
41. Mastering LLM Techniques: Text Data Processing | NVIDIA Technical Blog, accessed April 13, 2026, [https://developer.nvidia.com/blog/mastering-llm-techniques-data-preprocessing/](https://developer.nvidia.com/blog/mastering-llm-techniques-data-preprocessing/)  
42. MSI :: State of SecurityMSI :: State of Security | Insight from the Information Security Experts, accessed April 13, 2026, [https://stateofsecurity.com/](https://stateofsecurity.com/)  
43. How To Archives \- MSI :: State of Security, accessed April 13, 2026, [https://stateofsecurity.com/category/how-to/](https://stateofsecurity.com/category/how-to/)  
44. The second order effects of large language models | by January Capital \- Medium, accessed April 13, 2026, [https://january-capital.medium.com/the-second-order-effects-of-large-language-models-49c78024064d](https://january-capital.medium.com/the-second-order-effects-of-large-language-models-49c78024064d)  
45. Dynamic Feature Engineering Through Reinforcement and Prompt Based Learning, accessed April 13, 2026, [https://www.preprints.org/manuscript/202505.2193](https://www.preprints.org/manuscript/202505.2193)  
46. CPOstrategy, accessed April 13, 2026, [https://cpostrategy.media/?p=interface](https://cpostrategy.media/?p=interface)  
47. Causal Reasoning and Large Language Models for Military Decision-Making: Rethinking the Command Structures in the Era of Generative AI \- MDPI, accessed April 13, 2026, [https://www.mdpi.com/2673-2688/7/1/14](https://www.mdpi.com/2673-2688/7/1/14)  
48. 8 Chain-of-Thought Techniques To Fix Your AI Reasoning | Galileo, accessed April 13, 2026, [https://galileo.ai/blog/chain-of-thought-prompting-techniques](https://galileo.ai/blog/chain-of-thought-prompting-techniques)  
49. AI is Moving into the Runtime \- Medium, accessed April 13, 2026, [https://medium.com/@jengas/ai-is-moving-into-the-runtime-201927e60a14](https://medium.com/@jengas/ai-is-moving-into-the-runtime-201927e60a14)  
50. Multi-Agent collaboration patterns with Strands Agents and Amazon Nova \- AWS, accessed April 13, 2026, [https://aws.amazon.com/blogs/machine-learning/multi-agent-collaboration-patterns-with-strands-agents-and-amazon-nova/](https://aws.amazon.com/blogs/machine-learning/multi-agent-collaboration-patterns-with-strands-agents-and-amazon-nova/)  
51. Agentic AI for Finance: Workflows, Tips, and Case Studies, accessed April 13, 2026, [https://rpc.cfainstitute.org/research/the-automation-ahead-content-series/agentic-ai-for-finance](https://rpc.cfainstitute.org/research/the-automation-ahead-content-series/agentic-ai-for-finance)  
52. What is chain of thought (CoT) prompting? \- IBM, accessed April 13, 2026, [https://www.ibm.com/think/topics/chain-of-thoughts](https://www.ibm.com/think/topics/chain-of-thoughts)  
53. Chain-of-Thought (CoT) Prompting \- Prompt Engineering Guide, accessed April 13, 2026, [https://www.promptingguide.ai/techniques/cot](https://www.promptingguide.ai/techniques/cot)  
54. Leverage AI to Automate Financial Health Score Calculation using SEC 10-K Filings Data, accessed April 13, 2026, [https://st6.io/work/financial-score-calculation-with-ai/](https://st6.io/work/financial-score-calculation-with-ai/)  
55. Stochastic Multi-Agent Consensus: How to Get Better AI Ideas at Scale | MindStudio, accessed April 13, 2026, [https://www.mindstudio.ai/blog/stochastic-multi-agent-consensus-ai-agents](https://www.mindstudio.ai/blog/stochastic-multi-agent-consensus-ai-agents)  
56. Target-aware Financial Sentiment: Why Structure Beats Confidence with LLMs \- Substack, accessed April 13, 2026, [https://substack.com/home/post/p-186183792](https://substack.com/home/post/p-186183792)  
57. TELUS Digital Research Reveals a Hidden Risk in AI Model Behavior \- PR Newswire, accessed April 13, 2026, [https://www.prnewswire.com/news-releases/telus-digital-research-reveals-a-hidden-risk-in-ai-model-behavior-302696265.html](https://www.prnewswire.com/news-releases/telus-digital-research-reveals-a-hidden-risk-in-ai-model-behavior-302696265.html)  
58. TELUS Digital Research Reveals a Hidden Risk in AI Model Behavior, accessed April 13, 2026, [https://www.telusdigital.com/about/newsroom/telus-digital-research-ai-risk-persona-prompting-model-family-size](https://www.telusdigital.com/about/newsroom/telus-digital-research-ai-risk-persona-prompting-model-family-size)  
59. LLM Sampling: Temperature, Top-K, Top-P, and Min-P Explained \- Let's Data Science, accessed April 13, 2026, [https://letsdatascience.com/blog/llm-sampling-temperature-top-k-top-p-and-min-p-explained](https://letsdatascience.com/blog/llm-sampling-temperature-top-k-top-p-and-min-p-explained)  
60. LLM Temperature, Top-P, and Top-K Explained — With Python Simulations, accessed April 13, 2026, [https://machinelearningplus.com/gen-ai/llm-temperature-top-p-top-k-explained/](https://machinelearningplus.com/gen-ai/llm-temperature-top-p-top-k-explained/)  
61. LLM Settings \- Prompt Engineering Guide, accessed April 13, 2026, [https://www.promptingguide.ai/introduction/settings](https://www.promptingguide.ai/introduction/settings)  
62. LLM Sampling Parameters Guide \- smcleod.net, accessed April 13, 2026, [https://smcleod.net/2025/04/llm-sampling-parameters-guide/](https://smcleod.net/2025/04/llm-sampling-parameters-guide/)  
63. using local ollama/llama3.1:8b fails 16k context requirement \- Friends of the Crustacean, accessed April 13, 2026, [https://www.answeroverflow.com/m/1472418082180829204](https://www.answeroverflow.com/m/1472418082180829204)  
64. Extraction Schema (JSON) \- LandingAI, accessed April 13, 2026, [https://docs.landing.ai/ade/ade-extract-schema-json](https://docs.landing.ai/ade/ade-extract-schema-json)  
65. 7 Shadow AI Examples and Common Scenarios \- Knostic, accessed April 13, 2026, [https://www.knostic.ai/blog/shadow-ai-examples](https://www.knostic.ai/blog/shadow-ai-examples)  
66. AI Prompting Mistakes that Risk Company Data \- SoSafe, accessed April 13, 2026, [https://sosafe-awareness.com/blog/ai-prompting-mistakes-that-risk-company-data/](https://sosafe-awareness.com/blog/ai-prompting-mistakes-that-risk-company-data/)  
67. The Hidden Risk: When AI Becomes the Attack Surface \- Dataversity, accessed April 13, 2026, [https://www.dataversity.net/articles/the-hidden-risk-when-ai-becomes-the-attack-surface/](https://www.dataversity.net/articles/the-hidden-risk-when-ai-becomes-the-attack-surface/)  
68. \[2504.14633\] Harnessing Generative LLMs for Enhanced Financial Event Entity Extraction Performance \- arXiv, accessed April 13, 2026, [https://arxiv.org/abs/2504.14633](https://arxiv.org/abs/2504.14633)  
69. How AI unlocks deeper insights into central bank communications for investors \- Quoniam, accessed April 13, 2026, [https://www.quoniam.com/en/interview/deconstructing-news/](https://www.quoniam.com/en/interview/deconstructing-news/)  
70. LLMs for Financial Document Analysis: SEC Filings & Decks | IntuitionLabs, accessed April 13, 2026, [https://intuitionlabs.ai/articles/llm-financial-document-analysis](https://intuitionlabs.ai/articles/llm-financial-document-analysis)

[image1]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAoAAAAZCAYAAAAIcL+IAAAArUlEQVR4Xu3QLQpCQRiF4U9UEBX/siC4BcFlGARXYLPbzSIiFqNVBDG7BIvJ6A4MNqu+584dGQaDxXYPPDAzHO58d8yy/CsN5NJ1Hs1gn6SIBV5YoowJphYVh7hgjDMeOKEelpQuaum6j719KcXZoRUf+miOEdbBWRWlYJ9EM67M/ZSiaw/ofRpkgCfuuGKOGzYo+FIbR3TMfW1m7om2qPiSohk0i49m1aNn+T1v7N0UHgaD23IAAAAASUVORK5CYII=>

[image2]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAA8AAAAaCAYAAABozQZiAAAA70lEQVR4Xu3RrQ9BYRQG8McmMIJgw8aYJquCoOg2QbEJ/gRVUTSi6YpNEpggKbJiE2w2yV9gw3Mc3Ot1fWWe7VfuOff9OC/wj5fyVHCQpcCt0yEJatGYjrSlzsWcDjSi8KXfMSXozw3jexG6QI/cRu0cP01pR6n7EjK0pxWFjNo5Sehxp9CF7KlDT9TFk51lYNLQNr4noDsuKX5fsiL3lJ8rFKEolWlNM+gijvHQEDqUAaxJNylNLqv1MbLLhhYUNGpvk4Pu2seTgbxKDXrfqll4l+t95R3lPb9KDDpRIVP+KNd7ynHtJuSz9f3zozkBGi4xXt3vT/kAAAAASUVORK5CYII=>

[image3]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAA4AAAAaCAYAAACHD21cAAAAzUlEQVR4Xu3Suw5BQRDG8RENQaGRaBSiUUtUSgWNQq3wDEqt6JRKj6DVKXgID0BcEolWIy7/sQjjcmjxJb9iZ/Zsds45Ir8TP2KIv0H36f5jCthhiykmWD5Y7zEWd4D40EYHQS2cUj7VrlPBEBFd5NG6aYuEMUDG1ItonBdVZC8tlyQWiJp6SdxNnkZP1nl0jI/SFPfgRwmhj7VteOU838g2vKJvWb9p1za8Uhc3X802XiWAHjbImd7LpDDHDAnTu0saK3HXs+wv98+X5QAIOijZV1Fz/wAAAABJRU5ErkJggg==>

[image4]: <data:image/png;base64,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>

[image5]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAADYAAAAZCAYAAAB6v90+AAAB3ElEQVR4Xu2WzysFURTHj0REhCIlysLGAslCZCEWFixEKRb+BuXHP2DBSmwkJQspVkIki8dK2foHSCzEQiwkP77HmZnu3LneG++ZedL91GcxZ2aae5pzzr1EFoslDtrhC/yAN/AavjnXD/DK8cmJbchrWaUELpCs7xZ2+G8Ls3AXljvXNSTJ8Qv17kMgD26RPJ9NSuExXIWFTuwODnhPgDK4BxuVWA98hwlYrMSZaTiqxeJmBD7CViW2Bs9Ikv6Cy3Ae5rgBksVzyZn+zBLs1IMZMEX+b6eiAO7DS1itxHnNr6SsbRx2uxcO/CIn1qfF8+EcrNPimbANq/RgEjgZTuqcpNpc3J8xocQCmPorKibhmB5MQhNJGSbI3ybcHt9VmQf3FzdnkX4jAirhEcmCw8B99UzBxPpJEltXYgFSZv7LNMMT2KbfMJB2Ytycpv4KSxdcScNDkr1zh/xDQSftxHjUx1WGDE9E7rMZmKvdM8EDgweHaSpyYoNKzAeXYJxl2AuXSTb/sCxScLiZYh68uZ1SkqwjgJNSN9owtJAcpdRpekFyxPL2xFqScyD/Rl0+pjS4D0bEJgVPN6ngxQ/De5Lq4lF/QMqp4y+QyWIqSIbGEP3s9GKxWCyW/8EnkRBpiikVrOoAAAAASUVORK5CYII=>

[image6]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAACUAAAAZCAYAAAC2JufVAAAB50lEQVR4Xu2VP0jVURTHT1ghamUpSBhEUYO0CEYihBg4NBUETY0FRUSRooIEWiGCqImLOEST9J9aKjSIggiCqKWmGtob2lr18/Wcqzd5iQ76CH5f+PDOPb/fvff8e++ZFSpUqND/p1rYEnYF7M7Wm65tMArzMA5VcBl6rIxBnYHPcB4+wm+YhV35S5utg7Az7GPwyMoc0Eo9gD0rneWQ5uYsTGa+GqgMW1+AZMuf5kx+UUqr+XWGlM4sKc3UhPnAS2rdU2iBkzAM7+EWXIW7MAAX4DF0+7ZF6Vt7JXwfoC/8Ovu6+Z77MA1zsD+e/6VT8Ad+wVcYgR8wZZ5Rv/mcfYfW2PMTDoWthJ7D9lhfgofme9/CufB3wImwFeg98/v2hW9Jcjwzj1aZDJr/LGhDtXmb9KmLX9hyufU8tVAtHwq7Hr6ZB9IIX8yrLel8VXErPIl3SkqXpP5KuqjULOQX69CLYTfAJzhuHvxR84o2he8d1NnyWEh5sCnxdWsHvIHOWCuQlL18mpvD0AXN5hfuhdswY962drhhPkOn4x1Vtdc8yXVLWasaB2LdZv73I3XAa7gJR8wroqoqAM3ky7DTbI7BHXgF1+wfQ74WaQ5UrXydSy3I2yOlH978mdqkZLRfqK2FCm24FgBeRkWYQ1P/dgAAAABJRU5ErkJggg==>