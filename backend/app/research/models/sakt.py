"""
SAKT — Self-Attentive Knowledge Tracing (Pandey & Karypis 2019)

PyTorch implementation of the SAKT model:
- Input:  exercise embedding + correctness embedding (interaction embedding)
- Architecture:  Transformer (multi-head self-attention) + feed-forward
- Positional encoding:  sinusoidal, applied to exercise embeddings
- Output:  probability of answering correctly for each candidate exercise
- Loss:  masked BCE — only compute on the practiced exercise position

References:
    - Pandey, S., & Karypis, G. (2019). "A Self-Attentive model for Knowledge
      Tracing." arXiv:1907.06837.
"""
from __future__ import annotations

import logging
import math
from typing import List, Optional, Tuple

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, Dataset

logger = logging.getLogger(__name__)


class SinusoidalPositionEncoding(nn.Module):
    """Sinusoidal positional encoding (Vaswani et al. 2017)."""

    def __init__(self, d_model: int, max_len: int = 500):
        super().__init__()
        pe = torch.zeros(max_len, d_model)
        position = torch.arange(0, max_len, dtype=torch.float).unsqueeze(1)
        div_term = torch.exp(
            torch.arange(0, d_model, 2).float()
            * (-math.log(10000.0) / d_model)
        )
        pe[:, 0::2] = torch.sin(position * div_term)
        pe[:, 1::2] = torch.cos(position * div_term)
        self.register_buffer("pe", pe)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """x: (batch, seq_len, d_model) -> add positional encoding."""
        seq_len = x.size(1)
        return x + self.pe[:seq_len, :]


class SAKTModel(nn.Module):
    """Self-Attentive Knowledge Tracing (Pandey & Karypis 2019).

    Args:
        n_skills: Number of knowledge components (exercises).
        embed_dim: Dimension of exercise/correctness embeddings.
        num_heads: Number of attention heads.
        num_layers: Number of transformer layers.
        dropout: Dropout probability.
        max_seq_len: Maximum sequence length (for positional encoding).
    """

    def __init__(
        self,
        n_skills: int,
        embed_dim: int = 64,
        num_heads: int = 4,
        num_layers: int = 1,
        dropout: float = 0.2,
        max_seq_len: int = 500,
    ):
        super().__init__()
        self.n_skills = n_skills
        self.embed_dim = embed_dim

        # Embeddings: exercise + correctness interaction
        self.exercise_embed = nn.Embedding(n_skills + 1, embed_dim, padding_idx=0)
        self.correctness_embed = nn.Embedding(2, embed_dim)

        # Positional encoding
        self.pos_encoding = SinusoidalPositionEncoding(embed_dim, max_len=max_seq_len)

        # Layer norm + dropout before transformer
        self.layer_norm = nn.LayerNorm(embed_dim)
        self.dropout = nn.Dropout(dropout)

        # Transformer encoder (self-attention blocks)
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=embed_dim,
            nhead=num_heads,
            dim_feedforward=embed_dim * 4,
            dropout=dropout,
            batch_first=True,
        )
        self.transformer = nn.TransformerEncoder(encoder_layer, num_layers=num_layers)

        # Output projection: predict correctness for each exercise
        self.fc = nn.Linear(embed_dim, 1)
        self.sigmoid = nn.Sigmoid()

    def forward(
        self,
        exercise_ids: torch.Tensor,
        correctness: torch.Tensor,
        mask: Optional[torch.Tensor] = None,
    ) -> torch.Tensor:
        """Forward pass.

        Args:
            exercise_ids: (batch, seq_len) integer exercise indices (1-based, 0=pad).
            correctness: (batch, seq_len) integer correctness (0 or 1).
            mask: (batch, seq_len) boolean padding mask (True = valid).

        Returns:
            (batch, seq_len, 1) predicted correctness probabilities.
        """
        # Interaction embedding = exercise_embed + correctness_embed
        ex_emb = self.exercise_embed(exercise_ids)  # (batch, seq, embed_dim)
        cor_emb = self.correctness_embed(correctness)
        inter_emb = ex_emb + cor_emb

        inter_emb = self.pos_encoding(inter_emb)
        inter_emb = self.layer_norm(inter_emb)
        inter_emb = self.dropout(inter_emb)

        # Transformer expects src_key_padding_mask: (batch, seq) True = pad
        if mask is not None:
            src_key_padding_mask = ~mask.bool()  # True = pad positions
        else:
            src_key_padding_mask = None

        trans_out = self.transformer(
            inter_emb, src_key_padding_mask=src_key_padding_mask
        )
        trans_out = self.dropout(trans_out)

        logits = self.fc(trans_out)  # (batch, seq, 1)
        return self.sigmoid(logits)


