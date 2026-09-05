# Model card

## Intended use
Exploratory ranking of AI-paper metadata, hands-on temporal ML education, and reproducible benchmark inspection. Not hiring, grant allocation, researcher evaluation, or automatic scientific-quality assessment.

## Model
Fixed regularized logistic regression on title unigram TF-IDF plus standardized log metadata and sampled graph features. Sigmoid calibration fitted on an independent chronological cohort. JSON weights support equivalent Python and JavaScript inference. Parameters are not selected using test performance.

## Outcome
Following-calendar-year citations in the sampled publication-year cohort, thresholded at its 90th percentile with ties included and a minimum one-citation threshold. This is an attention proxy, not a probability of scientific importance. The app's score is experimental and not guaranteed calibrated under a different population.

## Exclusions and known risks
- Historical OpenAlex metadata was retrieved now, so date-order checks do not eliminate indexing or revision leakage.
- The target uses annual bins. It is not twelve months from the exact publication date.
- Current AI taxonomy defines sampling. The model's title tokenizer is ASCII based and underrepresents non-English work.
- Author graph features favor authors with more sampled history; audit unequal effects before any allocation use.
- Matched reference count can proxy indexing completeness, venue or paper type, not just content. The numeric baseline's strong performance motivates this concern.
- Citation count has sociological and field biases. High citation does not imply correctness or usefulness.
- Authors, preprint/journal versions and topics can overlap across years. DOI deduplication does not identify every near-duplicate version.
- Bootstrap intervals assume independent papers and are exploratory.
- Sparse sampled graph features are not complete author or institution histories.
- Live search returns at most 20 search-selected records and can drift away from the training population.

## Validation
See `dist/evaluation.json` and tests. Metadata baseline exceeds the full model on the current test set. Both this result and limitations must accompany any portfolio claim. A larger sample, archived publication snapshots, content ablations and future prospective evaluation are necessary before stronger claims.
