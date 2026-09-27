"""
torch_compat.py - make stable-baselines3 model loading work with newer PyTorch builds.

Problem: torch >= 2.1x cannot torch.load() from the non-seekable zip-member streams that
stable-baselines3 (DQN.load) passes in ("PytorchStreamReader failed reading file .data/serialization_id").
Saving is unaffected and the saved zips are valid. Fix: read the member fully into memory first.
Import this module BEFORE calling DQN.load (dqn_policy / hybrid_policy / policy_adaptation already do).
"""
import io
import torch

if not getattr(torch, "_kukule_load_patched", False):
    _orig_load = torch.load

    def _load(f, *args, **kwargs):
        if hasattr(f, "read") and not isinstance(f, io.BytesIO):
            f = io.BytesIO(f.read())
        return _orig_load(f, *args, **kwargs)

    torch.load = _load
    torch._kukule_load_patched = True