class SAKTDataset(Dataset):
    """Dataset wrapper for SAKT training.

    Input encoding:
        - exercise_ids: 1-based skill index (0 = padding)
        - correctness: 0 or 1
    Target encoding:
        - target: (seq_len, 1) correctness at practiced exercise
        - mask: (seq_len,) 1 where we have a label
    """

    def __init__(
        self,
        sequences: List[List[dict]],
        max_seq_len: Optional[int] = None,
    ):
        self.exercise_ids: List[torch.Tensor] = []
        self.correctness: List[torch.Tensor] = []
        self.targets: List[torch.Tensor] = []
        self.masks: List[torch.Tensor] = []

        if max_seq_len is None and sequences:
            max_seq_len = max(len(s) for s in sequences if s)
        self.max_seq_len = max_seq_len or 200

        for seq in sequences:
            if not seq:
                continue
            n_skills = seq[0]["skill_onehot"].shape[0]
            seq_len = min(len(seq), self.max_seq_len)

            ex_ids = torch.zeros(self.max_seq_len, dtype=torch.long)
            correct = torch.zeros(self.max_seq_len, dtype=torch.long)
            target = torch.zeros(self.max_seq_len, 1, dtype=torch.float32)
            mask = torch.zeros(self.max_seq_len, dtype=torch.float32)

            for t in range(seq_len):
                entry = seq[t]
                skill_oh = entry["skill_onehot"]
                skill_idx = int(np.argmax(skill_oh))
                # 1-based index for embedding (0 reserved for padding)
                ex_ids[t] = skill_idx + 1
                correct[t] = int(entry["correct"])
                target[t, 0] = float(entry["correct"])
                mask[t] = 1.0

            self.exercise_ids.append(ex_ids)
            self.correctness.append(correct)
            self.targets.append(target)
            self.masks.append(mask)

        self.n_skills = sequences[0][0]["skill_onehot"].shape[0] if sequences and sequences[0] else 1

    def __len__(self) -> int:
        return len(self.exercise_ids)

    def __getitem__(self, idx: int) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
        return (
            self.exercise_ids[idx],
            self.correctness[idx],
            self.targets[idx],
            self.masks[idx],
        )


