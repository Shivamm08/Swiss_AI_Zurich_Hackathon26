# Impact assignment rules

The impact level is assigned from the ticket `Description` and `Business Entity`.
The existing `Impact` value must not be used as an input feature.

## Impact definitions

| Output value | Definition |
| --- | --- |
| `highest` | Major / widespread: full unavailability of critical IT services supporting key operations, including more than two hours of downtime. |
| `high` | Significant / large: partial unavailability of critical IT services, one or more business entities affected, or financial counterparties affected. |
| `medium` | Moderate / limited: full unavailability of non-critical IT services or up to one business entity affected. |
| `low` | Minor / localized: partial unavailability of non-critical IT services or only individual users affected. |
| `lowest` | No direct impact / information: no direct operational impact, informational request, or maintenance without service degradation. |

## Embedding rule

1. Embed each ticket `Description` with the finance-domain BERT model.
2. Embed each ticket `Business Entity` value with the same model.
3. Create a weighted representation:

   `ticket_embedding = 0.7 * description_embedding + 0.3 * business_entity_embedding`

   Normalize the resulting vector before comparison.
4. Embed each definition in the Impact definitions table above.
5. Calculate cosine distance between `ticket_embedding` and every definition embedding.
6. Assign the output value with the smallest cosine distance. The only allowed
   output values are `highest`, `high`, `medium`, `low`, and `lowest`.

The implementation is in `classify_impact.py`. It writes the enriched dataset
to `jira_first_20000_impact_classified.csv` and stores the embedded impact
prototypes under `impact_model/`.
