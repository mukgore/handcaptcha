# -*- coding: utf-8 -*-
"""All TBD/tunable values from dataset_expansion_spec_v1.md live here as
overridable defaults. None of the defaults below are validated against real
Jester/InterHand2.6M data (§6 of the spec) -- they are placeholders so the
pipeline is runnable; re-derive them once real datasets are available
(grid_search_frontal.py for t_frontal_deg, stage5_weights.py's output for
w2_new/w3_new).
"""
from dataclasses import dataclass, field
from typing import List, Tuple


@dataclass
class PipelineConfig:
    # Stage 2 -- quality filter
    quality_n_std: float = 3.0
    quality_conf_min: float = 0.5
    quality_max_drop_frac: float = 0.10

    # Stage 3 -- frontality filter
    t_frontal_deg: float = 21.0  # placeholder, literature precedent only (face-frontality research)
    frontal_pass_frac: float = 0.90
    candidate_t_frontal_list: List[float] = field(default_factory=lambda: [10.0, 15.0, 20.0, 25.0, 30.0])

    # Stage 4 -- length normalization
    target_len_range_sec: Tuple[float, float] = (5.0, 6.0)

    # Stage 5 -- open-hand / weight re-estimation
    t_straight_deg: float = 160.0  # placeholder; ideally measured from the 6 original subject videos

    # Stage 6/7 -- occlusion + gate
    gate_pass_frac: float = 1.00
    condition1_margin_frac: float = 0.15  # shrink radius by this fraction when checking "fully covered"
    condition2_margin_frac: float = 0.10  # grow radius by this fraction when checking "clearly outside"

    def to_dict(self):
        d = dict(self.__dict__)
        d["target_len_range_sec"] = list(self.target_len_range_sec)
        d["candidate_t_frontal_list"] = list(self.candidate_t_frontal_list)
        return d