class SAKTTrainer:
    """Training loop for SAKT with masked BCE loss.

    Args:
        n_skills: Number of skills (exercises).
        embed_dim: Embedding dimension.
        num_heads: Number of attention heads.
        num_layers: Number of transformer layers.
        learning_rate: Adam learning rate.
        batch_size: Training batch size.
        max_epochs: Maximum training epochs.
        patience: Early stopping patience.
        device: torch device string.
    """

    def __init__(
        self,
        n_skills: int,
        embed_dim: int = 64,
        num_heads: int = 4,
        num_layers: int = 1,
        learning_rate: float = 0.001,
        batch_size: int = 32,
        max_epochs: int = 30,
        patience: int = 5,
        device: Optional[str] = None,
    ):
        self.n_skills = n_skills
        self.embed_dim = embed_dim
        self.num_heads = num_heads
        self.num_layers = num_layers
        self.lr = learning_rate
        self.batch_size = batch_size
        self.max_epochs = max_epochs
        self.patience = patience
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")

        self.model = SAKTModel(
            n_skills=n_skills,
            embed_dim=embed_dim,
            num_heads=num_heads,
            num_layers=num_layers,
        ).to(self.device)
        self.optimizer = torch.optim.Adam(self.model.parameters(), lr=learning_rate)
        self.criterion = nn.BCELoss(reduction="none")

    def _masked_loss(
        self, outputs: torch.Tensor, targets: torch.Tensor, masks: torch.Tensor
    ) -> torch.Tensor:
        """Masked BCE loss — only compute on practiced positions."""
        loss = self.criterion(outputs, targets)  # (batch, seq, 1)
        masked = loss * masks.unsqueeze(-1)  # zero out non-practiced positions
        total = masked.sum()
        count = masks.sum().clamp(min=1.0)
        return total / count

    def train_model(
        self,
        train_sequences: List[List[dict]],
        val_sequences: Optional[List[List[dict]]] = None,
    ) -> dict:
        """Train SAKT model with shifted input/target and masked loss.

        SAKT protocol: inputs[0..t-1] (exercise_ids + correctness) predict
        target[t] (correctness of exercise at step t).
        """
        train_dataset = SAKTDataset(train_sequences, max_seq_len=200)
        train_loader = DataLoader(
            train_dataset, batch_size=self.batch_size, shuffle=True, num_workers=0
        )

        best_val_loss = float("inf")
        patience_counter = 0
        best_epoch = 0

        self.model.train()
        for epoch in range(self.max_epochs):
            total_loss = 0.0
            n_batches = 0
            for ex_ids, correct, targets, masks in train_loader:
                ex_ids = ex_ids.to(self.device)
                correct = correct.to(self.device)
                targets = targets.to(self.device)
                masks = masks.to(self.device)

                # Shift: inputs[0..T-2] predict targets[1..T-1]
                if ex_ids.size(1) > 1:
                    inp_ex = ex_ids[:, :-1]
                    inp_cor = correct[:, :-1]
                    tgt = targets[:, 1:]
                    msk = masks[:, 1:]
                else:
                    continue

                self.optimizer.zero_grad()
                outputs = self.model(inp_ex, inp_cor, mask=msk)  # (batch, T-1, 1)
                loss = self._masked_loss(outputs, tgt, msk)
                loss.backward()
                torch.nn.utils.clip_grad_norm_(self.model.parameters(), max_norm=3.0)
                self.optimizer.step()

                total_loss += loss.item()
                n_batches += 1

            avg_loss = total_loss / max(n_batches, 1)

            if val_sequences is not None and len(val_sequences) > 0:
                val_loss = self._eval(val_sequences)
                if val_loss < best_val_loss - 1e-4:
                    best_val_loss = val_loss
                    best_epoch = epoch
                    patience_counter = 0
                else:
                    patience_counter += 1
                if patience_counter >= self.patience:
                    logger.info("[SAKT] Early stopping at epoch %d", epoch)
                    break
            else:
                best_epoch = epoch

            if (epoch + 1) % 5 == 0:
                logger.info(
                    "[SAKT] Epoch %d/%d — train_loss=%.4f",
                    epoch + 1, self.max_epochs, avg_loss,
                )

        return {
            "epochs_trained": best_epoch + 1,
            "best_val_loss": best_val_loss,
        }

    def _eval(self, sequences: List[List[dict]]) -> float:
        """Evaluate on a set of sequences, return average masked BCE loss."""
        dataset = SAKTDataset(sequences, max_seq_len=200)
        loader = DataLoader(dataset, batch_size=self.batch_size, shuffle=False, num_workers=0)
        self.model.eval()
        total_loss = 0.0
        n_batches = 0
        with torch.no_grad():
            for ex_ids, correct, targets, masks in loader:
                ex_ids = ex_ids.to(self.device)
                correct = correct.to(self.device)
                targets = targets.to(self.device)
                masks = masks.to(self.device)
                if ex_ids.size(1) > 1:
                    inp_ex = ex_ids[:, :-1]
                    inp_cor = correct[:, :-1]
                    tgt = targets[:, 1:]
                    msk = masks[:, 1:]
                else:
                    continue
                outputs = self.model(inp_ex, inp_cor, mask=msk)
                loss = self._masked_loss(outputs, tgt, msk)
                total_loss += loss.item()
                n_batches += 1
        self.model.train()
        return total_loss / max(n_batches, 1)

    def predict(
        self,
        sequences: List[List[dict]],
    ) -> List[List[float]]:
        """Predict correctness probabilities for each timestep.

        At step t, the model has seen interactions 0..t-1 and predicts
        the correctness for the exercise practiced at step t.

        Args:
            sequences: Per-student interaction sequences.

        Returns:
            List of per-student per-step predicted probabilities.
        """
        self.model.eval()
        all_preds: List[List[float]] = []

        for seq in sequences:
            n = len(seq)
            if n == 0:
                all_preds.append([])
                continue
            # Handle edge case where seq contains non-dict items (e.g. [[]])
            valid_seq = [entry for entry in seq if isinstance(entry, dict)]
            n = len(valid_seq)
            if n == 0:
                all_preds.append([])
                continue

            # Build input tensors
            max_seq = min(n, 200)
            ex_ids = torch.zeros(1, max_seq, dtype=torch.long, device=self.device)
            correct = torch.zeros(1, max_seq, dtype=torch.long, device=self.device)
            for t in range(max_seq):
                entry = valid_seq[t]
                skill_oh = entry["skill_onehot"]
                skill_idx = int(np.argmax(skill_oh))
                ex_ids[0, t] = skill_idx + 1
                correct[0, t] = int(entry["correct"])

            mask = torch.ones(1, max_seq, device=self.device)

            with torch.no_grad():
                outputs = self.model(ex_ids, correct, mask=mask)  # (1, max_seq, 1)

            preds = []
            for t in range(n):
                if t == 0 or t >= max_seq:
                    preds.append(float(outputs[0, 0, 0].cpu()))
                else:
                    # outputs[t-1] predicts step t (after seeing 0..t-1)
                    preds.append(float(outputs[0, t - 1, 0].cpu()))
            all_preds.append(preds)


        self.model.train()
        return all_preds
