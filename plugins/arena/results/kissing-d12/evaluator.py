import numpy as np


def _overlap_loss(scaled, n):
    total = 0.0
    for i in range(n):
        diffs = scaled[i + 1 :] - scaled[i]
        sq_dists = np.sum(diffs ** 2, axis=1)
        mask = sq_dists < 4.0
        if mask.any():
            total += float(np.sum(2.0 - np.sqrt(sq_dists[mask])))
    return total


def evaluate(data: dict) -> float:
    vectors = data["vectors"]
    n, d = 841, 12

    if len(vectors) != n:
        raise ValueError(f"Expected {n} vectors, got {len(vectors)}")
    for v in vectors:
        if len(v) != d:
            raise ValueError(f"Each vector must have {d} components, got {len(v)}")

    float_vecs = np.array([[float(x) for x in v] for v in vectors], dtype=np.float64)
    if not np.isfinite(float_vecs).all():
        raise ValueError("All vector components must be finite")
    sq_norms_f = np.sum(float_vecs ** 2, axis=1)
    if float(sq_norms_f.min()) == 0.0:
        raise ValueError("All vectors must be non-zero")

    int_vecs = np.round(float_vecs).astype(np.int64)
    if np.max(np.abs(float_vecs - int_vecs.astype(np.float64))) < 1e-9:
        sq_norms = np.sum(int_vecs ** 2, axis=1)
        max_sq_norm = int(sq_norms.max())
        valid = True
        for i in range(n):
            diffs = int_vecs[i + 1 :] - int_vecs[i]
            sq_dists = np.sum(diffs ** 2, axis=1)
            if len(sq_dists) > 0 and int(sq_dists.min()) < max_sq_norm:
                valid = False
                break
        if valid:
            return 0.0

    norms = np.sqrt(sq_norms_f[:, None])
    scaled = float_vecs / norms * 2.0
    return _overlap_loss(scaled, n)