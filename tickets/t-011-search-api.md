# T-011: Search API

## Objective
Search endpoints for text-to-image and image-to-text retrieval.

## API
- POST /api/search/text — {query, index_id, bit_length, top_k, method}
- POST /api/search/image — multipart {image, index_id, bit_length, top_k, method}

## Response
- results: [{rank, score, thumbnail_b64, caption, id}, ...]
- query_hash: binary code visualization
- search_time_ms

## Acceptance Criteria
- [ ] Text search returns top-K images with scores + thumbnails
- [ ] Image search returns top-K texts with scores
- [ ] Hamming and cosine methods supported
- [ ] Multiple bit lengths supported
- [ ] gate.sh PASS

## Status: PENDING
